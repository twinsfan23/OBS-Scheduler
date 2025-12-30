## Python replacement backend (FastAPI)

This service provides the FastAPI backend and talks to OBS directly via obs-websocket. Endpoints mirror the original servlet paths so the existing frontend keeps working.

### Run
```bash
cd obs-scheduler-api
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on mac/linux
pip install -r requirements.txt

set OBS_HOST=127.0.0.1
set OBS_PORT=4455
set OBS_PASSWORD=your_password
set OBS_SCENE="Scene 1"
set OBS_LAYER=1
set OBS_SOURCES_TO_MUTE="Mic/Aux,Desktop Audio"
uvicorn app:app --reload --port 8080
```

Then open http://localhost:8080/index.html (static assets are mounted from `obs-video-scheduler/WebContent`).

### What’s implemented
- Schedule + item storage compatible with the original JSON files in `data/`.
- Same endpoints (`/ScheduleGet`, `/ScheduleList`, `/AddScheduleEntry`, `/RescheduleScheduleEntry`, `/RemoveScheduleEntry`, `/StartContest`, `/VideoList`, `/AddActivity`, `/CurrentState`, `/ContestState`, `/SaveSchedule`, `/LoadSchedule`).
- Background playback loop that reads the schedule and controls OBS directly via obs-websocket to play/stop sources at the right times.

### OBS control
- Uses obsws-python (OBS websocket v5). Configure host/port/password/scene/layer via env vars above.
- API access can be protected with `api-key` in `config.json` or `OBS_API_KEY` env var.

### Data layout
- Uses the same JSON files (`filelist.txt`, `alist.txt`, `schedule.json`, `timestamp`, `schedules/`, `config.json`). The installer creates these under your chosen data directory (default `C:\scheduler`).

### Next steps
- Confirm the data directory has the expected files and durations in milliseconds.
- Align disclaimer/transition logic if you rely on it (currently the Python loop plays raw media without disclaimer overlays).
