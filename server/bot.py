import asyncio
import os

import uvicorn
from fastapi import FastAPI, Request
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
    await connection.initialize(body.get("sdp", ""), body.get("type", "offer"))
    task = asyncio.create_task(run_bot(connection))
    answer = connection.get_answer()
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
        PipelineParams(allow_interruptions=True),
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
