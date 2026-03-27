# SpeakWell Task Specs

Task specifications for the English Learning Voice AI Web App.

> **Note:** Qwen3-ASR (port 8001) and Qwen3-TTS (port 8002) servers are already running.
> Backend tasks only need to integrate against their APIs.

## Backend Tasks

| Task | File | Summary | Depends On |
|------|------|---------|------------|
| BE-3 | [BE-3-pipecat-stt-service.md](BE-3-pipecat-stt-service.md) | Custom Pipecat STT service | None |
| BE-4 | [BE-4-pipecat-tts-service.md](BE-4-pipecat-tts-service.md) | Custom Pipecat TTS service | None |
| BE-5 | [BE-5-tutor-prompt.md](BE-5-tutor-prompt.md) | English tutor system prompt | None |
| BE-6 | [BE-6-pipeline-server.md](BE-6-pipeline-server.md) | Main Pipecat pipeline + FastAPI server | BE-3, BE-4, BE-5 |

## Frontend Tasks

| Task | File | Summary | Depends On |
|------|------|---------|------------|
| FE-1 | [FE-1-project-scaffold.md](FE-1-project-scaffold.md) | Vite + React + TypeScript scaffold | None |
| FE-2 | [FE-2-app-shell.md](FE-2-app-shell.md) | PipecatClientProvider setup | FE-1 |
| FE-3 | [FE-3-chat-interface.md](FE-3-chat-interface.md) | Transcript UI + connect/disconnect | FE-2 |
| FE-4 | [FE-4-audio-indicator.md](FE-4-audio-indicator.md) | Visual speaking/listening indicator | FE-2 |
| FE-5 | [FE-5-styling-polish.md](FE-5-styling-polish.md) | Styling, error states, responsive design | FE-3, FE-4 |

## Integration

| Task | File | Summary | Depends On |
|------|------|---------|------------|
| INT-1 | [INT-1-integration-test.md](INT-1-integration-test.md) | End-to-end voice conversation test | BE-6, FE-5 |

## Existing Infrastructure

These servers are already deployed and running — no tasks needed:

| Service | Endpoint | Notes |
|---------|----------|-------|
| Qwen3-ASR | `POST http://localhost:8001/v1/chat/completions` | OpenAI-compatible API, base64 WAV input |
| Qwen3-TTS | `POST http://localhost:8002/tts` | Returns raw PCM int16, 12kHz, `X-Sample-Rate` header |

## Parallel Execution

```
Backend                          Frontend
--------                         --------
BE-3 --+                        FE-1
BE-4 --+  (all parallel)          |
BE-5 --+                        FE-2
       |                           |
BE-6 --+ (after BE-3,4,5)      FE-3 + FE-4 (parallel)
       |                           |
       |                        FE-5
       |                          |
       +------ INT-1 -------------+
```
