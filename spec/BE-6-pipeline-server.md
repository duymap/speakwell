# BE-6: Main Pipecat Pipeline Server

**File:** `server/bot.py`
**Port:** 7860
**Depends on:** BE-3 (STT service), BE-4 (TTS service), BE-5 (tutor prompt)
**Team:** Backend

---

## Objective

Build the main application server that:
1. Serves a FastAPI app on port 7860
2. Handles WebRTC signaling (SDP offer/answer) via SmallWebRTC
3. Creates a Pipecat pipeline for each connected client: audio in → STT → LLM → TTS → audio out
4. Supports voice interruptions (user can speak while the bot is talking)

This is the central orchestrator — it ties together all other backend components.

---

## Architecture

```
Browser (WebRTC)
    │
    ▼
FastAPI (port 7860)
    ├── POST /api/offer    → WebRTC SDP exchange
    │
    └── Per-connection Pipecat Pipeline:
        transport.input()      ← audio from browser mic
            → Qwen3STTService  → calls ASR server (port 8001)
            → OpenAILLMService → calls OpenAI GPT-4o API
            → Qwen3TTSService  → calls TTS server (port 8002)
        transport.output()     → audio back to browser
```

---

## Requirements

### 1. FastAPI Application

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="SpeakWell Pipeline Server")
```

### 2. WebRTC Signaling Endpoint

The frontend's `SmallWebRTCTransport` sends an SDP offer to connect. You handle it like this:

```python
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection

@app.post("/api/offer")
async def offer(request: Request):
    body = await request.json()
    connection = SmallWebRTCConnection()

    # Start the bot pipeline in a background task
    # The connection handles SDP exchange
    asyncio.create_task(run_bot(connection))

    # Return SDP answer to the browser
    answer = await connection.accept_offer(body)
    return JSONResponse(content=answer)
```

**Important:** Check the exact SmallWebRTC API. The connection setup may differ:
```bash
python -c "from pipecat.transports.smallwebrtc import connection; help(connection)"
```

Some versions use a different pattern:
```python
@app.post("/api/offer")
async def offer(request: Request):
    body = await request.json()
    connection = SmallWebRTCConnection()
    answer = await connection.offer(body.get("sdp"), body.get("type"))
    asyncio.create_task(run_bot(connection))
    return JSONResponse(content={"sdp": answer.sdp, "type": answer.type})
```

### 3. Pipeline Construction

```python
import asyncio
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.base_transport import TransportParams
from pipecat.services.openai.llm import OpenAILLMService

from services.qwen3_stt import Qwen3STTService
from services.qwen3_tts import Qwen3TTSService
from prompts import ENGLISH_TUTOR_PROMPT


async def run_bot(connection: SmallWebRTCConnection):
    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )

    stt = Qwen3STTService(
        api_url="http://localhost:8001/v1/chat/completions",
    )

    llm = OpenAILLMService(
        model="gpt-4o",
        system_instruction=ENGLISH_TUTOR_PROMPT,
    )

    tts = Qwen3TTSService(
        api_url="http://localhost:8002/tts",
        speaker="Ryan",
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        llm,
        tts,
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        PipelineParams(allow_interruptions=True),
    )

    # Kick off the first LLM turn (greeting) when client connects
    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        from pipecat.frames.frames import LLMMessagesFrame
        # Send an empty user message to trigger the greeting
        await task.queue_frames([LLMMessagesFrame(
            messages=[{"role": "user", "content": "Hello!"}]
        )])

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)
```

### 4. OpenAI API Key

The `OpenAILLMService` needs the `OPENAI_API_KEY` environment variable. Handle this via:

```bash
export OPENAI_API_KEY=sk-...
```

Do NOT hardcode the key. The `OpenAILLMService` reads it from the environment automatically.

### 5. VAD (Voice Activity Detection)

Pipecat needs VAD to know when the user starts/stops speaking. Add Silero VAD to the pipeline:

```python
from pipecat.audio.vad.silero import SileroVADAnalyzer

transport = SmallWebRTCTransport(
    webrtc_connection=connection,
    params=TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    ),
)
```

This enables:
- Detecting when the user starts speaking → pause TTS output (interruption)
- Detecting when the user stops speaking → send accumulated audio to STT

### 6. Interruption Support

`PipelineParams(allow_interruptions=True)` enables:
- When the user speaks while TTS is playing, Pipecat cancels the current TTS and processes the user's new input
- This creates a natural conversation flow where the user can interject

### 7. Configuration via Environment Variables

Make server URLs configurable:

```python
import os

