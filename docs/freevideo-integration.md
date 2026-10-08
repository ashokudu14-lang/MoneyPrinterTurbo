# FreeVideo integration for the Telugu Mystery Factory

MoneyPrinterTurbo can now generate the five visual clips for the Telugu Mystery Shorts Factory automatically with [FlashML-org/FreeVideo](https://github.com/FlashML-org/FreeVideo).

The recommended architecture for the existing Render deployment is:

`MoneyPrinterTurbo on Render → FreeVideo worker on a GPU machine → five MP4 clips → MoneyPrinterTurbo final render`

Do not install the full FreeVideo model inside the normal Render Streamlit service unless that service has enough compatible GPU memory. Keep the web UI/controller lightweight and run generation on the GPU worker.

## Option A: remote GPU worker (recommended for the Render deployment)

### 1. Install FreeVideo on the GPU machine

Follow the FreeVideo project setup for Windows, Linux or an existing ComfyUI installation. Confirm that the FreeVideo CLI can generate a video before starting the worker.

The worker invokes the same command shape used by FreeVideo:

```bash
freevideo generate --prompt-file prompt.txt --out video.mp4 --width 768 --height 1344 --seconds 10
```

If your launcher is not on `PATH`, configure `FREEVIDEO_ROOT` or `FREEVIDEO_CLI` on the worker.

### 2. Start the MoneyPrinterTurbo worker API

From this repository on the GPU machine:

```bash
python tools/freevideo_worker.py
```

By default it listens on port `8765`.

Recommended worker environment variables:

```text
FREEVIDEO_ROOT=/path/to/FreeVideo
FREEVIDEO_API_TOKEN=replace-with-a-long-random-secret
FREEVIDEO_TIMEOUT_SECONDS=3600
FREEVIDEO_WORKER_PORT=8765
```

Instead of `FREEVIDEO_ROOT`, a custom command can be supplied with `FREEVIDEO_CLI`. This is useful on Windows when the launcher is a PowerShell script, for example:

```text
FREEVIDEO_CLI=powershell -ExecutionPolicy Bypass -File C:\AI\FreeVideo\freevideo.ps1
```

### 3. Expose the worker securely

The Render service must be able to reach the GPU worker over HTTPS. Use a private network, VPN/tunnel or a properly secured reverse proxy. Do not expose an unauthenticated generation endpoint to the public internet.

Set `FREEVIDEO_API_TOKEN` on both sides to the same secret.

### 4. Configure MoneyPrinterTurbo on Render

Set these environment variables on the MoneyPrinterTurbo service:

```text
FREEVIDEO_MODE=remote
FREEVIDEO_BASE_URL=https://your-gpu-worker.example.com
FREEVIDEO_API_TOKEN=the-same-worker-secret
FREEVIDEO_TIMEOUT_SECONDS=3600
```

After deployment, open **Telugu Mystery Factory**. The **FreeVideo (automatic)** option should show that the remote backend is ready.

## Option B: local mode

Use this when MoneyPrinterTurbo itself runs on the same GPU computer as FreeVideo.

Set:

```text
FREEVIDEO_MODE=local
FREEVIDEO_ROOT=/path/to/FreeVideo
FREEVIDEO_TIMEOUT_SECONDS=3600
```

Or provide an explicit launcher command:

```text
FREEVIDEO_MODE=local
FREEVIDEO_CLI=/path/to/freevideo
```

The factory then calls FreeVideo directly without HTTP.

## Worker API

The worker intentionally exposes only two endpoints:

- `GET /health` — confirms that the worker can see the configured FreeVideo launcher.
- `POST /generate` — accepts one prompt/seed/size/duration request and returns an MP4 file.

When `FREEVIDEO_API_TOKEN` is configured, both endpoints require:

```text
Authorization: Bearer <token>
```

## Default generation settings

The Telugu factory currently uses:

- Resolution: `768 × 1344`
- Aspect ratio: `9:16`
- Duration: `10 seconds` per scene
- Scenes: `5`
- Seeds: deterministic base seed plus scene index
- Audio: stripped/prepared before MoneyPrinterTurbo assembles the master Telugu audio track

The Google Flow path remains available as a fallback if FreeVideo is unavailable or a particular scene needs manual regeneration.

## Security and licensing

FreeVideo's code is Apache-2.0, while its model weights are governed separately by the MiniMax H3 Community License. Review the model license for your intended territory and monetized YouTube use before production publishing.

Keep `FREEVIDEO_API_TOKEN` secret. Do not commit tokens, tunnel credentials or private worker addresses to the repository.
