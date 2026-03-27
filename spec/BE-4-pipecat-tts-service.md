# BE-4: Custom Pipecat TTS Service

**File:** `server/services/qwen3_tts.py`
**Depends on:** None (TTS server is already running on port 8002)
**Team:** Backend

---

## Objective

Create a custom Pipecat `TTSService` subclass that receives text from the LLM, sends it to the Qwen3-TTS HTTP server (port 8002, built in BE-1), and yields audio frames back into the pipeline for WebRTC output.

---

## Background: How Pipecat TTS Services Work

The TTS service sits between the LLM and the transport output:

```
LLM → [TextFrame / LLMFullResponseEndFrame] → TTSService → [TTSAudioRawFrame] → transport.output()
```

Key Pipecat concepts:
- **`TextFrame`**: Contains text from the LLM. The TTS service converts this to audio.
- **`TTSAudioRawFrame`**: Raw PCM audio frame. Contains `audio` (bytes), `sample_rate` (int), `num_channels` (int).
- **Sentence aggregation**: Pipecat typically aggregates LLM output into sentences before sending to TTS. The base `TTSService` handles this.
- **Interruptions**: When the user starts speaking mid-response, Pipecat cancels pending TTS. The service should handle cancellation gracefully.

### Pipecat TTS Base Class

Check the current Pipecat source for the exact API. The `TTSService` base class provides:

- `run_tts(text: str) -> AsyncGenerator[Frame]` — override this. Receives text, yields audio frames.
- Constructor: pass `sample_rate` to tell Pipecat what sample rate the audio will be.
- The base class handles text aggregation, interruption, and frame routing.

**Important:** Verify the exact API:
```bash
python -c "from pipecat.services import ai_services; help(ai_services.TTSService)"
```

---

## Requirements

### 1. Call the TTS HTTP Server

Send text to the BE-1 TTS server and receive raw PCM audio:

```python
async with self._session.post(self._api_url, json={
    "text": text,
    "language": "English",
    "speaker": self._speaker,
}) as resp:
    audio_bytes = await resp.read()
    sample_rate = int(resp.headers.get("X-Sample-Rate", "12000"))
```

### 2. Audio Sample Rate Handling

**Critical:** Qwen3-TTS outputs at **12kHz**, but WebRTC typically expects **16kHz** or **24kHz**.

Options:
1. **Resample in this service** — convert 12kHz → 16kHz before yielding frames
2. **Let Pipecat handle it** — Pipecat may auto-resample if you declare the correct `sample_rate`
3. **Resample in the TTS server (BE-1)** — add a query param to request a specific output rate

Check if Pipecat's `SmallWebRTCTransport` handles sample rate conversion. If it does, just declare `sample_rate=12000` in the constructor and yield 12kHz audio. If not, resample here:

```python
import audioop

def resample_audio(audio_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample PCM audio using audioop (stdlib, no dependencies)."""
    if from_rate == to_rate:
        return audio_bytes
    # audioop.ratecv: (fragment, width, nchannels, inrate, outrate, state)
    converted, _ = audioop.ratecv(audio_bytes, 2, 1, from_rate, to_rate, None)
    return converted
```

> **Note:** `audioop` is deprecated in Python 3.11+ and removed in 3.13. If using Python 3.13+, use `scipy.signal.resample` or include a simple linear interpolation function.

### 3. Chunked Audio Delivery

For smoother playback, consider yielding audio in chunks rather than one large frame:

```python
CHUNK_SIZE = 4800  # 300ms at 16kHz, 16-bit mono = 4800 bytes

for i in range(0, len(audio_bytes), CHUNK_SIZE):
    chunk = audio_bytes[i:i + CHUNK_SIZE]
    yield TTSAudioRawFrame(
        audio=chunk,
        sample_rate=sample_rate,
        num_channels=1,
    )
```

This allows the transport to start sending audio to the browser before the entire utterance is ready.

### 4. HTTP Session Management

Same as BE-3: create a persistent `aiohttp.ClientSession` in `start()`, close in `stop()`.

---

## Full Implementation Skeleton

