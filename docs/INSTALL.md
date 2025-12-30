## Overview
The scheduler can now run plugin-free using obs-websocket (no Java/Tomcat, no custom OBS plugin). Keep OBS in normal mode (not Studio) with obs-websocket enabled.

## Requirements
- Windows
- OBS 28+ with obs-websocket enabled (Tools → WebSocket Server Settings)
- Python 3.10+ (for FastAPI backend)
- ffmpeg on PATH (recommended for media handling)
- Browser

## Install (plugin-free path, all Python)
1) Clone or unzip the repo to a folder, e.g. `C:\obs-video-scheduler-master`.
2) Prepare `data/` (copy from your existing install if you have one):
   - `data/filelist.txt` (JSON array of videos)
   - `data/alist.txt` (JSON array of activities)
   - `data/schedule.json` (JSON array; can be empty `[]`)
   - `data/timestamp` (epoch ms for contest start; can be current time)
   - `data/schedules/` directory (for saved schedules)
   - `data/config.json` (scene, layer, video dirs; see Settings below)
3) Start OBS and enable obs-websocket (note the port/password).
4) Start Scheduler API + UI (Python):
   ```powershell
   cd obs-scheduler-api
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   $env:OBS_HOST="127.0.0.1"
   $env:OBS_PORT="4455"
   $env:OBS_PASSWORD="your_password"
   $env:OBS_SCENE="Scene 1"
   $env:OBS_LAYER="1"
   $env:OBS_SOURCES_TO_MUTE="Mic/Aux,Desktop Audio"
   uvicorn app:app --port 8080
   ```
5) Open http://localhost:8080/index.html. The existing UI should function against the new Python backend.

## Usage
1) Run OBS.
2) Run the Python API as above.
3) Open http://localhost:8080/. The UI polls `/CurrentState`, `/ContestState`, `/VideoList`, and `/ScheduleGet` from the Python service.
4) Schedule videos via the UI, drag to adjust, double-click to remove, use “Start now” or reschedule time to set contest start. `/comm` still shows upcoming content.

## Settings (config.json)
| Property | Default value | Description |
|-|-|-|
| server-video-dir | `C:/videos/` | Path where the scheduler reads media filenames |
| obs-video-dir | `C:/videos/` | Path OBS should load media from (usually same as above) |
| obs-host | `localhost` | Kept for compatibility (not used by websocket path) |
| scene-name | `Scene1` | Target scene in OBS |
| source-layer | `0` | Layer index for injected media |
| video-top-margin | `0` | Positioning (px or percent as used by UI) |
| video-left-margin | `0` | Positioning |
| video-width | `100` | Percent |
| video-height | `100` | Percent |
| sources-to-mute | `[]` | Inputs to mute while playing |
| disclaimer-file-name | *(unused here)* | Ignored if empty |
| disclaimer-transition-time | *(unused here)* | Ignored if empty |

## Legacy install (Java/Tomcat + Thrift plugin)
Still in the repo if you need it; requires JDK/JRE, Tomcat, and obs-thrift-api.dll. Prefer the plugin-free path above for new setups.***
