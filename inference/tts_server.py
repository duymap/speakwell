"""
SpeakWell TTS Server — Qwen3-TTS-12Hz-1.7B-VoiceDesign (transformers backend)
Runs on port 8002
"""

import io
import logging
from contextlib import asynccontextmanager

import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("tts_server")
logging.basicConfig(level=logging.INFO)

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
HOST = "0.0.0.0"
PORT = 8002

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


class SynthesisRequest(BaseModel):
    text: str
    language: str = "Auto"
    instruct: str = "A warm, friendly voice with a natural and clear tone."
    format: str = "wav"  # wav or mp3


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
