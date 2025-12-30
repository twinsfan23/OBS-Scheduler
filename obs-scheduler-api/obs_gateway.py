import os
import time
from typing import List, Optional, Dict

from obsws_python import ReqClient

_client: Optional[ReqClient] = None
_conn_settings: Dict[str, str] = {}


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _get_config():
    try:
        from data_provider import get_config
        return get_config()
    except Exception:
        return {}


def _resolve_settings() -> Dict[str, str]:
    cfg = _get_config()
    settings = {
        "host": os.getenv("OBS_HOST") or cfg.get("obs-host", "127.0.0.1"),
        "port": os.getenv("OBS_PORT") or cfg.get("obs-port", "4455"),
        "password": os.getenv("OBS_PASSWORD") or cfg.get("obs-password", ""),
        "scene": os.getenv("OBS_SCENE") or cfg.get("scene-name", "Scene 1"),
        "idle_scene_enabled": os.getenv("OBS_IDLE_SCENE_ENABLED") or cfg.get("idle-scene-enabled", False),
        "idle_scene_name": os.getenv("OBS_IDLE_SCENE_NAME") or cfg.get("idle-scene-name", "Slides"),
        "layer": os.getenv("OBS_LAYER") or cfg.get("source-layer", "1"),
        "mute_sources": os.getenv("OBS_SOURCES_TO_MUTE") or ",".join(cfg.get("sources-to-mute", [])),
        "left_margin": os.getenv("OBS_LEFT_MARGIN") or cfg.get("source-left-margin", 0),
        "top_margin": os.getenv("OBS_TOP_MARGIN") or cfg.get("source-top-margin", 0),
        "relative_width": os.getenv("OBS_REL_WIDTH") or cfg.get("source-relative-width", 1),
        "relative_height": os.getenv("OBS_REL_HEIGHT") or cfg.get("source-relative-height", 1),
        "audio_monitor_sources": os.getenv("OBS_AUDIO_MONITOR_SOURCES") or cfg.get("audio-monitor-sources", ""),
        "audio_monitor_prefix": os.getenv("OBS_AUDIO_MONITOR_PREFIX") or cfg.get("audio-monitor-prefix", "Scheduler:"),
        "audio_monitor_mode": os.getenv("OBS_AUDIO_MONITOR_MODE") or cfg.get("audio-monitor-mode", "monitor_and_output"),
    }
    return settings


def _ensure_client() -> ReqClient:
    global _client
    global _conn_settings
    settings = _resolve_settings()
    if _client is not None:
        try:
            _client.get_version()
            if settings != _conn_settings:
                _client = None
            else:
                return _client
        except Exception:
            _client = None
    _conn_settings = settings
    _client = ReqClient(
        host=settings["host"],
        port=int(settings["port"]),
        password=settings["password"],
        timeout=3
    )
    return _client


def heartbeat():
    client = _ensure_client()
    res = client.get_current_program_scene()
    _apply_audio_monitoring(client, _resolve_settings())
    return {"ok": True, "scene": res.current_program_scene_name}


def get_stream_status() -> bool:
    client = _ensure_client()
    if hasattr(client, "get_stream_status"):
        res = client.get_stream_status()
        return bool(getattr(res, "output_active", False) or getattr(res, "outputActive", False))
    if hasattr(client, "call"):
        res = client.call("GetStreamStatus", {})
        return bool(res.get("outputActive"))
    return False


def get_program_screenshot(width: int = 480, height: int = 270) -> str | None:
    client = _ensure_client()
    scene = heartbeat().get("scene")
    if not scene:
        return None
    try:
        res = client.get_source_screenshot(
            source_name=scene,
            image_format="png",
            image_width=width,
            image_height=height,
            image_compression_quality=80,
        )
        image_data = getattr(res, "image_data", None) or getattr(res, "imageData", None)
        if image_data:
            return image_data
    except Exception:
        pass
    return None


def start_streaming() -> None:
    client = _ensure_client()
    if hasattr(client, "start_stream"):
        client.start_stream()
        return
    if hasattr(client, "call"):
        client.call("StartStream", {})
        return
    if hasattr(client, "send"):
        client.send("StartStream", {})


