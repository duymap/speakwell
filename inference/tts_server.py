"""
SpeakWell TTS Server — Qwen3-TTS with vLLM-Omni backend
Runs on port 8002

Uses vllm-omni's Omni engine for efficient GPU inference with
continuous batching and PagedAttention. Exposes the same /tts endpoint
returning raw PCM audio with an X-Sample-Rate header.
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

engine = None


def _estimate_token_length(text: str, language: str = "English") -> int:
    """Estimate the number of prompt tokens needed for a TTS request.

    The Qwen3-TTS tokenizer operates at 12Hz (12 tokens per second of audio).
    We estimate ~150ms per word for English and ~200ms per character for CJK.
    """
    if language in ("Chinese", "Japanese", "Korean"):
        estimated_seconds = len(text) * 0.2
    else:
        estimated_seconds = len(text.split()) * 0.15
    # Minimum 1 second, add 20% buffer
    estimated_seconds = max(1.0, estimated_seconds * 1.2)
    return max(1, int(estimated_seconds * 12))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    from vllm_omni import Omni

    logger.info("Loading TTS model %s with vLLM-Omni engine ...", MODEL_ID)
    engine = Omni(
        model=MODEL_ID,
        log_stats=False,
    )
    logger.info("TTS model loaded with vLLM-Omni.")
    yield
    engine = None


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


def _generate_audio(text: str, language: str, instruct: str):
    """Run TTS inference through vLLM-Omni engine. Returns (audio_np, sample_rate)."""
    token_len = _estimate_token_length(text, language)
    inputs = {
        "prompt_token_ids": [0] * token_len,
        "additional_information": {
            "text": [text],
            "language": [language],
            "instruct": [instruct],
        },
    }

    results = engine.generate(inputs)

    # Extract audio from multimodal output
    # results[0].request_output is a list of RequestOutput objects
    # Each RequestOutput has a .multimodal_output dict with "audio" and "sr"
    stage_output = results[0]
    req_output = stage_output.request_output[0]
    mm_output = req_output.multimodal_output
    audio = mm_output["audio"]
    sr = mm_output["sr"]

    # Convert to numpy if it's a torch tensor
    if isinstance(audio, torch.Tensor):
        audio = audio.cpu().numpy()
    elif isinstance(audio, list):
        audio = torch.cat(audio).cpu().numpy() if isinstance(audio[0], torch.Tensor) else np.array(audio)

    return audio, sr


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
    if engine is None:
        raise HTTPException(503, "Model not loaded yet")

    if not req.text or not req.text.strip():
        raise HTTPException(400, "Empty text")

    instruct = SPEAKER_VOICES.get(req.speaker, DEFAULT_INSTRUCT)
    language = req.language if req.language in SUPPORTED_LANGUAGES else "English"

    audio, sr = _generate_audio(req.text, language, instruct)

    # Convert float audio to 16-bit PCM bytes
    if audio.dtype != np.int16:
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
    return {"status": "ok", "model": MODEL_ID, "backend": "vllm-omni"}


@app.get("/v1/voices/languages")
async def list_languages():
    return {"languages": SUPPORTED_LANGUAGES}


@app.post("/v1/synthesize")
async def synthesize(req: SynthesisRequest):
    """Synthesize speech from text. Returns audio as wav/mp3 binary."""
    if engine is None:
        raise HTTPException(503, "Model not loaded yet")

    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            400,
            f"Unsupported language '{req.language}'. Must be one of: {SUPPORTED_LANGUAGES}",
        )

    audio, sr = _generate_audio(req.text, req.language, req.instruct)

    buf = io.BytesIO()
    audio_format = req.format.lower()
    if audio_format not in ("wav", "mp3"):
        audio_format = "wav"

    sf.write(buf, audio, sr, format=audio_format.upper())
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

    if engine is None:
        raise HTTPException(503, "Model not loaded yet")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, item in enumerate(req.items):
            audio, sr = _generate_audio(item.text, item.language, item.instruct)
            audio_buf = io.BytesIO()
            fmt = item.format.lower() if item.format.lower() in ("wav", "mp3") else "wav"
            sf.write(audio_buf, audio, sr, format=fmt.upper())
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
