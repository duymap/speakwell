"""
SpeakWell STT Server — Qwen3-ASR-1.7B with vLLM backend
Runs on port 8001

Exposes an OpenAI-compatible /v1/chat/completions endpoint so the
Pipecat pipeline server can send base64-encoded audio and receive
transcribed text in the standard chat-completions response format.
"""

import asyncio
import base64
import io
import logging
import tempfile
import time
import wave
from contextlib import asynccontextmanager
from pathlib import Path

import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger("stt_server")
logging.basicConfig(level=logging.INFO)

MODEL_ID = "Qwen/Qwen3-ASR-1.7B"
HOST = "0.0.0.0"
PORT = 8001

model = None
_inference_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    from qwen_asr import Qwen3ASRModel

    logger.info("Loading STT model %s with vLLM backend ...", MODEL_ID)
    model = Qwen3ASRModel.LLM(
        model=MODEL_ID,
        gpu_memory_utilization=0.9,
        max_new_tokens=32,
        max_model_len=4096,
        enforce_eager=True,
    )
    logger.info("STT model loaded.")
    yield
    model = None


app = FastAPI(title="SpeakWell STT", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None


class BatchTranscriptionResponse(BaseModel):
    results: list[TranscriptionResponse]


# ---------------------------------------------------------------------------
# OpenAI-compatible chat completions endpoint (used by Pipecat pipeline)
# ---------------------------------------------------------------------------

@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    """OpenAI-compatible endpoint that accepts base64 audio in audio_url
    and returns transcription in the chat completions response format.

    Expected payload (from Pipecat qwen3_stt.py):
    {
        "model": "Qwen/Qwen3-ASR-1.7B",
        "messages": [{
            "role": "user",
            "content": [{
                "type": "audio_url",
                "audio_url": {"url": "data:audio/wav;base64,<base64data>"}
            }]
        }]
    }
    """
    if model is None:
        raise HTTPException(503, "Model not loaded yet")

    try:
        messages = request.get("messages", [])
        if not messages:
            raise HTTPException(400, "No messages provided")

        # Extract base64 audio from the last user message
        last_msg = messages[-1]
        content = last_msg.get("content", [])

        audio_data = None
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "audio_url":
                    url = part["audio_url"]["url"]
                    # Parse data URI: data:audio/wav;base64,<data>
                    if url.startswith("data:"):
                        b64_data = url.split(",", 1)[1]
                        audio_data = base64.b64decode(b64_data)
                    break

        if audio_data is None:
            raise HTTPException(400, "No audio data found in request")

        # Write to temp file for the model (lock to prevent concurrent vLLM access)
        async with _inference_lock:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(audio_data)
                tmp.flush()

                results = model.transcribe(audio=tmp.name, language="en")

        # Format as "<|language_code|>transcribed text" to match vLLM ASR output
        lang = results[0].language or ""
        text = results[0].text or ""

        # Map language name to code
        lang_map = {
            "English": "en", "Chinese": "zh", "Japanese": "ja",
            "Korean": "ko", "French": "fr", "German": "de",
            "Spanish": "es", "Russian": "ru", "Portuguese": "pt",
            "Italian": "it",
        }
        lang_code = lang_map.get(lang, lang.lower()[:2] if lang else "en")
        response_content = f"<|{lang_code}|>{text}"

        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.get("model", MODEL_ID),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content,
                    },
                    "finish_reason": "stop",
                }
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("chat/completions ASR error: %s", e, exc_info=True)
        raise HTTPException(500, str(e))


# ---------------------------------------------------------------------------
# Standalone transcription endpoints (for direct usage / testing)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_ID}


@app.post("/v1/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = Form(None),
):
    """Transcribe a single audio file. Accepts wav, mp3, flac, etc."""
    if model is None:
        raise HTTPException(503, "Model not loaded yet")

    suffix = Path(file.filename or "audio.wav").suffix
    async with _inference_lock:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp.flush()

            results = model.transcribe(
                audio=tmp.name,
                language=language,
            )

    return TranscriptionResponse(
        text=results[0].text,
        language=results[0].language,
    )


@app.post("/v1/transcribe/batch", response_model=BatchTranscriptionResponse)
async def transcribe_batch(
    files: list[UploadFile] = File(...),
    language: str | None = Form(None),
):
    """Transcribe multiple audio files in a single batch."""
    if model is None:
        raise HTTPException(503, "Model not loaded yet")

    tmp_paths = []
    tmp_files = []
    try:
        for f in files:
            suffix = Path(f.filename or "audio.wav").suffix
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(await f.read())
            tmp.flush()
            tmp_paths.append(tmp.name)
            tmp_files.append(tmp)

        async with _inference_lock:
            results = model.transcribe(
                audio=tmp_paths,
                language=language,
            )
    finally:
        for tmp in tmp_files:
            tmp.close()
            Path(tmp.name).unlink(missing_ok=True)

    return BatchTranscriptionResponse(
        results=[
            TranscriptionResponse(text=r.text, language=r.language)
            for r in results
        ]
    )


if __name__ == "__main__":
    uvicorn.run("stt_server:app", host=HOST, port=PORT, log_level="info")
