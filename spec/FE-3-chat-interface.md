# FE-3: Chat Interface — Transcript & Controls

**File:** `client/src/components/ChatInterface.tsx`
**Depends on:** FE-2 (app shell with Pipecat provider)
**Team:** Frontend

---

## Objective

Build the main UI component that:
1. Shows a "Start Conversation" / "End Conversation" button
2. Manages the WebRTC connection lifecycle
3. Displays the live conversation transcript (user speech and bot responses)

---

## Background: Pipecat Client Lifecycle

```
[Idle] → click Start → [Connecting] → WebRTC established → [Connected]
                                                                  │
                                                         user speaks ↔ bot responds
                                                                  │
                                        click End → [Disconnecting] → [Idle]
```

The `usePipecatClient()` hook provides `connect()`, `disconnect()`, and `state`.
The `usePipecatConversation()` hook provides `messages` — an array that updates in real-time as the user speaks and the bot responds.

---

## Requirements

### 1. Connection Control

```tsx
import { usePipecatClient } from "@pipecat-ai/client-react";

function ChatInterface() {
  const client = usePipecatClient();

  const handleConnect = async () => {
    try {
      await client.connect({ endpoint: "/api/offer" });
    } catch (error) {
      console.error("Connection failed:", error);
    }
  };

  const handleDisconnect = async () => {
    await client.disconnect();
  };
}
```

**Connect flow:**
1. User clicks "Start Conversation"
2. Browser prompts for microphone permission (first time only)
3. WebRTC connection is established with the backend
4. Bot sends initial greeting (audio + transcript)

**Important:** The `endpoint` path for `connect()` must match the Vite proxy config (`/api/offer` → backend port 7860). Verify the exact parameter name — it may be `endpoint`, `url`, `signalingUrl`, etc. Check the SDK types.

### 2. Connection Button States

| Client State | Button Text | Button Action | Button Style |
|-------------|-------------|---------------|--------------|
| `idle` / `disconnected` | "Start Conversation" | `connect()` | Primary (green/blue) |
| `connecting` | "Connecting..." | disabled | Muted/loading |
| `connected` | "End Conversation" | `disconnect()` | Danger (red) |
| `disconnecting` | "Disconnecting..." | disabled | Muted/loading |

```tsx
const isConnected = client.state === "connected";
const isTransitioning = client.state === "connecting" || client.state === "disconnecting";

<button
  onClick={isConnected ? handleDisconnect : handleConnect}
  disabled={isTransitioning}
  className={`connect-btn ${isConnected ? "connected" : ""}`}
>
  {client.state === "connecting" && "Connecting..."}
  {client.state === "connected" && "End Conversation"}
  {client.state === "disconnecting" && "Disconnecting..."}
  {(client.state === "idle" || client.state === "disconnected") && "Start Conversation"}
</button>
```

### 3. Transcript Display

```tsx
import { usePipecatConversation } from "@pipecat-ai/client-react";

function ChatInterface() {
  const { messages } = usePipecatConversation();

  return (
    <div className="transcript">
      {messages.map((msg, index) => (
        <div key={index} className={`message message-${msg.role}`}>
          <span className="message-role">
            {msg.role === "user" ? "You" : "Tutor"}
          </span>
          <span className="message-text">
            {msg.parts?.map((part, j) => {
              const text = typeof part.text === "string"
                ? part.text
                : part.text?.spoken || "";
              return <span key={j}>{text}</span>;
            })}
          </span>
        </div>
      ))}
    </div>
  );
}
```

**Message structure (check actual SDK types):**
```typescript
interface Message {
  role: "user" | "assistant";
  parts: Array<{
    text: string | { spoken: string; written?: string };
  }>;
}
```

The `text` field may be:
- A plain string (simple case)
- An object with `spoken` (what was said) and optionally `written` (formatted text)
- Always check the actual SDK types and handle both cases

### 4. Auto-Scroll

The transcript should auto-scroll to the latest message:

```tsx
import { useRef, useEffect } from "react";

function ChatInterface() {
  const { messages } = usePipecatConversation();
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="transcript" ref={transcriptRef}>
      {/* messages */}
    </div>
  );
}
```

### 5. Empty States

Show appropriate content when:

- **Not connected:** "Click 'Start Conversation' to begin practicing English with your AI tutor."
- **Connected, no messages yet:** "Listening... Say hello!" (brief moment before bot greeting arrives)
- **Microphone denied:** "Microphone access is required. Please allow microphone access and try again."

### 6. Error Handling

Handle connection failures gracefully:

```tsx
const [error, setError] = useState<string | null>(null);

const handleConnect = async () => {
  setError(null);
  try {
    await client.connect({ endpoint: "/api/offer" });
  } catch (err) {
    if (err instanceof DOMException && err.name === "NotAllowedError") {
      setError("Microphone access was denied. Please allow microphone access in your browser settings.");
    } else {
      setError("Failed to connect. Make sure the server is running and try again.");
    }
  }
};
```

