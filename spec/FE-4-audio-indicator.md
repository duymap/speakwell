# FE-4: Audio Indicator — Visual Speaking/Listening State

**File:** `client/src/components/AudioIndicator.tsx`
**Depends on:** FE-2 (app shell with Pipecat provider)
**Team:** Frontend

---

## Objective

Build a visual component that shows the current conversation state:
- **Idle:** No animation (not connected)
- **Listening:** Subtle pulse animation (connected, waiting for user to speak)
- **User speaking:** Active waveform/pulse (user's mic is picking up voice)
- **Bot speaking:** Different animation (bot is playing audio response)

This gives the user clear feedback about what's happening, which is critical for voice-only interactions.

---

## Background: Pipecat Client Events

The Pipecat client SDK exposes state information about audio activity. Check the SDK for available hooks or events:

```typescript
// Possible APIs (verify against actual SDK):
const client = usePipecatClient();

// Option 1: State property
client.state // "idle" | "connecting" | "connected" | ...

// Option 2: Events/callbacks
client.on("botStartedSpeaking", () => { ... });
client.on("botStoppedSpeaking", () => { ... });
client.on("userStartedSpeaking", () => { ... });
client.on("userStoppedSpeaking", () => { ... });

// Option 3: Dedicated hook
const { isBotSpeaking, isUserSpeaking } = usePipecatMediaState();
```

**You must check the actual SDK exports.** Run:
```bash
# Check available exports
grep -r "export" node_modules/@pipecat-ai/client-react/dist/index.d.ts
```

If the SDK doesn't provide speaking-state hooks, you can detect audio activity from:
1. The Web Audio API (analyze mic input levels)
2. Pipecat events on the transport

---

## Requirements

### 1. State Detection

Determine the current audio state. Priority order for detection:

**Option A — SDK provides hooks (preferred):**
```tsx
// If something like this exists:
const { isBotSpeaking, isUserSpeaking } = useSomePipecatHook();

type AudioState = "idle" | "listening" | "userSpeaking" | "botSpeaking";

const getAudioState = (): AudioState => {
  if (!isConnected) return "idle";
  if (isUserSpeaking) return "userSpeaking";
  if (isBotSpeaking) return "botSpeaking";
  return "listening";
};
```

**Option B — Use transport events:**
```tsx
const [audioState, setAudioState] = useState<AudioState>("idle");

useEffect(() => {
  const client = usePipecatClient();
  // Register event listeners (check actual API)
  client.on?.("botStartedSpeaking", () => setAudioState("botSpeaking"));
  client.on?.("botStoppedSpeaking", () => setAudioState("listening"));
  client.on?.("userStartedSpeaking", () => setAudioState("userSpeaking"));
  client.on?.("userStoppedSpeaking", () => setAudioState("listening"));
  // Cleanup
  return () => { /* remove listeners */ };
}, []);
```

**Option C — Fallback (connected vs idle only):**
```tsx
// Simplest version if no speaking events are available
const audioState = isConnected ? "listening" : "idle";
```

### 2. Visual Design

Create a circular indicator that changes based on state:

| State | Visual | Color | Animation |
|-------|--------|-------|-----------|
| `idle` | Static circle | Gray (#ccc) | None |
| `listening` | Gentle pulse | Blue (#1976d2) | Slow pulse (2s cycle) |
| `userSpeaking` | Active rings | Green (#4caf50) | Expanding rings |
| `botSpeaking` | Waveform bars | Purple (#7b1fa2) | Oscillating bars |

### 3. CSS Animations

```css
/* Listening pulse */
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.15); opacity: 0.7; }
}

/* User speaking - expanding rings */
@keyframes ripple {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(2); opacity: 0; }
}

/* Bot speaking - bar oscillation */
@keyframes oscillate {
  0%, 100% { height: 8px; }
  50% { height: 24px; }
}
```

### 4. State Label

Show a text label below the indicator:

| State | Label |
|-------|-------|
| `idle` | "" (empty) |
| `listening` | "Listening..." |
| `userSpeaking` | "You're speaking..." |
| `botSpeaking` | "Tutor is speaking..." |

---

## Implementation Skeleton

```tsx
// client/src/components/AudioIndicator.tsx

import { usePipecatClient } from "@pipecat-ai/client-react";
import "./AudioIndicator.css";

type AudioState = "idle" | "listening" | "userSpeaking" | "botSpeaking";

interface AudioIndicatorProps {
  audioState?: AudioState; // Allow parent to override if needed
}

export function AudioIndicator({ audioState: overrideState }: AudioIndicatorProps) {
  const client = usePipecatClient();

  // Determine state (adjust based on actual SDK API)
  const audioState: AudioState = overrideState
    ?? (client.state === "connected" ? "listening" : "idle");

  const labels: Record<AudioState, string> = {
    idle: "",
    listening: "Listening...",
    userSpeaking: "You're speaking...",
    botSpeaking: "Tutor is speaking...",
  };

  return (
    <div className={`audio-indicator audio-indicator-${audioState}`}>
      <div className="indicator-visual">
        {audioState === "botSpeaking" ? (
          // Oscillating bars for bot speaking
          <div className="bars">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="bar"
                style={{ animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
        ) : (
          // Circle with optional ripple for other states
          <div className="circle">
            {audioState === "userSpeaking" && (
              <>
                <div className="ripple ripple-1" />
                <div className="ripple ripple-2" />
              </>
            )}
          </div>
        )}
      </div>
      {labels[audioState] && (
        <p className="indicator-label">{labels[audioState]}</p>
      )}
    </div>
  );
}
```

### CSS (`AudioIndicator.css`)

```css
.audio-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
}

.indicator-visual {
  position: relative;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Circle indicator */
.circle {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #ccc;
  position: relative;
}

/* Idle - static gray */
.audio-indicator-idle .circle {
  background: #ccc;
}

/* Listening - blue pulse */
.audio-indicator-listening .circle {
  background: #1976d2;
  animation: pulse 2s ease-in-out infinite;
}

/* User speaking - green with ripples */
.audio-indicator-userSpeaking .circle {
  background: #4caf50;
}

.ripple {
  position: absolute;
  top: 0;
  left: 0;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 2px solid #4caf50;
  animation: ripple 1.5s ease-out infinite;
}

.ripple-2 {
  animation-delay: 0.5s;
}

/* Bot speaking - bars */
.bars {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 32px;
}

.bar {
  width: 6px;
  height: 8px;
  background: #7b1fa2;
  border-radius: 3px;
  animation: oscillate 0.8s ease-in-out infinite;
}

/* Label */
.indicator-label {
  font-size: 0.85rem;
  color: #666;
}

/* Animations */
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.15); opacity: 0.7; }
}

@keyframes ripple {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(2); opacity: 0; }
}

@keyframes oscillate {
  0%, 100% { height: 8px; }
  50% { height: 24px; }
}
```

---

## Integration with App.tsx

Add to the app layout (from FE-2):

```tsx
import { AudioIndicator } from "./components/AudioIndicator";

// Inside the provider, above or below ChatInterface:
<footer className="app-footer">
  <AudioIndicator />
</footer>
```

---

## Testing

### Visual Testing (no backend needed)

Test each state by temporarily hardcoding the `audioState` prop:

```tsx
// Test all states
<AudioIndicator audioState="idle" />
<AudioIndicator audioState="listening" />
<AudioIndicator audioState="userSpeaking" />
<AudioIndicator audioState="botSpeaking" />
```

Verify:
- [ ] Idle: gray static circle, no label
- [ ] Listening: blue pulsing circle, "Listening..." label
- [ ] User speaking: green circle with ripple rings, "You're speaking..." label
- [ ] Bot speaking: purple oscillating bars, "Tutor is speaking..." label
- [ ] Animations are smooth (60fps)

### With Backend

- Connect to the backend and verify the state transitions happen automatically
- Speak → indicator changes to "userSpeaking"
- Stop speaking → bot responds → indicator changes to "botSpeaking"
- Bot finishes → returns to "listening"

---

## Acceptance Criteria

- [ ] Component renders four distinct visual states
- [ ] Animations are smooth and not janky
- [ ] State labels are correct for each state
- [ ] Works with `audioState` prop (for testing) and auto-detection (for production)
- [ ] No TypeScript errors
- [ ] CSS animations use `transform`/`opacity` only (GPU-accelerated, performant)
