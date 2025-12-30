import express from 'express';
import { OBSWebSocket } from 'obs-websocket-js';

const app = express();
app.use(express.json());

const obs = new OBSWebSocket();

const config = {
    url: process.env.OBS_WS_URL || 'ws://127.0.0.1:4455',
    password: process.env.OBS_WS_PASSWORD || '',
    sceneName: process.env.OBS_SCENE || 'Scene 1',
    defaultLayer: Number(process.env.OBS_LAYER || 1),
    sourcesToMute: (process.env.OBS_SOURCES_TO_MUTE || '').split(',').map(s => s.trim()).filter(Boolean)
};

async function ensureObsConnected() {
    if (obs._connected) {
        return;
    }
    await obs.connect(config.url, config.password);
}

async function muteConfiguredSources(mute) {
    for (const name of config.sourcesToMute) {
        await obs.call('SetInputMute', { inputName: name, inputMuted: mute });
    }
}

async function ensureMediaInput({ sceneName, sourceName, file, layer, widthPct, heightPct, leftPct, topPct }) {
    const targetScene = sceneName || config.sceneName;
    const transform = {
        positionX: leftPct ?? 0,
        positionY: topPct ?? 0,
        width: widthPct ?? 1,
        height: heightPct ?? 1
    };

    let sceneItemId;
    try {
        const { sceneItemId: existing } = await obs.call('GetSceneItemId', {
            sceneName: targetScene,
            sourceName: sourceName
        });
        sceneItemId = existing;
        await obs.call('SetInputSettings', {
            inputName: sourceName,
            inputSettings: { local_file: file },
            overlay: true
        });
        await obs.call('SetSceneItemEnabled', {
            sceneName: targetScene,
            sceneItemId,
            sceneItemEnabled: true
        });
    } catch (err) {
        const { sceneItemId: createdId } = await obs.call('CreateInput', {
            sceneName: targetScene,
            inputName: sourceName,
            inputKind: 'ffmpeg_source',
            inputSettings: { local_file: file },
            sceneItemEnabled: true
        });
        sceneItemId = createdId;
    }

    if (layer !== undefined && layer !== null) {
        await obs.call('SetSceneItemIndex', {
            sceneName: targetScene,
            sceneItemId,
            sceneItemIndex: layer
        });
    }

    await obs.call('SetSceneItemTransform', {
        sceneName: targetScene,
        sceneItemId,
        sceneItemTransform: transform
    });

    return sceneItemId;
}

app.post('/obs/play', async (req, res) => {
    const { file, sourceName, sceneName, layer, widthPct, heightPct, leftPct, topPct, restart } = req.body || {};

    if (!file || !sourceName) {
        return res.status(400).json({ error: 'file and sourceName are required' });
    }

    try {
        await ensureObsConnected();
        await muteConfiguredSources(true);
        await ensureMediaInput({
            sceneName,
            sourceName,
            file,
            layer: layer ?? config.defaultLayer,
            widthPct: widthPct ?? 1,
            heightPct: heightPct ?? 1,
            leftPct: leftPct ?? 0,
            topPct: topPct ?? 0
        });

        await obs.call('TriggerMediaInputAction', {
            inputName: sourceName,
            mediaAction: restart ? 'restart' : 'play'
        });

        return res.json({ ok: true });
    } catch (err) {
        console.error('play error', err);
        return res.status(500).json({ error: err.message || 'play failed' });
    }
});

app.post('/obs/stop', async (req, res) => {
    const { sourceName, sceneName, clear } = req.body || {};
    if (!sourceName) {
        return res.status(400).json({ error: 'sourceName is required' });
    }
    try {
        await ensureObsConnected();
        if (clear) {
            await obs.call('RemoveInput', { inputName: sourceName });
        } else {
            const { sceneItemId } = await obs.call('GetSceneItemId', {
                sceneName: sceneName || config.sceneName,
                sourceName
            });
            await obs.call('SetSceneItemEnabled', {
                sceneName: sceneName || config.sceneName,
                sceneItemId,
                sceneItemEnabled: false
            });
        }
        await muteConfiguredSources(false);
        return res.json({ ok: true });
    } catch (err) {
        console.error('stop error', err);
        return res.status(500).json({ error: err.message || 'stop failed' });
    }
});

app.post('/obs/mute', async (req, res) => {
    const { inputName, mute } = req.body || {};
    if (!inputName || mute === undefined) {
        return res.status(400).json({ error: 'inputName and mute are required' });
    }
    try {
        await ensureObsConnected();
        await obs.call('SetInputMute', { inputName, inputMuted: !!mute });
        return res.json({ ok: true });
    } catch (err) {
        return res.status(500).json({ error: err.message || 'mute failed' });
    }
});

app.get('/obs/heartbeat', async (_req, res) => {
    try {
        await ensureObsConnected();
        const { currentProgramSceneName } = await obs.call('GetCurrentProgramScene');
        return res.json({ ok: true, scene: currentProgramSceneName });
    } catch (err) {
        return res.status(500).json({ ok: false, error: err.message || 'heartbeat failed' });
    }
});

const port = process.env.PORT || 5050;
app.listen(port, () => {
    console.log(`obs-websocket-gateway listening on http://localhost:${port}`);
});
