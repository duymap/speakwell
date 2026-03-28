import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMMessagesFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.openai.llm import OpenAILLMContext, OpenAILLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.smallwebrtc.request_handler import (
    IceCandidate,
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
request_handler = SmallWebRTCRequestHandler()


@app.post("/api/offer")
async def offer(request: Request):
    body = await request.json()
    webrtc_request = SmallWebRTCRequest.from_dict(body)

    async def on_connection(connection: SmallWebRTCConnection):
        asyncio.create_task(run_bot(connection))

    answer = await request_handler.handle_web_request(webrtc_request, on_connection)
    return JSONResponse(content=answer)


@app.patch("/api/offer")
async def offer_patch(request: Request):
    body = await request.json()
    candidates = [
        IceCandidate(
            candidate=c["candidate"],
            sdp_mid=c.get("sdpMid", ""),
            sdp_mline_index=c.get("sdpMLineIndex", 0),
        )
        for c in body.get("candidates", [])
    ]
    patch_request = SmallWebRTCPatchRequest(
        pc_id=body["pc_id"],
        candidates=candidates,
    )
    await request_handler.handle_patch_request(patch_request)
    return JSONResponse(content={"status": "ok"})


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def run_bot(connection: SmallWebRTCConnection):
    import logging
    logger = logging.getLogger("run_bot")
    logger.info("run_bot started")
    try:
        await _run_bot(connection)
    except Exception as e:
        logger.exception(f"run_bot crashed: {e}")


async def _run_bot(connection: SmallWebRTCConnection):
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

    llm = OpenAILLMService(model=LLM_MODEL)

    tts = Qwen3TTSService(api_url=TTS_URL, speaker=TTS_SPEAKER)

    messages = [{"role": "system", "content": ENGLISH_TUTOR_PROMPT}]
    context = OpenAILLMContext(messages=messages)
    context_aggregator = llm.create_context_aggregator(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True),
    )

    @transport.event_handler("on_client_connected")
    async def on_connected(transport, client):
        await task.queue_frames(
            [LLMMessagesFrame(messages=messages)]
        )

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(transport, client):
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