---

## Component Structure

```tsx
// client/src/components/ChatInterface.tsx

import { useState, useRef, useEffect } from "react";
import { usePipecatClient, usePipecatConversation } from "@pipecat-ai/client-react";
import "./ChatInterface.css";

export function ChatInterface() {
  const client = usePipecatClient();
  const { messages } = usePipecatConversation();
  const [error, setError] = useState<string | null>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);

  const isConnected = client.state === "connected";
  const isTransitioning = client.state === "connecting" || client.state === "disconnecting";

  // Auto-scroll on new messages
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [messages]);

  const handleConnect = async () => {
    setError(null);
    try {
      await client.connect({ endpoint: "/api/offer" });
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setError("Microphone access was denied. Please allow it and try again.");
      } else {
        setError("Connection failed. Is the server running?");
      }
    }
  };

  const handleDisconnect = async () => {
    await client.disconnect();
  };

  return (
    <div className="chat-interface">
      {/* Transcript area */}
      <div className="transcript" ref={transcriptRef}>
        {!isConnected && messages.length === 0 && (
          <div className="empty-state">
            <p>Click "Start Conversation" to begin practicing English with your AI tutor.</p>
          </div>
        )}

        {messages.map((msg, index) => (
          <div key={index} className={`message message-${msg.role}`}>
            <span className="message-role">
              {msg.role === "user" ? "You" : "Tutor"}
            </span>
            <span className="message-text">
              {msg.parts?.map((part, j) => {
                const text = typeof part.text === "string"
                  ? part.text
                  : part.text?.spoken || "";
                return <span key={j}>{text}</span>;
              })}
            </span>
          </div>
        ))}
      </div>

      {/* Error display */}
      {error && <div className="error-message">{error}</div>}

      {/* Controls */}
      <div className="controls">
        <button
          onClick={isConnected ? handleDisconnect : handleConnect}
          disabled={isTransitioning}
          className={`connect-btn ${isConnected ? "connected" : ""}`}
        >
          {client.state === "connecting" && "Connecting..."}
          {client.state === "connected" && "End Conversation"}
          {client.state === "disconnecting" && "Disconnecting..."}
          {(client.state === "idle" || client.state === "disconnected") && "Start Conversation"}
        </button>
      </div>
    </div>
  );
}
```

### Basic CSS (`ChatInterface.css`)

```css
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.transcript {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.message {
  margin-bottom: 0.75rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
}

.message-user {
  background: #e3f2fd;
  margin-left: 2rem;
}

.message-assistant {
  background: #f5f5f5;
  margin-right: 2rem;
}

.message-role {
  font-weight: 600;
  margin-right: 0.5rem;
  font-size: 0.85rem;
  text-transform: uppercase;
  color: #666;
}

.message-text {
  line-height: 1.5;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #888;
  text-align: center;
  padding: 2rem;
}

.error-message {
  padding: 0.75rem 1rem;
  background: #ffebee;
  color: #c62828;
  border-radius: 4px;
  margin: 0 1rem;
}

.controls {
  padding: 1rem;
  display: flex;
  justify-content: center;
}

.connect-btn {
  padding: 0.75rem 2rem;
  border: none;
  border-radius: 24px;
  font-size: 1rem;
  cursor: pointer;
  background: #1976d2;
  color: white;
  transition: background 0.2s;
}

.connect-btn:hover:not(:disabled) {
  background: #1565c0;
}

.connect-btn.connected {
  background: #d32f2f;
}

.connect-btn.connected:hover:not(:disabled) {
  background: #c62828;
}

.connect-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
```

---

## Integration with App.tsx

Update `App.tsx` (from FE-2) to include this component:

```tsx
import { ChatInterface } from "./components/ChatInterface";

// Inside the provider:
<main className="app">
  <header className="app-header">
    <h1>SpeakWell</h1>
  </header>
  <ChatInterface />
</main>
```

---

## Testing

### Without Backend (UI only)

1. Verify the component renders without crashing
2. Button shows "Start Conversation" in idle state
3. Clicking "Start Conversation" without backend shows error message
4. Empty state message is visible

### With Backend Running (E2E)

1. Click "Start Conversation" → mic permission dialog appears
2. After granting mic → button changes to "End Conversation"
3. Bot greeting appears in transcript
4. Speak → your text appears in transcript
5. Bot responds → response appears in transcript
6. Click "End Conversation" → button returns to "Start Conversation"

---

## Acceptance Criteria

- [ ] Connect/disconnect button with correct states
- [ ] Transcript displays user and bot messages in real-time
- [ ] Auto-scroll to latest message
- [ ] Empty state shown when not connected
- [ ] Error message shown on connection failure
- [ ] Mic permission denial handled with user-friendly message
- [ ] Component is exported and usable from `App.tsx`
- [ ] No TypeScript errors
