# Plan: English Learning Voice AI Web App with Pipecat

## Context

Build a web application where users practice English conversation with an AI tutor via voice. The AI speaks and listens in real-time, and a transcript is shown on screen. The user runs STT and TTS inference locally on GPU, so we need custom Pipecat service integrations.

---

## Technology Choices

| Component | Technology | Details |
|-----------|-----------|---------|
| **LLM** | OpenAI GPT-4o | Cloud API, conversational English tutor persona |
| **STT** | [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) | Local GPU server. Model: `Qwen/Qwen3-ASR-1.7B`. Has built-in vLLM server with OpenAI-compatible API |
| **TTS** | [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Local GPU server. Model: `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`. Output: 12kHz sample rate, numpy waveform |
| **Transport** | Pipecat SmallWebRTC | Browser ↔ server low-latency audio via WebRTC |
| **Backend** | FastAPI + Pipecat | Pipeline orchestration |
| **Frontend** | React + Vite + Pipecat React SDK | Voice UI with transcript |

---

## Qwen3-ASR Details

- **Install**: `pip install -U qwen-asr[vllm]`
- **Server mode** (OpenAI-compatible API):
  ```bash
  qwen-asr-serve Qwen/Qwen3-ASR-1.7B \
    --gpu-memory-utilization 0.8 \
    --host 0.0.0.0 \
    --port 8001
  ```
- **API endpoint**: `POST http://localhost:8001/v1/chat/completions`
- **Request format** (OpenAI-compatible):
  ```json
  {
    "messages": [{
      "role": "user",
      "content": [{
        "type": "audio_url",
        "audio_url": { "url": "data:audio/wav;base64,<base64_audio>" }
      }]
    }]
  }
  ```
- **Response**: `response.json()['choices'][0]['message']['content']` → parse with `qwen_asr.parse_asr_output(content)` → `(language, text)`
- **Supports**: 52 languages, auto language detection, streaming (vLLM only)
- **Audio input**: WAV files, URLs, base64, numpy arrays

## Qwen3-TTS Details

- **Install**: `pip install -U qwen-tts`
- **No built-in server** — we need to wrap it in a FastAPI endpoint ourselves
- **Python API**:
  ```python
  from qwen_tts import Qwen3TTSModel
  model = Qwen3TTSModel.from_pretrained(
      "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
      device_map="cuda:0", dtype=torch.bfloat16,
      attn_implementation="flash_attention_2",
  )
  wavs, sr = model.generate_custom_voice(
      text="Hello!", language="English", speaker="Ryan"
  )
  # wavs[0] = numpy array, sr = 12000
  ```
- **Output**: numpy waveform at **12kHz** sample rate
- **Preset voices**: Ryan, Vivian, etc. (use `model.get_supported_speakers()`)
- **Features**: streaming (97ms latency), emotion/style control via `instruct` param
- **We will build**: a thin FastAPI wrapper (`server/tts_server.py`) to expose it as HTTP API

---

## Architecture Overview

```
┌─────────────────────────────────┐
│  Frontend (React + Vite)        │
│  - Mic capture & audio playback │
│  - Live transcript display      │
│  - Connect/disconnect controls  │
│  └──── WebRTC (SmallWebRTC) ────┼──┐
└─────────────────────────────────┘  │
                                     │
┌────────────────────────────────────┼───────────────────────┐
│  Backend (FastAPI + Pipecat)       │                       │
│  Port 7860                         ▼                       │
│  ┌─────────────────────────────────────────────────┐      │
│  │ Pipeline:                                        │      │
│  │  transport.input()                               │      │
│  │    → Qwen3STTService → base64 audio to ASR API   │      │
│  │      → OpenAI GPT-4o (English tutor)             │      │
│  │        → Qwen3TTSService → text to TTS API       │      │
│  │          → transport.output()                     │      │
│  └─────────────────────────────────────────────────┘      │
│                                                            │
└──────────────┬──────────────────────────┬─────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────────┐ ┌──────────────────────────┐
│  Qwen3-ASR Server        │ │  Qwen3-TTS Server        │
│  Port 8001               │ │  Port 8002               │
│  qwen-asr-serve (vLLM)   │ │  Custom FastAPI wrapper   │
│  OpenAI-compatible API    │ │  Returns raw PCM audio    │
│  GPU: cuda:0              │ │  GPU: cuda:1 (or shared)  │
└──────────────────────────┘ └──────────────────────────┘
```

---

## Project Structure

```
speakwell/
├── server/
│   ├── bot.py                  # Main Pipecat pipeline + FastAPI app (port 7860)
│   ├── services/
│   │   ├── qwen3_stt.py        # Pipecat STTService subclass → Qwen3-ASR API
│   │   └── qwen3_tts.py        # Pipecat TTSService subclass → Qwen3-TTS API
│   ├── prompts.py              # System prompt for English tutor persona
│   └── requirements.txt
├── client/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx             # PipecatClientProvider + PipecatClientAudio
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx   # Transcript display + connect/disconnect
│   │   │   └── AudioIndicator.tsx  # Visual speaking/listening state
│   │   └── main.tsx
│   └── vite.config.ts          # Proxy /api → backend:7860
└── PLAN.md
```

---

## Pre-existing Infrastructure

The following servers are already deployed and running — no setup tasks needed:

| Service | Endpoint | Notes |
|---------|----------|-------|
| Qwen3-ASR | `POST http://localhost:8001/v1/chat/completions` | OpenAI-compatible API, base64 WAV input |
| Qwen3-TTS | `POST http://localhost:8002/tts` | Returns raw PCM int16, 12kHz, `X-Sample-Rate` header |

---

## Step-by-Step Implementation

### Step 1: Custom STT Service (`server/services/qwen3_stt.py`)

Calls the Qwen3-ASR vLLM server (OpenAI-compatible API) with base64-encoded audio:

```python
import base64
import aiohttp
from pipecat.services.stt_service import STTService
from pipecat.frames.frames import TranscriptionFrame

class Qwen3STTService(STTService):
    def __init__(self, api_url: str = "http://localhost:8001/v1/chat/completions", **kwargs):
        super().__init__(**kwargs)
        self._api_url = api_url

    async def run_stt(self, audio: bytes):
        audio_b64 = base64.b64encode(audio).decode()
        payload = {
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "audio_url",
                    "audio_url": {"url": f"data:audio/wav;base64,{audio_b64}"}
                }]
            }]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self._api_url, json=payload) as resp:
                result = await resp.json()
                content = result["choices"][0]["message"]["content"]
                # Parse "language: English\ntext: Hello world" format
                text = self._parse_asr_output(content)
                if text:
                    yield TranscriptionFrame(text=text, user_id="user", timestamp="")

    def _parse_asr_output(self, content: str) -> str:
        # Qwen3-ASR returns "<language>\n<text>" format
        lines = content.strip().split("\n", 1)
        return lines[-1].strip() if lines else ""
```

### Step 2: Custom TTS Service (`server/services/qwen3_tts.py`)

Calls our Qwen3-TTS wrapper server:

```python
import aiohttp
from pipecat.services.tts_service import TTSService
from pipecat.frames.frames import TTSAudioRawFrame

class Qwen3TTSService(TTSService):
    def __init__(self, api_url: str = "http://localhost:8002/tts",
                 speaker: str = "Ryan", **kwargs):
        super().__init__(sample_rate=12000, **kwargs)  # Qwen3-TTS outputs 12kHz
        self._api_url = api_url
        self._speaker = speaker

    async def run_tts(self, text: str, context_id: str):
        async with aiohttp.ClientSession() as session:
            async with session.post(self._api_url, json={
                "text": text,
                "language": "English",
                "speaker": self._speaker,
            }) as resp:
                audio_bytes = await resp.read()
                yield TTSAudioRawFrame(
                    audio=audio_bytes,
                    sample_rate=12000,
                    num_channels=1,
                    context_id=context_id,
                )
```

### Step 3: Pipeline & Server (`server/bot.py`)

```python
import uvicorn
from fastapi import FastAPI
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.base_transport import TransportParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.frames.frames import LLMRunFrame

from services.qwen3_stt import Qwen3STTService
from services.qwen3_tts import Qwen3TTSService
from prompts import ENGLISH_TUTOR_PROMPT

app = FastAPI()

@app.post("/api/offer")
async def offer(request):
    ...  # SmallWebRTC SDP offer/answer

async def run_bot(webrtc_connection):
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )

    stt = Qwen3STTService(api_url="http://localhost:8001/v1/chat/completions")
    llm = OpenAILLMService(model="gpt-4o", system_instruction=ENGLISH_TUTOR_PROMPT)
    tts = Qwen3TTSService(api_url="http://localhost:8002/tts", speaker="Ryan")

    pipeline = Pipeline([
        transport.input(),
        stt,
        llm,
        tts,
        transport.output(),
    ])

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        await task.queue_frames([LLMRunFrame()])

    runner = PipelineRunner()
    await runner.run(task)
```

### Step 4: English Tutor Prompt (`server/prompts.py`)

```python
ENGLISH_TUTOR_PROMPT = """You are a friendly English conversation tutor.
Your job is to have natural conversations to help the user practice English.

Rules:
- Speak naturally as in a real conversation
- Keep responses concise (1-3 sentences) so the conversation flows
- Gently correct grammar/pronunciation mistakes inline
- Adjust difficulty to the user's level
- Suggest better phrasing when appropriate
- Be encouraging and patient
- Do not use markdown, bullet points, or any text formatting - speak naturally
- Start by greeting the user and asking what they'd like to talk about
"""
```

### Step 5: React Frontend (`client/`)

**App.tsx**:
```tsx
import { PipecatClientProvider, PipecatClientAudio } from "@pipecat-ai/client-react";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { ChatInterface } from "./components/ChatInterface";

function App() {
  return (
    <PipecatClientProvider transport={new SmallWebRTCTransport()}>
      <PipecatClientAudio />
      <ChatInterface />
    </PipecatClientProvider>
  );
}
```

**ChatInterface.tsx**:
```tsx
import { usePipecatClient, usePipecatConversation } from "@pipecat-ai/client-react";

function ChatInterface() {
  const client = usePipecatClient();
  const { messages } = usePipecatConversation();

  const connect = async () => {
    await client.startBotAndConnect({ endpoint: "/api/connect" });
  };

  return (
    <div>
      <button onClick={connect}>Start Conversation</button>
      <div className="transcript">
        {messages.map((msg, i) => (
          <div key={i} className={msg.role}>
            <strong>{msg.role === "user" ? "You" : "Tutor"}:</strong>
            {msg.parts?.map((part, j) => (
              <span key={j}>{typeof part.text === "string" ? part.text : part.text.spoken}</span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### Step 6: Vite Config

```ts
export default defineConfig({
  server: {
    proxy: { "/api": "http://localhost:7860" }
  }
})
```

---

## Implementation Order

1. **Pipecat custom services** — `qwen3_stt.py` and `qwen3_tts.py` subclasses (integrates with existing ASR/TTS servers)
2. **English tutor prompt** — `prompts.py` system prompt for GPT-4o
3. **Pipeline server** — `bot.py` with FastAPI + SmallWebRTC + full pipeline
4. **React frontend** — Vite + Pipecat React SDK with transcript UI
5. **Integration test** — end-to-end voice conversation
6. **Polish** — styling, error handling, reconnection, audio indicators

---

## Running the Full Stack

```bash
# Qwen3-ASR server (port 8001) — already running
# Qwen3-TTS server (port 8002) — already running

# Terminal 1: Pipecat pipeline server
export OPENAI_API_KEY=sk-...
uvicorn server.bot:app --host 0.0.0.0 --port 7860

# Terminal 2: React frontend
cd client && npm run dev
```

---

## Dependencies

### Server (`requirements.txt`)
```
pipecat-ai[smallwebrtc,openai,silero]
fastapi
uvicorn
aiohttp
numpy
```

### Client (`package.json`)
```json
{
  "dependencies": {
    "@pipecat-ai/client-js": "latest",
    "@pipecat-ai/client-react": "latest",
    "@pipecat-ai/small-webrtc-transport": "latest",
    "react": "^18",
    "react-dom": "^18"
  }
}
```

---

## Verification

1. Ensure ASR (port 8001) and TTS (port 8002) servers are running, then start Pipecat and frontend
2. Open browser at `http://localhost:5173`
3. Click "Start Conversation" → grant mic permission
4. Speak English → verify user transcript appears
5. Verify GPT-4o generates a tutor response
6. Verify Qwen3-TTS synthesizes audio and it plays back
7. Verify tutor transcript appears alongside audio
8. Test interruption: speak while the bot is talking → it should stop and listen
