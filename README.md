# SpeakWell

A real-time voice AI web app for practicing English conversation with an AI tutor. Users speak naturally with the AI, which listens, responds via voice, and displays a live transcript on screen.

## Architecture

```
Browser (React + WebRTC)
    ↕
Pipecat Pipeline Server (FastAPI, port 7860)
    ↕               ↕               ↕
Qwen3-ASR       GPT-4o LLM      Qwen3-TTS
(STT, port 8001)                 (TTS, port 8002)
```

**Pipeline flow:** Audio in → Speech-to-Text → LLM → Text-to-Speech → Audio out

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, Pipecat React SDK |
| Transport | WebRTC via Pipecat SmallWebRTC |
| Backend | FastAPI + Pipecat pipeline orchestration |
| LLM | OpenAI GPT-4o |
| STT | [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) (local GPU, OpenAI-compatible API) |
| TTS | [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) (local GPU, 12kHz output) |
| VAD | Silero VAD (voice activity detection) |

## Prerequisites

- Python 3.10+
- Node.js 18+
- Qwen3-ASR server running on port 8001
- Qwen3-TTS server running on port 8002
- OpenAI API key

## Setup

### Backend

```bash
cd server
pip install -r requirements.txt
```

### Frontend

```bash
cd client
npm install
```

## Running

```bash
# Terminal 1: Pipeline server
export OPENAI_API_KEY=sk-...
cd server
uvicorn bot:app --host 0.0.0.0 --port 7860

# Terminal 2: Frontend dev server
cd client
npm run dev
```

Open `http://localhost:5173`, click **Start Conversation**, and grant microphone access.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (required) |
| `ASR_URL` | `http://localhost:8001/v1/chat/completions` | Qwen3-ASR endpoint |
| `TTS_URL` | `http://localhost:8002/tts` | Qwen3-TTS endpoint |
| `LLM_MODEL` | `gpt-4o` | OpenAI model name |
| `TTS_SPEAKER` | `Ryan` | TTS voice preset |
| `PORT` | `7860` | Backend server port |

## Project Structure

```
speakwell/
├── server/
│   ├── bot.py                 # FastAPI app + Pipecat pipeline
│   ├── prompts.py             # English tutor system prompt
│   ├── services/
│   │   ├── qwen3_stt.py       # Custom Pipecat STT service → Qwen3-ASR
│   │   └── qwen3_tts.py       # Custom Pipecat TTS service → Qwen3-TTS
│   └── requirements.txt
├── client/
│   ├── src/
│   │   ├── App.tsx            # PipecatClientProvider setup
│   │   └── components/
│   │       ├── ChatInterface.tsx   # Transcript + connect/disconnect
│   │       └── AudioIndicator.tsx  # Visual speaking/listening state
│   ├── package.json
│   └── vite.config.ts         # Proxies /api → backend
└── spec/                      # Implementation specifications
```

## License

MIT
