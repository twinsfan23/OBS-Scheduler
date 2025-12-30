from fastapi import FastAPI, Query, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from uuid import uuid4
from pathlib import Path
import shutil
import shutil
from datetime import datetime

import data_provider as dp
from scheduler_loop import PlaybackLoop
from obs_gateway import heartbeat, start_streaming, stop_streaming, apply_audio_monitoring, get_stream_status

app = FastAPI(title="OBS Scheduler (Python)", version="0.1.0")
loop = PlaybackLoop()


@app.on_event("startup")
async def _startup():
    await loop.start()


def _html_table(headers, rows):
    html = ["<table>", "<tr>"]
    for h in headers:
        html.append(f"<td>{h}</td>")
    html.append("</tr>")
    for idx, row in enumerate(rows):
        bgcolor = "" if idx % 2 == 0 else " bgcolor=\"#CCCCCC\""
        html.append(f"<tr{bgcolor}>")
        for cell in row:
            html.append(f"<td>{cell}</td>")
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)


@app.get("/ScheduleGet")
def schedule_get():
    return JSONResponse(dp.as_schedule_payload())


@app.get("/ScheduleList")
def schedule_list():
    files = dp.get_schedule_list()
    options = "".join([f'<option value="{f}">{f}</option>' for f in files])
    html = (
        '<form> Load schedule '
        f'<select id = "load_file">{options}</select>'
        '<input type = "submit" value = "Load" onclick = "load();"/></form>'
    )
    return HTMLResponse(html)


@app.get("/SaveSchedule")
def save_schedule(file: str = Query(..., alias="file")):
    dp.save_schedule(file)
    return Response(status_code=204)


@app.get("/LoadSchedule")
def load_schedule(file: str = Query(..., alias="file")):
    try:
        dp.load_schedule(file)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="schedule not found")
    return Response(status_code=204)


@app.get("/AddScheduleEntry")
def add_schedule_entry(uuid: str = Query(...)):
    items_by_uuid = dp.get_all_items_by_name()
    all_items_uuid = {}
    videos_uuid = dp.get_videos()[1]
    activities_uuid = dp.get_activities()[1]
    all_items_uuid.update(videos_uuid)
    all_items_uuid.update(activities_uuid)

    item = all_items_uuid.get(uuid)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    now = dp.current_time_ms()
    interval_ms = 5 * 60 * 1000
    start_time = now + interval_ms
    start_time = ((start_time + interval_ms - 1) // interval_ms) * interval_ms

    schedule = dp.get_schedule()
    schedule.append(
        {
            "uuid": str(uuid4()),
            "start_timestamp": start_time,
            "name": item["name"],
        }
    )
    dp.write_schedule(schedule)
    return JSONResponse(dp.as_schedule_payload())


@app.get("/RemoveScheduleEntry")
def remove_schedule_entry(uuid: str = Query(...)):
    schedule = dp.get_schedule()
    schedule = [e for e in schedule if e["uuid"] != uuid]
    dp.write_schedule(schedule)
    return JSONResponse(dp.as_schedule_payload())


@app.get("/DeleteVideo")
def delete_video(uuid: str = Query(...)):
    videos_by_name, videos_by_uuid = dp.get_videos()
    item = videos_by_uuid.get(uuid)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found")
    name = item["name"]
    remaining = [v for v in videos_by_name.values() if v["uuid"] != uuid]
    dp.write_videos(remaining)
    schedule = [e for e in dp.get_schedule() if e["name"] != name]
    dp.write_schedule(schedule)
    return JSONResponse(dp.as_schedule_payload())


@app.get("/ArchiveVideo")
def archive_video(uuid: str = Query(...)):
    videos_by_name, videos_by_uuid = dp.get_videos()
    item = videos_by_uuid.get(uuid)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found")
    config = dp.get_config()
    video_dir = config.get("server-video-dir") or config.get("obs-video-dir")
    archive_dir = config.get("archive-dir")
    if not video_dir or not archive_dir:
        raise HTTPException(status_code=400, detail="archive-dir or video directory not set")
    source_path = Path(video_dir) / item["name"]
    archive_path = Path(archive_dir)
    archive_path.mkdir(parents=True, exist_ok=True)
    target = archive_path / source_path.name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        idx = 1
        while True:
            candidate = archive_path / f"{stem} ({idx}){suffix}"
            if not candidate.exists():
                target = candidate
                break
            idx += 1
    if source_path.exists():
        shutil.move(str(source_path), str(target))
    remaining = [v for v in videos_by_name.values() if v["uuid"] != uuid]
    dp.write_videos(remaining)
    schedule = [e for e in dp.get_schedule() if e["name"] != item["name"]]
    dp.write_schedule(schedule)
    return JSONResponse(dp.as_schedule_payload())


@app.get("/RenameVideo")
def rename_video(uuid: str = Query(...), name: str = Query(...)):
    new_name = name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="New name is required")
    videos_by_name, videos_by_uuid = dp.get_videos()
    item = videos_by_uuid.get(uuid)
    if not item:
        raise HTTPException(status_code=404, detail="Video not found")
    if new_name in videos_by_name and videos_by_name[new_name]["uuid"] != uuid:
        raise HTTPException(status_code=400, detail="A video with that name already exists")
    config = dp.get_config()
    video_dir = config.get("server-video-dir") or config.get("obs-video-dir")
    if not video_dir:
        raise HTTPException(status_code=400, detail="Video directory not set")
    source_path = Path(video_dir) / item["name"]
    target_path = Path(video_dir) / new_name
    if target_path.exists():
        raise HTTPException(status_code=400, detail="Target file already exists")
    if source_path.exists():
        shutil.move(str(source_path), str(target_path))
    updated = []
    for v in videos_by_name.values():
        if v["uuid"] == uuid:
            v = dict(v)
            v["name"] = new_name
        updated.append(v)
    dp.write_videos(updated)
    schedule = []
    for e in dp.get_schedule():
        if e["name"] == item["name"]:
            e = dict(e)
            e["name"] = new_name
        schedule.append(e)
    dp.write_schedule(schedule)
    return JSONResponse(dp.as_schedule_payload())


