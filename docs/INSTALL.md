## Overview
The scheduler runs plugin-free using obs-websocket (no Java/Tomcat, no custom OBS plugin). Keep OBS in normal mode (not Studio) with obs-websocket enabled.

## Requirements
- Windows
- OBS 28+ with obs-websocket enabled (Tools → WebSocket Server Settings)
- Python 3.10+ (for FastAPI backend)
- ffmpeg/ffprobe on PATH (recommended for media handling)
- Browser

## Install (Windows, Python)
1) Download `install-python.ps1` from the repo.
2) Run it in PowerShell (it prompts for the install folder; default is `C:\scheduler`).
3) Start OBS and enable obs-websocket (note the port/password).
4) Edit `run-python.bat` in your install folder for OBS host/port/password/scene/layer if needed.
5) Run `run-python.bat`.
6) Open http://localhost:8080/.

## Usage
1) Run OBS.
2) Run the Python API as above.
3) Open http://localhost:8080/. The UI polls `/CurrentState`, `/ContestState`, `/VideoList`, and `/ScheduleGet` from the Python service.
4) Schedule videos via the UI, drag to adjust, double-click to remove.

## Update (Windows, Python)
1) Download `update-python.ps1` from the repo.
2) Run it in PowerShell (choose GitHub download, local folder, or offline zip).
3) Start the scheduler again if it was running.

## Auto-start on Windows (optional)
If you want the scheduler to start at Windows login without showing a console window:
1) Copy `tools/start_scheduler.vbs.example` to `C:\scheduler\start_scheduler.vbs` (or your install folder).
2) Edit the `.vbs` file if your install directory is different.
3) Press `Win+R`, type `shell:startup`, and press Enter.
4) Move the `start_scheduler.vbs` file into the Startup folder.

This runs `run-python.bat` hidden and appends a simple log line to `C:\scheduler\log.txt`.

## Settings (config.json)
| Property | Default value | Description |
|-|-|-|
| server-video-dir | `C:/videos/` | Path where the scheduler reads media filenames |
| obs-video-dir | `C:/videos/` | Path OBS should load media from (usually same as above) |
| obs-host | `localhost` | Kept for compatibility (not used by websocket path) |
| scene-name | `Scene1` | Target scene in OBS |
| source-layer | `0` | Layer index for injected media |
| source-left-margin | `0` | Positioning (px) |
| source-top-margin | `0` | Positioning (px) |
| source-relative-width | `1` | Relative width (0-1) |
| source-relative-height | `1` | Relative height (0-1) |
| sources-to-mute | `[]` | Inputs to mute while playing |
| audio-monitor-sources | `""` | Audio inputs to set monitor mode |
| audio-monitor-prefix | `Scheduler:` | Audio input prefix to match |
| audio-monitor-mode | `monitor_and_output` | Audio monitor mode |
| idle-scene-enabled | `false` | Switch to idle scene when nothing plays |
| idle-scene-name | `Slides` | Idle scene name |
