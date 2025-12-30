# OBS Websocket Gateway (plugin-free path)

Small HTTP wrapper around `obs-websocket` so the scheduler can talk to OBS without the custom Java/Thrift plugin. This does not yet replace the Java scheduler logic, but gives you the OBS control surface you need to wire the existing endpoints over.

## Quick start
1) Install deps (no network? download offline packages first):
   ```bash
   cd obs-websocket-gateway
   npm install
   ```
2) In OBS, enable obs-websocket (Tools → WebSocket Server Settings). Note the port and password.
3) Run the gateway:
   ```bash
   OBS_WS_URL=ws://127.0.0.1:4455 \
   OBS_WS_PASSWORD=your_password \
   OBS_SCENE="Scene 1" \
   OBS_LAYER=1 \
   OBS_SOURCES_TO_MUTE="Mic/Aux,Desktop Audio" \
   npm start
   ```
4) Test the heartbeat:
   ```bash
   curl http://localhost:5050/obs/heartbeat
   ```

## Endpoints (mapped from OBSApi.java semantics)
- `POST /obs/play`
  - body: `{ file, sourceName, sceneName?, layer?, widthPct?, heightPct?, leftPct?, topPct?, restart? }`
  - Creates or updates an `ffmpeg_source`, positions it, mutes configured sources, and triggers play/restart.
- `POST /obs/stop`
  - body: `{ sourceName, sceneName?, clear? }`
  - Hides or removes the source and unmutes configured sources.
- `POST /obs/mute`
  - body: `{ inputName, mute }`
  - Direct mute/unmute.
- `GET /obs/heartbeat`
  - Quick connectivity check (returns current program scene).

## How to wire this into the scheduler
- Replace calls to `OBSApi.startPlayback/switchPlayback/endPlayback` with HTTP calls to `/obs/play` and `/obs/stop`. The fields line up with the values previously passed to `launchVideo(...)` (file path, scene, layer, transform).
- The Java servlets and schedule logic can stay intact while you swap the transport layer; once you are confident, you can port the servlets to Node/Express and retire Tomcat entirely.
- `sourcesToMute` is controlled via `OBS_SOURCES_TO_MUTE` env var (comma-separated).

## Notes
- Uses `obs-websocket-js` v5 API (OBS 28+). If you are on OBS 27, pin obs-websocket-js v4 and adjust calls.
- Transform units are expressed as percentages (0–1). If you prefer pixels, convert on the caller side before sending.
- The service is stateless; you can run/restart it independently of the scheduler UI.***