@app.get("/RescheduleScheduleEntry")
def reschedule_schedule_entry(uuid: str = Query(...), start: int = Query(...)):
    schedule = dp.get_schedule()
    changed = False
    for entry in schedule:
        if entry["uuid"] == uuid:
            if entry["start_timestamp"] == start:
                return Response("no-op")
            entry["start_timestamp"] = start
            changed = True
    if changed:
        dp.write_schedule(schedule)
    return JSONResponse(dp.as_schedule_payload())


@app.get("/StartContest")
def start_contest(time: str | None = Query(None)):
    if time:
        h, m = time.split("-")
        now = datetime.now()
        new_start = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
        dp.start_contest(int(new_start.timestamp() * 1000))
    else:
        dp.start_contest()
    return Response(status_code=204)


@app.get("/AddActivity")
def add_activity(name: str, duration: str):
    if "-" in duration:
        mins, secs = duration.split("-")
        dur_ms = int(mins) * 60000 + int(secs) * 1000
    else:
        dur_ms = int(duration) * 1000
    activities_by_name, _ = dp.get_activities()
    activities = list(activities_by_name.values())
    activities.append(
        {
            "uuid": str(uuid4()),
            "name": name,
            "duration": dur_ms,
            "isVideo": False,
        }
    )
    dp.write_activities(activities)
    return Response(status_code=204)


