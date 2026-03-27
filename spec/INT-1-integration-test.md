# INT-1: End-to-End Integration Test

**Depends on:** BE-6 (pipeline server), FE-5 (polished frontend)
**Team:** Backend + Frontend

---

## Objective

Verify the full system works end-to-end: a user opens the browser, connects, speaks English, sees their transcript, hears the AI tutor respond, and sees the tutor's transcript. This is the final validation before the app is ready.

---

## Prerequisites

All four servers must be running:

```bash
# Terminal 1: Qwen3-ASR server (GPU)
qwen-asr-serve Qwen/Qwen3-ASR-1.7B --gpu-memory-utilization 0.8 --host 0.0.0.0 --port 8001

# Terminal 2: Qwen3-TTS server (GPU)
cd server && uvicorn tts_server:app --host 0.0.0.0 --port 8002

# Terminal 3: Pipecat pipeline server
export OPENAI_API_KEY=sk-...
cd server && uvicorn bot:app --host 0.0.0.0 --port 7860

# Terminal 4: React frontend
cd client && npm run dev
```

---

## Test Scenarios

### Test 1: Basic Connection

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Open `http://localhost:5173` | App loads, shows "Start Conversation" button |
| 2 | Click "Start Conversation" | Browser asks for mic permission |
| 3 | Grant mic permission | Button changes to "End Conversation" |
| 4 | Wait 2-3 seconds | Bot speaks a greeting, greeting appears in transcript |
| 5 | Audio indicator shows "Tutor is speaking..." | Visual feedback during bot speech |

**Pass criteria:** Bot greeting is heard through speakers AND visible in transcript.

### Test 2: User Speech Recognition

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | (Connected from Test 1) | |
| 2 | Say "Hello, my name is Alex" | Audio indicator shows "You're speaking..." |
| 3 | Stop speaking | Your text appears in transcript: "Hello, my name is Alex" (or close) |
| 4 | Wait 2-5 seconds | Bot responds with a relevant reply |

**Pass criteria:** User speech is transcribed accurately and bot response is contextually appropriate.

### Test 3: Conversation Flow

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Say "I want to practice talking about my hobbies" | Transcribed and bot asks about hobbies |
| 2 | Say "I like to play the guitar" | Bot responds about guitar/music |
| 3 | Say "Yesterday I go to the concert" (intentional grammar error) | Bot gently corrects: "went to the concert" |
| 4 | Have 3-4 more exchanges | Conversation flows naturally |

**Pass criteria:** Multi-turn conversation works, grammar correction happens naturally.

### Test 4: Interruption

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Wait for bot to start a long response | Bot is speaking |
| 2 | Start speaking mid-response | Bot audio stops immediately |
| 3 | Finish your sentence | Your speech is transcribed, bot responds to it |

**Pass criteria:** Bot stops speaking when interrupted, responds to the new input.

### Test 5: Disconnect & Reconnect

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Click "End Conversation" | Button changes to "Start Conversation" |
| 2 | Verify audio stops | No more bot audio |
| 3 | Click "Start Conversation" again | New connection established |
| 4 | Bot sends a new greeting | Fresh conversation starts |

**Pass criteria:** Clean disconnect and reconnect without errors.

### Test 6: Error Recovery

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Stop the pipeline server (Ctrl+C on Terminal 3) | |
| 2 | Click "Start Conversation" | Error message: "Connection failed" |
| 3 | Restart the pipeline server | |
| 4 | Click "Retry" or "Start Conversation" | Connection succeeds |

**Pass criteria:** App handles server downtime gracefully with clear error message.

### Test 7: Performance

Measure these latencies during a conversation:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| User speech → transcript appears | < 3 seconds | Stopwatch from end of speech to text appearing |
| User speech → bot starts speaking | < 5 seconds | Stopwatch from end of speech to hearing bot audio |
| Bot text → bot audio sync | < 1 second | Transcript and audio should be roughly in sync |
| Overall round-trip | < 8 seconds | From user stops talking to bot finishes responding |

**Note:** These are aspirational targets. Document actual measurements even if they exceed targets.

---

## Bug Report Template

If a test fails, document it:

```markdown
### Bug: [Short description]

**Test:** Test N — [name]
**Step:** Step N
**Expected:** [what should happen]
**Actual:** [what happened]
**Logs:** [paste relevant console/server output]
**Screenshot:** [if applicable]
**Severity:** Critical / Major / Minor
```

---

## Known Issues to Watch For

1. **Audio echo**: If the user doesn't use headphones, the bot's audio may be picked up by the mic and transcribed, creating a feedback loop. This is expected without echo cancellation.
2. **WebRTC ICE failures**: If running on a network with restrictive firewalls, WebRTC may fail to establish a direct connection.
3. **First response delay**: The first TTS request may be slower due to model warmup.
4. **Sample rate mismatch**: If the TTS outputs 12kHz but WebRTC expects 16kHz, audio may sound distorted (chipmunk or slow). This indicates BE-4's resampling is needed.

---

## Acceptance Criteria

- [ ] Test 1 passes: Basic connection and bot greeting
- [ ] Test 2 passes: User speech is transcribed
- [ ] Test 3 passes: Multi-turn conversation with grammar correction
- [ ] Test 4 passes: Interruption works
- [ ] Test 5 passes: Disconnect and reconnect
- [ ] Test 6 passes: Error recovery
- [ ] Test 7 documented: Latency measurements recorded
- [ ] No console errors during normal conversation flow
- [ ] No server crashes during normal conversation flow