```python
import aiohttp
from typing import AsyncGenerator

from pipecat.frames.frames import Frame, TTSAudioRawFrame
from pipecat.services.ai_services import TTSService


class Qwen3TTSService(TTSService):
    """TTS service that calls a Qwen3-TTS HTTP server."""

    def __init__(
        self,
        api_url: str = "http://localhost:8002/tts",
        speaker: str = "Ryan",
        language: str = "English",
        output_sample_rate: int = 16000,  # What the transport expects
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

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        if not text or not text.strip():
            return

        try:
            async with self._session.post(self._api_url, json={
                "text": text,
                "language": self._language,
                "speaker": self._speaker,
            }) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"TTS error ({resp.status}): {error_text}")
                    return

                audio_bytes = await resp.read()
                source_sample_rate = int(resp.headers.get("X-Sample-Rate", "12000"))

                # Resample if needed
                if source_sample_rate != self._output_sample_rate:
                    audio_bytes = self._resample(
                        audio_bytes, source_sample_rate, self._output_sample_rate
                    )

                # Yield in chunks for smoother streaming
                chunk_duration_ms = 200
                bytes_per_sample = 2  # 16-bit
                chunk_size = int(
                    self._output_sample_rate * chunk_duration_ms / 1000
                ) * bytes_per_sample

                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i:i + chunk_size]
                    yield TTSAudioRawFrame(
                        audio=chunk,
                        sample_rate=self._output_sample_rate,
                        num_channels=1,
                    )

        except Exception as e:
            print(f"TTS request failed: {e}")

    @staticmethod
    def _resample(audio_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
        """Resample 16-bit mono PCM audio."""
        if from_rate == to_rate:
            return audio_bytes
        try:
            import audioop
            converted, _ = audioop.ratecv(audio_bytes, 2, 1, from_rate, to_rate, None)
            return converted
        except ImportError:
            # audioop removed in Python 3.13+
            # Fallback: use numpy linear interpolation
            import numpy as np
            samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            ratio = to_rate / from_rate
            new_length = int(len(samples) * ratio)
            indices = np.linspace(0, len(samples) - 1, new_length)
            resampled = np.interp(indices, np.arange(len(samples)), samples)
            return resampled.astype(np.int16).tobytes()
```

---

## Important Notes

### Pipecat Version Compatibility

Same caveats as BE-3. Verify:

1. **Import path**: `pipecat.services.ai_services.TTSService` or `pipecat.services.tts.TTSService`
2. **`run_tts` signature**: May accept `context_id` or other params — check the base class
3. **`TTSAudioRawFrame` fields**: Verify exact constructor params
4. **Sample rate declaration**: How does the base class use the `sample_rate` param?

### Latency

TTS is the biggest latency contributor in the pipeline. Measure:
- Time from `run_tts` call to first audio chunk yielded
- Total time for a typical sentence (10-20 words)

If latency is too high, consider:
1. Streaming TTS (if BE-1 supports it)
2. Sentence splitting (shorter texts = faster synthesis)

### Interruption Handling

When the user speaks during TTS playback, Pipecat cancels the current TTS task. Make sure:
- The HTTP request is cancellable (aiohttp supports this)
- No leaked sessions or hanging connections
- The service recovers cleanly for the next utterance

---

## Testing

### Unit Test

```python
async def test_tts_resample():
    # Test resampling 12kHz → 16kHz
    # 1 second of silence at 12kHz, 16-bit mono
    audio_12k = b'\x00\x00' * 12000
    result = Qwen3TTSService._resample(audio_12k, 12000, 16000)
    # Should be approximately 16000 samples * 2 bytes
    assert abs(len(result) - 32000) < 100  # Allow small rounding error
```

### Integration Test (requires BE-1 running)

```python
async def test_tts_integration():
    tts = Qwen3TTSService(api_url="http://localhost:8002/tts")
    await tts.start(None)

    frames = []
    async for frame in tts.run_tts("Hello, how are you today?"):
        frames.append(frame)

    assert len(frames) > 0
    total_bytes = sum(len(f.audio) for f in frames)
    assert total_bytes > 0
    print(f"Generated {len(frames)} audio chunks, {total_bytes} bytes total")
    print(f"Sample rate: {frames[0].sample_rate}")

    # Optionally save to file for manual listening
    with open("test_tts_output.raw", "wb") as f:
        for frame in frames:
            f.write(frame.audio)
    print("Saved to test_tts_output.raw — play with:")
    print(f"  ffplay -f s16le -ar {frames[0].sample_rate} -ac 1 test_tts_output.raw")

    await tts.stop(None)
```

---

## Dependencies

```
pipecat-ai
aiohttp
numpy  # fallback resampling only
```

---

## Acceptance Criteria

- [ ] `Qwen3TTSService` subclasses the correct Pipecat TTS base class
- [ ] Text is sent to the TTS HTTP server in the expected format
- [ ] Raw PCM response is correctly received and parsed
- [ ] Audio is resampled from 12kHz to the transport's expected rate (if needed)
- [ ] Audio is delivered in chunks for streaming playback
- [ ] Empty text is handled gracefully
- [ ] TTS errors are logged but don't crash the pipeline
- [ ] HTTP session is reused across calls
- [ ] Integration test produces audible, correct speech