@app.get("/VideoList")
def video_list(type: str = "video"):
    if type == "video":
        items_by_name, _ = dp.get_videos()
    else:
        items_by_name, _ = dp.get_activities()
    items = sorted(items_by_name.values(), key=lambda x: x["name"])
    schedule = dp.get_schedule()
    contest_start = dp.get_contest_start()
    rows = []
    now = dp.current_time_ms()
    for idx, item in enumerate(items):
        duration_ms = item["duration"]
        dur = f"{duration_ms // 60000}:{(duration_ms // 1000) % 60:02d}"
        prev, future = [], []
        p = f = 0
        for s in schedule:
            if s["name"] != item["name"]:
                continue
            diff = abs((s["start_timestamp"] - contest_start) // 60000)
            contest_diff = f"{diff // 60}:{diff % 60:02d}"
            if s["start_timestamp"] < contest_start:
                contest_diff = "-" + contest_diff
            if s["start_timestamp"] < now:
                prev.append(contest_diff)
                p += 1
            else:
                future.append(contest_diff)
                f += 1
        max_list = 5
        prev_display = prev[:max_list]
        future_display = future[:max_list]
        prev_play = ", ".join(prev_display) + (" ..." if len(prev) > max_list else "")
        future_play = ", ".join(future_display) + (" ..." if len(future) > max_list else "")
        if type == "video":
            rows.append(
                [
                    f'<input type="submit" value="Schedule" onclick=\'add_event("{item["uuid"]}");\'/>',
                    f'<input type="submit" value="Archive" onclick=\'archive_video("{item["uuid"]}");\'/>'
                    f'<input type="submit" value="Rename" onclick=\'rename_video("{item["uuid"]}");\'/>',
                    item["name"],
                    dur,
                    f"{prev_play} ({p})",
                    f"{future_play} ({f})",
                ]
            )
        else:
            rows.append(
                [
                    f'<input type="submit" value="Schedule" onclick=\'add_event("{item["uuid"]}");\'/>',
                    "",
                    item["name"],
                    dur,
                    f"{prev_play} ({p})",
                    f"{future_play} ({f})",
                ]
            )
    # Activity creation inputs are handled by the main UI now.
    headers = ["", "", "Title", "Duration", "Previous plays", "Future plays"]
    return HTMLResponse(_html_table(headers, rows))


@app.get("/VideoListJson")
def video_list_json(type: str = "video"):
    if type == "video":
        items_by_name, _ = dp.get_videos()
    else:
        items_by_name, _ = dp.get_activities()
    items = sorted(items_by_name.values(), key=lambda x: x["name"])
    return JSONResponse(items)


@app.get("/CurrentState")
def current_state():
    items = dp.get_all_items_by_name()
    schedule = dp.get_schedule()
    now = dp.current_time_ms()
    lines = [datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), "<br/>"]
    for e in schedule:
        item = items.get(e["name"])
        if not item:
            continue
        start = e["start_timestamp"]
        stop = start + item["duration"]
        if start < now < stop:
            lines.append(f"Currently playing: {e['name']}, {(stop - now)//1000} seconds left</html>")
            return HTMLResponse("".join(lines))
        if now < start and start - now < 30000:
            lines.append(f"Playing soon: {e['name']}, in {(start - now)//1000} seconds</html>")
            return HTMLResponse("".join(lines))
    lines.append("Currently happens nothing.\n</html>")
    return HTMLResponse("".join(lines))

@app.get("/CurrentStateJson")
def current_state_json():
    items = dp.get_all_items_by_name()
    schedule = dp.get_schedule()
    now = dp.current_time_ms()
    payload = {
        "now_ts": now,
        "status": "idle",
        "name": None,
        "seconds_left": None,
        "seconds_until": None,
        "start_ts": None,
        "stop_ts": None,
    }
    for e in schedule:
        item = items.get(e["name"])
        if not item:
            continue
        start = e["start_timestamp"]
        stop = start + item["duration"]
        if start < now < stop:
            payload.update({
                "status": "playing",
                "name": e["name"],
                "seconds_left": int((stop - now) / 1000),
                "start_ts": start,
                "stop_ts": stop,
            })
            return JSONResponse(payload)
        if now < start and start - now < 30000:
            payload.update({
                "status": "soon",
                "name": e["name"],
                "seconds_until": int((start - now) / 1000),
                "start_ts": start,
                "stop_ts": stop,
            })
            return JSONResponse(payload)
    return JSONResponse(payload)


@app.get("/ContestState")
def contest_state():
    contest_time = dp.get_contest_start()
    current_time = dp.current_time_ms()
    d = abs(contest_time - current_time)
    h = d // 1000 // 60 // 60
    m = d // 1000 // 60 % 60
    s = d // 1000 % 60
    contest_str = f"{h}:{m}:{s}"
    if contest_time < current_time:
        msg = f"Current contest time: {contest_str}"
    else:
        msg = f"Time before start: {contest_str}"
    html = f"<html>Start at: {datetime.utcfromtimestamp(contest_time/1000)}<br/>{msg}</html>"
    return HTMLResponse(html)

@app.get("/ContestStateJson")
def contest_state_json():
    contest_time = dp.get_contest_start()
    current_time = dp.current_time_ms()
    d = abs(contest_time - current_time)
    mode = "running" if contest_time < current_time else "before"
    return JSONResponse({
        "contest_start_ts": contest_time,
        "current_ts": current_time,
        "mode": mode,
        "delta_ms": d,
    })

