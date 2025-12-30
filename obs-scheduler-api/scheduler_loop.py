import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from data_provider import (
    get_all_items_by_name,
    get_schedule,
    get_config,
    current_time_ms,
)
from pathlib import Path
from obs_gateway import play, stop, set_current_scene


def _now_ms() -> int:
    return current_time_ms()


class PlaybackLoop:
    def __init__(self):
        self.running = False
        self.current_uuid: Optional[str] = None
        self.active_scene: Optional[str] = None

    async def start(self):
        if self.running:
            return
        self.running = True
        asyncio.create_task(self._loop())

    async def _loop(self):
        while self.running:
            try:
                await self.tick()
            except Exception as exc:
                print("Playback loop error:", exc)
            await asyncio.sleep(1)

    async def tick(self):
        schedule = sorted(get_schedule(), key=lambda e: e["start_timestamp"])
        items = get_all_items_by_name()
        now = _now_ms()
        config = get_config()
        media_root = Path(config.get("obs-video-dir", config.get("server-video-dir", ".")))
        idle_enabled = str(config.get("idle-scene-enabled", "")).strip().lower() in ("1", "true", "yes", "on")
        idle_scene = config.get("idle-scene-name", "Slides")
        video_scene = config.get("scene-name", "Scene 1")
        found_current = False
        for idx, entry in enumerate(schedule):
            item = items.get(entry["name"])
            if not item:
                continue
            start = entry["start_timestamp"]
            stop_ts = start + item["duration"]
            has_next = idx < len(schedule) - 1 and stop_ts == schedule[idx + 1]["start_timestamp"]
            media_path = str(media_root / entry["name"])
            if self.current_uuid == entry["uuid"]:
                found_current = True

            if start <= now < stop_ts and self.current_uuid != entry["uuid"]:
                source_name = f"Scheduler: {entry['name']} [{entry['uuid']}]"
                if idle_enabled and self.active_scene != video_scene:
                    await asyncio.to_thread(set_current_scene, video_scene)
                    self.active_scene = video_scene
                await asyncio.to_thread(play, media_path, source_name, layer=None)
                self.current_uuid = entry["uuid"]
                return

            if self.current_uuid == entry["uuid"] and now >= stop_ts:
                source_name = f"Scheduler: {entry['name']} [{entry['uuid']}]"
                await asyncio.to_thread(stop, source_name, clear=not has_next)
                self.current_uuid = None
                return

        if self.current_uuid is not None and not found_current:
            self.current_uuid = None

        if idle_enabled and self.current_uuid is None and self.active_scene != idle_scene:
            await asyncio.to_thread(set_current_scene, idle_scene)
            self.active_scene = idle_scene

    def stop(self):
        self.running = False
