import base64
import io
import re
import struct
from typing import AsyncGenerator

import aiohttp
from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.services.stt_service import SegmentedSTTService


class Qwen3STTService(SegmentedSTTService):
    """STT service that calls a Qwen3-ASR vLLM server (OpenAI-compatible API)."""

    def __init__(
        self,
        *,
        api_url: str = "http://localhost:8001/v1/chat/completions",
        model: str = "Qwen/Qwen3-ASR-1.7B",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._api_url = api_url
        self._model = model
        self._session: aiohttp.ClientSession | None = None

    async def start(self, frame):
        await super().start(frame)
        self._session = aiohttp.ClientSession()

    async def stop(self, frame):
        if self._session:
            await self._session.close()
            self._session = None
        await super().stop(frame)

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        """audio is WAV bytes from SegmentedSTTService (buffered full utterance)."""
        if not audio:
            return

        audio_b64 = base64.b64encode(audio).decode()

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "audio_url",
                            "audio_url": {
                                "url": f"data:audio/wav;base64,{audio_b64}"
                            },
                        }
                    ],
                }
            ],
        }

        try:
            async with self._session.post(self._api_url, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"ASR error ({resp.status}): {error_text}")
                    return

                result = await resp.json()
                content = result["choices"][0]["message"]["content"]
                text = self._parse_asr_output(content)

                if text:
                    yield TranscriptionFrame(
                        text=text,
                        user_id="user",
                        timestamp="",
                    )
        except Exception as e:
            logger.error(f"ASR request failed: {e}")

    @staticmethod
    def _pcm_to_wav_base64(
        audio_bytes: bytes,
        sample_rate: int = 16000,
        num_channels: int = 1,
        sample_width: int = 2,
    ) -> str:
        """Convert raw PCM bytes to base64-encoded WAV."""
        buf = io.BytesIO()
        data_size = len(audio_bytes)
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(
            struct.pack(
                "<IHHIIHH",
                16,
                1,
                num_channels,
                sample_rate,
                sample_rate * num_channels * sample_width,
                num_channels * sample_width,
                sample_width * 8,
            )
        )
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(audio_bytes)
        return base64.b64encode(buf.getvalue()).decode()

    @staticmethod
    def _parse_asr_output(content: str) -> str:
        """Extract transcribed text from ASR response.

        Format: '<|language_code|>transcribed text'
        Example: '<|en|>Hello, how are you?'
        """
        try:
            from qwen_asr import parse_asr_output

            _, text = parse_asr_output(content)
            return text.strip()
        except ImportError:
            return re.sub(r"^<\|[a-z]{2}\|>", "", content).strip()