ASR_URL = os.getenv("ASR_URL", "http://localhost:8001/v1/chat/completions")
TTS_URL = os.getenv("TTS_URL", "http://localhost:8002/tts")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
TTS_SPEAKER = os.getenv("TTS_SPEAKER", "Ryan")
PORT = int(os.getenv("PORT", "7860"))
```

---

## Important Notes

### Pipecat Version Compatibility

The SmallWebRTC API is relatively new in Pipecat. Key things to verify:

1. **Import paths** — may be under `pipecat.transports.smallwebrtc` or `pipecat.transports.network`
2. **SDP exchange** — the exact method for handling offer/answer varies. Check examples in the Pipecat repo: https://github.com/pipecat-ai/pipecat/tree/main/examples
3. **`LLMMessagesFrame` vs `LLMRunFrame`** — different versions use different frame types to trigger the initial LLM response
4. **`system_instruction` vs `system_prompt`** — parameter name for the LLM system prompt

### Concurrency

Each WebRTC connection gets its own pipeline (its own `run_bot` coroutine). Multiple users can connect simultaneously. Each pipeline runs independently.

### Graceful Shutdown

Handle cleanup when the client disconnects:
- Cancel the pipeline task
- Close any open HTTP sessions (handled by BE-3 and BE-4's `stop()` methods)
- Release transport resources

### Error Recovery

If the ASR or TTS server goes down mid-conversation:
- The pipeline should not crash
- The STT/TTS services (BE-3/BE-4) already handle errors gracefully
- Consider adding a health check on startup that verifies ASR and TTS servers are reachable

---

## Full Implementation Skeleton

```python
import os
import asyncio

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.base_transport import TransportParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.audio.vad.silero import SileroVADAnalyzer

from services.qwen3_stt import Qwen3STTService
from services.qwen3_tts import Qwen3TTSService
from prompts import ENGLISH_TUTOR_PROMPT

# Configuration
ASR_URL = os.getenv("ASR_URL", "http://localhost:8001/v1/chat/completions")
TTS_URL = os.getenv("TTS_URL", "http://localhost:8002/tts")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
TTS_SPEAKER = os.getenv("TTS_SPEAKER", "Ryan")
PORT = int(os.getenv("PORT", "7860"))

app = FastAPI(title="SpeakWell Pipeline Server")


@app.post("/api/offer")
async def offer(request: Request):
    body = await request.json()
    connection = SmallWebRTCConnection()
    asyncio.create_task(run_bot(connection))
    answer = await connection.accept_offer(body)
    return JSONResponse(content=answer)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def run_bot(connection: SmallWebRTCConnection):
    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    stt = Qwen3STTService(api_url=ASR_URL)

    llm = OpenAILLMService(
        model=LLM_MODEL,
        system_instruction=ENGLISH_TUTOR_PROMPT,
    )

    tts = Qwen3TTSService(
        api_url=TTS_URL,
        speaker=TTS_SPEAKER,
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        llm,
        tts,
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        PipelineParams(allow_interruptions=True),
    )

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        from pipecat.frames.frames import LLMMessagesFrame
        await task.queue_frames([LLMMessagesFrame(
            messages=[{"role": "user", "content": "Hello!"}]
        )])

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

---

## How to Run

```bash
# Make sure these are running first:
# - ASR server on port 8001 (already deployed)
# - TTS server on port 8002 (already deployed)
# - OPENAI_API_KEY is set

export OPENAI_API_KEY=sk-...

cd server
uvicorn bot:app --host 0.0.0.0 --port 7860

# Or directly:
python bot.py
```

---

## Testing

### Health Check

```bash
curl http://localhost:7860/api/health
# → {"status": "ok"}
```

### End-to-End Test

This requires the frontend (FE tasks) or a WebRTC test client. For backend-only testing:

1. Verify the server starts without import errors
2. Verify `/api/health` responds
3. Verify `/api/offer` accepts a POST (even with dummy SDP, it should not crash)
4. Full E2E testing happens in INT-1

### Smoke Test Script

```python
"""Verify the pipeline server starts and all imports work."""
import requests

# Health check
resp = requests.get("http://localhost:7860/api/health")
assert resp.status_code == 200
print("Health check: OK")

# Offer endpoint exists (will fail with bad SDP, but shouldn't 404)
resp = requests.post("http://localhost:7860/api/offer", json={"sdp": "test", "type": "offer"})
assert resp.status_code != 404, "Offer endpoint not found"
print(f"Offer endpoint: returned {resp.status_code} (expected non-404)")
```

---

## Dependencies

```
pipecat-ai[smallwebrtc,openai,silero]
fastapi
uvicorn
```

Plus the custom services from BE-3 and BE-4.

---

## Acceptance Criteria

- [ ] Server starts on port 7860 without errors
- [ ] `/api/health` returns 200
- [ ] `/api/offer` accepts POST requests
- [ ] Pipeline is correctly wired: input → STT → LLM → TTS → output
- [ ] VAD is enabled (Silero)
- [ ] Interruptions are enabled
- [ ] Bot sends initial greeting when client connects
- [ ] Pipeline cleans up when client disconnects
- [ ] Server URLs are configurable via environment variables
- [ ] Works with real WebRTC connection (tested in INT-1)
