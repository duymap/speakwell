"""
SpeakWell TTS Server — Qwen3-TTS-12Hz-1.7B-VoiceDesign (transformers backend)
Runs on port 8002

Exposes a /tts endpoint returning raw PCM audio with an X-Sample-Rate header,
matching what the Pipecat pipeline server (qwen3_tts.py) expects.
"""

import io
import logging
from contextlib import asynccontextmanager

import numpy as np
import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("tts_server")
logging.basicConfig(level=logging.INFO)

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
HOST = "0.0.0.0"
PORT = 8002

# Default voice design instruction for the VoiceDesign model
DEFAULT_INSTRUCT = "A warm, friendly voice with a natural and clear tone."

model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    from qwen_tts import Qwen3TTSModel

    logger.info("Loading TTS model %s ...", MODEL_ID)
    model = Qwen3TTSModel.from_pretrained(
        MODEL_ID,
        device_map="cuda:0",
        dtype=torch.bfloat16,
    )
    logger.info("TTS model loaded.")
    yield
    model = None


app = FastAPI(title="SpeakWell TTS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_LANGUAGES = [
    "Chinese", "English", "Japanese", "Korean",
    "German", "French", "Russian", "Portuguese",
    "Spanish", "Italian", "Auto",
]

# Map speaker presets to voice design instructions (VoiceDesign model
# doesn't use speaker names, so we translate them to instruct descriptions)
SPEAKER_VOICES = {
    "Ryan": "A confident, warm adult male voice with clear articulation and a friendly tone.",
    "Vivian": "A bright, cheerful young female voice with a warm and engaging tone.",
    "Default": DEFAULT_INSTRUCT,
}


# ---------------------------------------------------------------------------
# Pipeline-compatible endpoint (used by Pipecat qwen3_tts.py)
# ---------------------------------------------------------------------------

class PipelineTTSRequest(BaseModel):
    text: str
    language: str = "English"
    speaker: str = "Ryan"


@app.post("/tts")
async def tts_pipeline(req: PipelineTTSRequest):
    """Endpoint compatible with the Pipecat pipeline server.

    Accepts: {"text": "...", "language": "English", "speaker": "Ryan"}
    Returns: Raw 16-bit PCM audio bytes with X-Sample-Rate header.
    """
    if model is None:
        raise HTTPException(503, "Model not loaded yet")

    if not req.text or not req.text.strip():
        raise HTTPException(400, "Empty text")

    instruct = SPEAKER_VOICES.get(req.speaker, DEFAULT_INSTRUCT)
    language = req.language if req.language in SUPPORTED_LANGUAGES else "English"

    wavs, sr = model.generate_voice_design(
        text=req.text,
        language=language,
        instruct=instruct,
    )

    # Convert float audio to 16-bit PCM bytes
    audio = wavs[0]
    if audio.dtype != np.int16:
        # Normalize float audio to int16 range
        if np.issubdtype(audio.dtype, np.floating):
            audio = np.clip(audio, -1.0, 1.0)
            audio = (audio * 32767).astype(np.int16)
        else:
            audio = audio.astype(np.int16)

    pcm_bytes = audio.tobytes()

    return Response(
        content=pcm_bytes,
        media_type="application/octet-stream",
        headers={"X-Sample-Rate": str(sr)},
    )


# ---------------------------------------------------------------------------
# Standalone synthesis endpoints (for direct usage / testing)
# ---------------------------------------------------------------------------

class SynthesisRequest(BaseModel):
    text: str
    language: str = "Auto"
    instruct: str = DEFAULT_INSTRUCT
    format: str = "wav"


class BatchSynthesisRequest(BaseModel):
    items: list[SynthesisRequest]


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_ID}


@app.get("/v1/voices/languages")
async def list_languages():
    return {"languages": SUPPORTED_LANGUAGES}


@app.post("/v1/synthesize")
async def synthesize(req: SynthesisRequest):
    """Synthesize speech from text. Returns audio as wav/mp3 binary."""
    if model is None:
        raise HTTPException(503, "Model not loaded yet")

    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            400,
            f"Unsupported language '{req.language}'. Must be one of: {SUPPORTED_LANGUAGES}",
        )

    wavs, sr = model.generate_voice_design(
        text=req.text,
        language=req.language,
        instruct=req.instruct,
    )

    buf = io.BytesIO()
    audio_format = req.format.lower()
    if audio_format not in ("wav", "mp3"):
        audio_format = "wav"

    sf.write(buf, wavs[0], sr, format=audio_format.upper())
    buf.seek(0)

    media_type = "audio/wav" if audio_format == "wav" else "audio/mpeg"
    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=speech.{audio_format}"},
    )


@app.post("/v1/synthesize/batch")
async def synthesize_batch(req: BatchSynthesisRequest):
    """Synthesize multiple texts in a batch. Returns a zip of audio files."""
    import zipfile

    if model is None:
        raise HTTPException(503, "Model not loaded yet")

    texts = [item.text for item in req.items]
    languages = [item.language for item in req.items]
    instructs = [item.instruct for item in req.items]

    wavs, sr = model.generate_voice_design(
        text=texts,
        language=languages,
        instruct=instructs,
    )

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, wav in enumerate(wavs):
            audio_buf = io.BytesIO()
            fmt = req.items[i].format.lower() if req.items[i].format.lower() in ("wav", "mp3") else "wav"
            sf.write(audio_buf, wav, sr, format=fmt.upper())
            audio_buf.seek(0)
            zf.writestr(f"speech_{i}.{fmt}", audio_buf.read())

    zip_buf.seek(0)
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=batch_speech.zip"},
    )


if __name__ == "__main__":
    uvicorn.run("tts_server:app", host=HOST, port=PORT, log_level="info")