@app.get("/OBSStatus.jsp")
def obs_status():
    try:
        status = heartbeat()
        return HTMLResponse(f"<html>Connected to OBS (Scene: {status.get('scene', 'unknown')})</html>")
    except Exception:
        return HTMLResponse("<html>Not connected to OBS</html>")


@app.post("/StartStreaming")
def start_stream():
    try:
        start_streaming()
        return JSONResponse({"ok": True})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/StopStreaming")
def stop_stream():
    try:
        stop_streaming()
        return JSONResponse({"ok": True})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/ApplyAudioMonitoring")
def apply_audio_monitoring_endpoint():
    try:
        result = apply_audio_monitoring()
        return JSONResponse({"ok": True, "applied": result.get("applied", []), "failed": result.get("failed", [])})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/StreamStatus")
def stream_status():
    try:
        return JSONResponse({"active": bool(get_stream_status())})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))



@app.get("/ScheduleGetJson")
def schedule_get_json():
    return JSONResponse(dp.get_schedule())


@app.get("/SettingsGet")
def settings_get():
    return JSONResponse(dp.get_config())


@app.post("/SettingsUpdate")
def settings_update(payload: dict):
    current = dp.get_config()
    current.update(payload)
    dp.write_config(current)
    return JSONResponse({"ok": True})


@app.post("/RefreshVideos")
def refresh_videos():
    dp.refresh_videos_if_needed(force=True, rebuild=True)
    ffprobe_path = dp.get_ffprobe_path()
    return JSONResponse({"ok": True, "ffprobe": bool(ffprobe_path), "ffprobe_path": ffprobe_path})


@app.post("/BulkSchedule")
def bulk_schedule(payload: dict):
    entries = payload.get("entries", [])
    mode = payload.get("mode", "skip")
    items = dp.get_all_items_by_name()
    schedule = dp.get_schedule()

    def stop_time(entry):
        item = items.get(entry["name"])
        duration = item["duration"] if item and item["duration"] > 0 else 60000
        return entry["start_timestamp"] + duration

    def overlaps(a_start, a_stop, b_start, b_stop):
        return a_start < b_stop and b_start < a_stop

    new_entries = []
    for raw in entries:
        if "name" not in raw or "start_timestamp" not in raw:
            continue
        new_entries.append({
            "uuid": raw.get("uuid") or str(uuid4()),
            "name": raw["name"],
            "start_timestamp": int(raw["start_timestamp"]),
        })

    if mode == "overwrite":
        filtered = []
        for existing in schedule:
            e_start = existing["start_timestamp"]
            e_stop = stop_time(existing)
            conflict = False
            for n in new_entries:
                n_start = n["start_timestamp"]
                n_stop = stop_time(n)
                if overlaps(e_start, e_stop, n_start, n_stop):
                    conflict = True
                    break
            if not conflict:
                filtered.append(existing)
        schedule = filtered

    if mode == "shift":
        adjusted = []
        for n in new_entries:
            n_start = n["start_timestamp"]
            n_stop = stop_time(n)
            while True:
                conflict = None
                for existing in schedule + adjusted:
                    e_start = existing["start_timestamp"]
                    e_stop = stop_time(existing)
                    if overlaps(n_start, n_stop, e_start, e_stop):
                        conflict = e_stop
                        break
                if conflict:
                    n_start = conflict
                    n_stop = n_start + (n_stop - n_start)
                    continue
                break
            adjusted.append({
                "uuid": n["uuid"],
                "name": n["name"],
                "start_timestamp": n_start,
            })
        new_entries = adjusted

    if mode == "skip":
        filtered_new = []
        for n in new_entries:
            n_start = n["start_timestamp"]
            n_stop = stop_time(n)
            conflict = False
            for existing in schedule:
                e_start = existing["start_timestamp"]
                e_stop = stop_time(existing)
                if overlaps(n_start, n_stop, e_start, e_stop):
                    conflict = True
                    break
            if not conflict:
                filtered_new.append(n)
        new_entries = filtered_new

    schedule.extend(new_entries)
    dp.write_schedule(schedule)
    return JSONResponse(dp.as_schedule_payload())


static_dir = Path(__file__).resolve().parent.parent / "obs-video-scheduler" / "WebContent"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

# Override data directory via env (for C:\scheduler)
import os
import data_provider as dp
custom_data = os.getenv("SCHEDULER_DATA")
if custom_data:
    dp.set_data_root(custom_data)
