# BE-3: Custom Pipecat STT Service

**File:** `server/services/qwen3_stt.py`
**Depends on:** None (ASR server is already running on port 8001)
**Team:** Backend

---

## Objective

Create a custom Pipecat `STTService` subclass that receives raw audio frames from the WebRTC transport, converts them to base64-encoded WAV, sends them to the Qwen3-ASR server (port 8001), and yields `TranscriptionFrame`s back into the pipeline.

---

## Background: How Pipecat STT Services Work

Pipecat uses a pipeline architecture where frames flow through processors. The STT service sits between the transport input (raw audio from the user's mic) and the LLM.

The flow:
```
transport.input() → [raw audio frames] → STTService → [TranscriptionFrame] → LLM
```

Key Pipecat concepts:
- **`InputAudioRawFrame`**: Raw PCM audio from the transport. Contains `audio` (bytes), `sample_rate` (int), `num_channels` (int).
- **`TranscriptionFrame`**: Contains transcribed text. This is what the LLM consumes.
- **VAD (Voice Activity Detection)**: Pipecat uses Silero VAD to detect when the user starts/stops speaking. The STT service receives audio after VAD determines the user has finished a phrase.

### Pipecat STT Base Class

Check the current Pipecat source for the exact base class API. As of recent versions, `STTService` (from `pipecat.services.ai_services` or `pipecat.services.stt`) provides:

- `run_stt(audio: bytes) -> AsyncGenerator[Frame]` — override this method. Receives accumulated audio bytes after VAD detects end-of-speech.
- The base class handles VAD integration, audio accumulation, and frame routing.

**Important:** The Pipecat API evolves. Before implementing, check:
```bash
pip install pipecat-ai[smallwebrtc,openai,silero]
python -c "from pipecat.services import ai_services; help(ai_services.STTService)"
```

---

## Requirements

### 1. Audio Format Conversion

The transport delivers raw PCM audio. The ASR API expects base64-encoded WAV. You must:

1. Take raw PCM bytes (16-bit signed int, 16kHz, mono — WebRTC default)
2. Wrap in a valid WAV header
3. Base64-encode the result

```python
import struct
import io
import base64

def pcm_to_wav_base64(audio_bytes: bytes, sample_rate: int = 16000, num_channels: int = 1, sample_width: int = 2) -> str:
    """Convert raw PCM bytes to base64-encoded WAV."""
    buf = io.BytesIO()
    data_size = len(audio_bytes)
    # WAV header (44 bytes)
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<IHHIIHH",
        16,                                    # chunk size
        1,                                     # PCM format
        num_channels,
        sample_rate,
        sample_rate * num_channels * sample_width,  # byte rate
        num_channels * sample_width,           # block align
        sample_width * 8,                      # bits per sample
    ))
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(audio_bytes)
    return base64.b64encode(buf.getvalue()).decode()
```

### 2. ASR API Call

Send the base64 WAV to the Qwen3-ASR server:

```python
async def _call_asr(self, audio_b64: str) -> str:
    payload = {
        "model": "Qwen/Qwen3-ASR-1.7B",
        "messages": [{
            "role": "user",
            "content": [{
                "type": "audio_url",
                "audio_url": {"url": f"data:audio/wav;base64,{audio_b64}"}
            }]
        }]
    }
    async with self._session.post(self._api_url, json=payload) as resp:
        result = await resp.json()
        return result["choices"][0]["message"]["content"]
```

### 3. Response Parsing

The ASR returns content like `<|en|>Hello, how are you?`. Parse out the text:

```python
def _parse_asr_output(self, content: str) -> str:
    """Extract transcribed text from ASR response.

    Format: '<|language_code|>transcribed text'
    Example: '<|en|>Hello, how are you?'
    """
    # Try using official parser first
    try:
        from qwen_asr import parse_asr_output
        language, text = parse_asr_output(content)
        return text.strip()
    except ImportError:
        # Fallback: strip language tag manually
        import re
        text = re.sub(r'^<\|[a-z]{2}\|>', '', content).strip()
        return text
```

### 4. HTTP Session Management

Create a persistent `aiohttp.ClientSession` to avoid connection overhead per request:

- Create session in `start()` (Pipecat lifecycle method)
- Close session in `stop()`
- Do NOT create a new session per `run_stt` call

---

## Full Implementation Skeleton

```python
import base64
import struct
import io
import re
import aiohttp
from typing import AsyncGenerator

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.services.ai_services import STTService

class Qwen3STTService(STTService):
    """STT service that calls a Qwen3-ASR vLLM server."""

    def __init__(
        self,
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
        if not audio:
            return

        # Convert raw PCM to base64 WAV
        audio_b64 = self._pcm_to_wav_base64(audio)

        # Call ASR API
        payload = {
            "model": self._model,
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "audio_url",
                    "audio_url": {"url": f"data:audio/wav;base64,{audio_b64}"}
                }]
            }]
        }

        try:
            async with self._session.post(self._api_url, json=payload) as resp:
                if resp.status != 200:
                    # Log error but don't crash the pipeline
                    error_text = await resp.text()
                    # TODO: use proper Pipecat logger
                    print(f"ASR error ({resp.status}): {error_text}")
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
            print(f"ASR request failed: {e}")

    def _pcm_to_wav_base64(
        self,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        num_channels: int = 1,
        sample_width: int = 2,
    ) -> str:
        buf = io.BytesIO()
        data_size = len(audio_bytes)
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<IHHIIHH",
            16, 1, num_channels, sample_rate,
            sample_rate * num_channels * sample_width,
            num_channels * sample_width,
            sample_width * 8,
        ))
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(audio_bytes)
        return base64.b64encode(buf.getvalue()).decode()

    def _parse_asr_output(self, content: str) -> str:
        try:
            from qwen_asr import parse_asr_output
            _, text = parse_asr_output(content)
            return text.strip()
        except ImportError:
            return re.sub(r'^<\|[a-z]{2}\|>', '', content).strip()
```

---

## Important Notes

### Pipecat Version Compatibility

The base class API may differ between Pipecat versions. Key things to verify:

1. **Import path**: Could be `pipecat.services.ai_services.STTService` or `pipecat.services.stt.STTService`
2. **`run_stt` signature**: May accept additional params like `language`
3. **Frame types**: `TranscriptionFrame` fields may vary — check if `user_id` and `timestamp` are still required
4. **Lifecycle methods**: `start()`/`stop()` may take a `frame` argument or not

Run this to check:
```python
import pipecat
print(pipecat.__version__)
# Then inspect the actual STTService class
```

### Audio Sample Rate

WebRTC audio from Pipecat transport is typically 16kHz. If the transport uses a different rate, the WAV header must match. The sample rate can usually be obtained from the `InputAudioRawFrame.sample_rate` field. For now, hardcoding 16kHz is fine.

### Error Handling

- Do NOT let ASR errors crash the pipeline. Log and skip.
- If the ASR server is temporarily unavailable, the user just won't see their transcript — the conversation can continue when it recovers.

---

## Testing

### Unit Test (mock ASR server)

```python
import asyncio
from unittest.mock import AsyncMock, patch

async def test_stt_service():
    stt = Qwen3STTService(api_url="http://localhost:8001/v1/chat/completions")

    # Test WAV conversion
    fake_audio = b'\x00\x01' * 16000  # 1 second of fake audio
    wav_b64 = stt._pcm_to_wav_base64(fake_audio)
    assert len(wav_b64) > 0

    # Test ASR parsing
    assert stt._parse_asr_output("<|en|>Hello world") == "Hello world"
    assert stt._parse_asr_output("<|zh|>你好") == "你好"
    assert stt._parse_asr_output("") == ""
```

### Integration Test (requires BE-2 running)

```python
async def test_stt_integration():
    stt = Qwen3STTService()
    await stt.start(None)

    # Load a real speech WAV file
    with open("test_hello.wav", "rb") as f:
        # Skip WAV header (44 bytes) to get raw PCM
        f.read(44)
        audio = f.read()

    frames = []
    async for frame in stt.run_stt(audio):
        frames.append(frame)

    assert len(frames) > 0
    assert frames[0].text  # Should have transcribed text
    print(f"Transcribed: {frames[0].text}")

    await stt.stop(None)
```

---

## Dependencies

```
pipecat-ai[silero]
aiohttp
qwen-asr  # optional, for parse_asr_output
```

---

## Acceptance Criteria

- [ ] `Qwen3STTService` subclasses the correct Pipecat STT base class
- [ ] Raw PCM audio is correctly converted to WAV with proper header
- [ ] Base64-encoded WAV is sent to ASR API in the correct format
- [ ] ASR response is parsed correctly (language tag stripped)
- [ ] Empty/silent audio is handled gracefully (no crash, no empty transcription)
- [ ] HTTP session is reused across calls (not created per request)
- [ ] ASR errors are logged but don't crash the pipeline
- [ ] Unit tests pass for WAV conversion and response parsing
- [ ] Integration test passes with a real audio file against the ASR server
