"""
SpeakWell STT Server — Qwen3-ASR-1.7B with vLLM backend
Runs on port 8001
"""

import io
import logging
import tempfile
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    from qwen_asr import Qwen3ASRModel

    logger.info("Loading STT model %s with vLLM backend ...", MODEL_ID)
    model = Qwen3ASRModel.LLM(
        model=MODEL_ID,
        gpu_memory_utilization=0.4,
        max_inference_batch_size=32,
        max_new_tokens=4096,
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


class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None


class BatchTranscriptionResponse(BaseModel):
    results: list[TranscriptionResponse]


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
