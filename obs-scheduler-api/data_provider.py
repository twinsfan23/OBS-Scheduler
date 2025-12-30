import json
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import time
import os
import uuid
import subprocess
import shutil

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

# Allow override when set before import
def set_data_root(root_path: str):
    global DATA_ROOT, VIDEO_LIST_FILE, ACTIVITY_LIST_FILE, SCHEDULE_FILE, EVENT_START_TIMESTAMP_FILE, SCHEDULE_SAVE_DIR, CONFIG_FILE
    DATA_ROOT = Path(root_path)
    VIDEO_LIST_FILE = DATA_ROOT / "filelist.txt"
    ACTIVITY_LIST_FILE = DATA_ROOT / "alist.txt"
    SCHEDULE_FILE = DATA_ROOT / "schedule.json"
    EVENT_START_TIMESTAMP_FILE = DATA_ROOT / "timestamp"
    SCHEDULE_SAVE_DIR = DATA_ROOT / "schedules"
    CONFIG_FILE = DATA_ROOT / "config.json"

VIDEO_LIST_FILE = DATA_ROOT / "filelist.txt"
ACTIVITY_LIST_FILE = DATA_ROOT / "alist.txt"
SCHEDULE_FILE = DATA_ROOT / "schedule.json"
EVENT_START_TIMESTAMP_FILE = DATA_ROOT / "timestamp"
SCHEDULE_SAVE_DIR = DATA_ROOT / "schedules"
CONFIG_FILE = DATA_ROOT / "config.json"
_LAST_SCAN = 0
_SCAN_INTERVAL_SEC = 5


def _load_json_array(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def get_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)

def write_config(config: dict) -> None:
    _write_json(CONFIG_FILE, config)


def get_contest_start() -> int:
    if not EVENT_START_TIMESTAMP_FILE.exists():
        now = int(current_time_ms())
        EVENT_START_TIMESTAMP_FILE.parent.mkdir(parents=True, exist_ok=True)
        EVENT_START_TIMESTAMP_FILE.write_text(str(now), encoding="ascii")
        return now
    return int(EVENT_START_TIMESTAMP_FILE.read_text(encoding="utf-8-sig").strip())


def current_time_ms() -> int:
    return int(time.time() * 1000)


def _load_items(path: Path) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    items = _load_json_array(path)
    by_name = {}
    by_uuid = {}
    for entry in items:
        by_name[entry["name"]] = entry
        by_uuid[entry["uuid"]] = entry
    return by_name, by_uuid


def get_videos() -> Tuple[Dict[str, dict], Dict[str, dict]]:
    refresh_videos_if_needed()
    return _load_items(VIDEO_LIST_FILE)


def get_activities() -> Tuple[Dict[str, dict], Dict[str, dict]]:
    return _load_items(ACTIVITY_LIST_FILE)


def get_all_items_by_name() -> Dict[str, dict]:
    videos, _ = get_videos()
    activities, _ = get_activities()
    merged = {}
    merged.update(videos)
    merged.update(activities)
    return merged


def write_items(path: Path, items: List[dict]) -> None:
    _write_json(path, items)


def write_videos(items: List[dict]) -> None:
    write_items(VIDEO_LIST_FILE, items)


def write_activities(items: List[dict]) -> None:
    write_items(ACTIVITY_LIST_FILE, items)


def get_schedule() -> List[dict]:
    return _load_json_array(SCHEDULE_FILE)


def write_schedule(schedule: List[dict]) -> None:
    _write_json(SCHEDULE_FILE, schedule)


def update_schedule_from_json(raw: str) -> None:
    decoded = urllib.parse.unquote(raw)
    payload = json.loads(decoded)
    write_schedule(payload)


def start_contest(new_ts_ms: int | None = None) -> None:
    if new_ts_ms is None:
        new_ts_ms = current_time_ms()
    current_start = get_contest_start()
    diff = new_ts_ms - current_start
    EVENT_START_TIMESTAMP_FILE.write_text(str(new_ts_ms), encoding="utf-8")
    schedule = get_schedule()
    for entry in schedule:
        entry["start_timestamp"] += diff
    write_schedule(schedule)


def get_schedule_list() -> List[str]:
    if not SCHEDULE_SAVE_DIR.exists():
        return []
    seen = set()
    for f in SCHEDULE_SAVE_DIR.glob("*.*"):
        seen.add(f.stem)
    return sorted(seen)