def stop_streaming() -> None:
    client = _ensure_client()
    if hasattr(client, "stop_stream"):
        client.stop_stream()
        return
    if hasattr(client, "call"):
        client.call("StopStream", {})
        return
    if hasattr(client, "send"):
        client.send("StopStream", {})


def set_current_scene(scene_name: str) -> None:
    client = _ensure_client()
    if hasattr(client, "set_current_program_scene"):
        client.set_current_program_scene(scene_name)
        return
    if hasattr(client, "call"):
        client.call("SetCurrentProgramScene", {"sceneName": scene_name})
        return
    if hasattr(client, "send"):
        client.send("SetCurrentProgramScene", {"sceneName": scene_name})


def _mute_sources(mute: bool) -> None:
    client = _ensure_client()
    settings = _resolve_settings()
    sources = [s.strip() for s in settings.get("mute_sources", "").split(",") if s.strip()]
    for name in sources:
        client.set_input_mute(name, mute)


def _apply_audio_monitoring(client: ReqClient, settings: Dict[str, str]) -> Dict[str, list]:
    raw_sources = settings.get("audio_monitor_sources", "")
    source_entries = [s.strip() for s in raw_sources.split(",") if s.strip()]
    sources = []
    prefixes = []
    for entry in source_entries:
        if entry.endswith(":"):
            prefixes.append(entry)
        else:
            sources.append(entry)
    prefix = (settings.get("audio_monitor_prefix") or "").strip()
    if prefix:
        prefixes.append(prefix)
    if not sources and not prefixes:
        return {"applied": [], "failed": []}
    mode_key = (settings.get("audio_monitor_mode") or "monitor_and_output").lower()
    mode_map = {
        "monitor_and_output": ["OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT"],
        "monitor_only": ["OBS_MONITORING_TYPE_MONITOR_ONLY"],
        "monitor_off": ["OBS_MONITORING_TYPE_MONITOR_OFF"],
    }
    modes = mode_map.get(mode_key, mode_map["monitor_and_output"])
    applied = []
    failed = []
    targets = []
    if sources:
        targets.extend([(name, False) for name in sources])
    if prefixes:
        try:
            inputs = client.get_input_list()
            for item in inputs.inputs:
                name = getattr(item, "input_name", None) or getattr(item, "inputName", None)
                if not name:
                    continue
                for prefix_value in prefixes:
                    if name.startswith(prefix_value):
                        targets.append((name, True))
                        break
        except Exception:
            pass
    if not targets:
        return {"applied": [], "failed": []}
    seen = set()
    for name, _ in targets:
        if name in seen:
            continue
        seen.add(name)
        updated = False
        for mode in modes:
            try:
                if hasattr(client, "set_input_audio_monitor_type"):
                    client.set_input_audio_monitor_type(name, mode)
                    updated = True
                    break
            except Exception:
                pass
            try:
                if hasattr(client, "send"):
                    client.send("SetInputAudioMonitorType", {"inputName": name, "monitorType": mode})
                    updated = True
                    break
            except Exception:
                pass
            try:
                if hasattr(client, "call"):
                    client.call("SetInputAudioMonitorType", {"inputName": name, "monitorType": mode})
                    updated = True
                    break
            except Exception:
                pass
        if updated:
            applied.append(name)
        else:
            failed.append(name)
            print(f"Audio monitoring update failed for source '{name}'. Check the input name.")
    return {"applied": applied, "failed": failed}


def _set_audio_monitoring_for_input(client: ReqClient, input_name: str, settings: Dict[str, str]) -> bool:
    mode_key = (settings.get("audio_monitor_mode") or "monitor_and_output").lower()
    mode_map = {
        "monitor_and_output": "OBS_MONITORING_TYPE_MONITOR_AND_OUTPUT",
        "monitor_only": "OBS_MONITORING_TYPE_MONITOR_ONLY",
        "monitor_off": "OBS_MONITORING_TYPE_MONITOR_OFF",
    }
    mode = mode_map.get(mode_key, mode_map["monitor_and_output"])
    try:
        if hasattr(client, "set_input_audio_monitor_type"):
            client.set_input_audio_monitor_type(input_name, mode)
            return True
    except Exception:
        pass
    try:
        if hasattr(client, "send"):
            client.send("SetInputAudioMonitorType", {"inputName": input_name, "monitorType": mode})
            return True
    except Exception:
        pass
    try:
        if hasattr(client, "call"):
            client.call("SetInputAudioMonitorType", {"inputName": input_name, "monitorType": mode})
            return True
    except Exception:
        pass
    print(f"Audio monitoring update failed for source '{input_name}'. Check the exact input name.")
    return False


