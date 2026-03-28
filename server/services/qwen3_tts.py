from typing import AsyncGenerator

import aiohttp
import numpy as np
from loguru import logger

from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.services.tts_service import TTSService


class Qwen3TTSService(TTSService):
    """TTS service that calls a Qwen3-TTS HTTP server."""

    def __init__(
        self,
        *,
        api_url: str = "http://localhost:8002/tts",
        speaker: str = "Ryan",
        language: str = "English",
        output_sample_rate: int = 16000,
        **kwargs,
    ):
        super().__init__(sample_rate=output_sample_rate, **kwargs)
        self._api_url = api_url
        self._speaker = speaker
        self._language = language
        self._output_sample_rate = output_sample_rate
        self._session: aiohttp.ClientSession | None = None

    async def start(self, frame):
        await super().start(frame)
        self._session = aiohttp.ClientSession()

    async def stop(self, frame):
        if self._session:
            await self._session.close()
            self._session = None
        await super().stop(frame)

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        if not text or not text.strip():
            return

        try:
            async with self._session.post(
                self._api_url,
                json={
                    "text": text,
                    "language": self._language,
                    "speaker": self._speaker,
                },
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"TTS error ({resp.status}): {error_text}")
                    return

                audio_bytes = await resp.read()
                source_sample_rate = int(
                    resp.headers.get("X-Sample-Rate", "12000")
                )
                logger.info(
                    f"TTS response: {len(audio_bytes)} bytes, "
                    f"source_sr={source_sample_rate}, target_sr={self._output_sample_rate}"
                )

                if source_sample_rate != self._output_sample_rate:
                    audio_bytes = self._resample(
                        audio_bytes, source_sample_rate, self._output_sample_rate
                    )

                # Yield in chunks for smoother streaming (200ms per chunk)
                bytes_per_sample = 2  # 16-bit
                chunk_size = int(self._output_sample_rate * 0.2) * bytes_per_sample

                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i : i + chunk_size]
                    yield TTSAudioRawFrame(
                        audio=chunk,
                        sample_rate=self._output_sample_rate,
                        num_channels=1,
                        context_id=context_id,
                    )

        except Exception as e:
            logger.error(f"TTS request failed: {e}")

    @staticmethod
    def _resample(audio_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
        """Resample 16-bit mono PCM audio using numpy linear interpolation."""
        if from_rate == to_rate:
            return audio_bytes
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        ratio = to_rate / from_rate
        new_length = int(len(samples) * ratio)
        indices = np.linspace(0, len(samples) - 1, new_length)
        resampled = np.interp(indices, np.arange(len(samples)), samples)
        return resampled.astype(np.int16).tobytes()