def save_schedule(name: str) -> None:
    schedule = _load_json_array(SCHEDULE_FILE)
    payload = {"start_timestamp": get_contest_start(), "schedule": schedule}
    count = sum(1 for f in SCHEDULE_SAVE_DIR.glob(f"{name}.*"))
    target = SCHEDULE_SAVE_DIR / f"{name}.{count}"
    _write_json(target, payload)


def load_schedule(name: str) -> None:
    versions = sorted(SCHEDULE_SAVE_DIR.glob(f"{name}.*"))
    if not versions:
        raise FileNotFoundError(name)
    latest = versions[-1]
    payload = json.loads(latest.read_text())
    start_ts = payload["start_timestamp"]
    schedule = payload["schedule"]

    contest_start = datetime.utcnow()
    loaded_start = datetime.utcfromtimestamp(start_ts / 1000)
    contest_start = contest_start.replace(hour=loaded_start.hour, minute=loaded_start.minute, second=loaded_start.second, microsecond=loaded_start.microsecond)
    start_contest(int(contest_start.timestamp() * 1000))

    rebased = []
    for entry in schedule:
        new_start = contest_start.replace()
        old = datetime.utcfromtimestamp(entry["start_timestamp"] / 1000)
        new_start = new_start.replace(hour=old.hour, minute=old.minute, second=old.second, microsecond=old.microsecond)
        entry_copy = dict(entry)
        entry_copy["start_timestamp"] = int(new_start.timestamp() * 1000)
        rebased.append(entry_copy)
    write_schedule(rebased)


def as_schedule_payload() -> dict:
    items = get_all_items_by_name()
    schedule = sorted(get_schedule(), key=lambda e: e["start_timestamp"])
    contest_ts = get_contest_start()
    rendered = []
    for entry in schedule:
        item = items.get(entry["name"])
        if not item:
            continue
        duration = item["duration"]
        if duration <= 0:
            duration = 60000
        # Disclaimer offsets will be handled by caller if needed.
        stop = entry["start_timestamp"] + duration
        rendered.append({
            "_id": entry["uuid"],
            "start": entry["start_timestamp"],
            "stop": stop,
            "name": entry["name"],
        })
    return {"contest_timestamp": contest_ts, "schedule": rendered}


def _video_dir_from_config() -> Path | None:
    cfg = get_config()
    video_dir = cfg.get("server-video-dir") or cfg.get("obs-video-dir")
    if not video_dir:
        return None
    return Path(video_dir)


def _probe_duration_ms(path: Path) -> int:
    try:
        ffprobe_path = _get_ffprobe_path()
        if not ffprobe_path:
            return 0
        result = subprocess.run(
            [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        output = result.stdout.strip()
        if output:
            seconds = float(output)
            return int(seconds * 1000)
    except Exception:
        pass
    return 0


def _get_ffprobe_path() -> str | None:
    env_path = os.getenv("FFPROBE_PATH")
    if env_path:
        return env_path
    hardcoded = "C:\\ffmpeg\\bin\\ffprobe.exe"
    if Path(hardcoded).exists():
        return hardcoded
    return shutil.which("ffprobe")


def get_ffprobe_path() -> str | None:
    return _get_ffprobe_path()


def refresh_videos_if_needed(force: bool = False, rebuild: bool = False) -> None:
    global _LAST_SCAN
    now = time.time()
    if not force and (now - _LAST_SCAN) < _SCAN_INTERVAL_SEC:
        return
    _LAST_SCAN = now
    video_dir = _video_dir_from_config()
    if not video_dir or not video_dir.exists():
        return
    by_name, _ = _load_items(VIDEO_LIST_FILE)
    extensions = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mpg", ".mpeg"}
    updated = [] if rebuild else list(by_name.values())
    updated_map = {item["name"]: item for item in updated}
    for path in video_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue
        name = path.name
        duration = _probe_duration_ms(path)
        if name in updated_map:
            existing = updated_map[name]
            if existing.get("duration", 0) <= 0 and duration > 0:
                existing["duration"] = duration
            continue
        item_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
        updated.append({
            "uuid": item_uuid,
            "name": name,
            "duration": duration,
            "isVideo": True,
        })
    write_videos(updated)