def _ensure_media_input(client: ReqClient, source_name: str, file_path: str, layer: int) -> int:
    settings = _resolve_settings()
    scene_name = settings["scene"]
    scene_item_id = None
    try:
        created = client.create_input(
            sceneName=scene_name,
            inputName=source_name,
            inputKind="ffmpeg_source",
            inputSettings={"local_file": file_path},
            sceneItemEnabled=True,
        )
        scene_item_id = created.scene_item_id
    except Exception:
        resp = client.get_scene_item_id(scene_name, source_name)
        scene_item_id = resp.scene_item_id
        client.set_input_settings(source_name, {"local_file": file_path}, True)
        client.set_scene_item_enabled(scene_name, scene_item_id, True)

    if layer is not None:
        client.set_scene_item_index(scene_name, scene_item_id, layer)
    return scene_item_id


def _apply_source_dimensions(client: ReqClient, scene_name: str, scene_item_id: int, settings: Dict[str, str]) -> None:
    try:
        video_settings = client.get_video_settings()
        base_width = getattr(video_settings, "base_width", None) or getattr(video_settings, "baseWidth", None)
        base_height = getattr(video_settings, "base_height", None) or getattr(video_settings, "baseHeight", None)
        if not base_width or not base_height:
            return
        left_margin = float(settings.get("left_margin", 0) or 0)
        top_margin = float(settings.get("top_margin", 0) or 0)
        rel_width = float(settings.get("relative_width", 1) or 1)
        rel_height = float(settings.get("relative_height", 1) or 1)
        if rel_width <= 0:
            rel_width = 1
        if rel_height <= 0:
            rel_height = 1
        bounds_width = base_width * rel_width
        bounds_height = base_height * rel_height
        transform = {
            "positionX": left_margin,
            "positionY": top_margin,
            "rotation": 0,
            "scaleX": 1.0,
            "scaleY": 1.0,
            "cropLeft": 0,
            "cropTop": 0,
            "cropRight": 0,
            "cropBottom": 0,
            "boundsType": "OBS_BOUNDS_STRETCH",
            "boundsWidth": bounds_width,
            "boundsHeight": bounds_height,
            "boundsAlignment": 0,
        }
        client.set_scene_item_transform(scene_name, scene_item_id, transform)
    except Exception:
        return


def _restart_media(client: ReqClient, scene_name: str, scene_item_id: int, source_name: str, file_path: str) -> None:
    try:
        client.set_scene_item_enabled(scene_name, scene_item_id, False)
        time.sleep(0.1)
        client.set_input_settings(source_name, {"local_file": file_path}, True)
        client.set_scene_item_enabled(scene_name, scene_item_id, True)
    except Exception:
        return


def play(file_path: str, source_name: str, layer: int | None = None):
    client = _ensure_client()
    _mute_sources(True)
    settings = _resolve_settings()
    scene_item_id = _ensure_media_input(
        client,
        source_name=source_name,
        file_path=file_path,
        layer=layer if layer is not None else int(settings["layer"]),
    )
    _apply_audio_monitoring(client, settings)
    _set_audio_monitoring_for_input(client, source_name, settings)
    _apply_source_dimensions(client, settings["scene"], scene_item_id, settings)
    _restart_media(client, settings["scene"], scene_item_id, source_name, file_path)
    _set_audio_monitoring_for_input(client, source_name, settings)
    return {"ok": True, "sceneItemId": scene_item_id}


def stop(source_name: str, clear: bool = False):
    client = _ensure_client()
    settings = _resolve_settings()
    if clear:
        client.remove_input(source_name)
    else:
        try:
            resp = client.get_scene_item_id(settings["scene"], source_name)
            client.set_scene_item_enabled(settings["scene"], resp.scene_item_id, False)
        except Exception:
            pass
    _mute_sources(False)
    return {"ok": True}


def apply_audio_monitoring() -> Dict[str, list]:
    client = _ensure_client()
    settings = _resolve_settings()
    return _apply_audio_monitoring(client, settings)
