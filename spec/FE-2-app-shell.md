# FE-2: App Shell — Pipecat Provider Setup

**File:** `client/src/App.tsx`
**Depends on:** FE-1 (project scaffold)
**Team:** Frontend

---

## Objective

Set up the `PipecatClientProvider` and `PipecatClientAudio` components that wrap the entire app. These provide the WebRTC connection context and audio playback that all child components will use.

After this task, the app won't look different visually, but the Pipecat infrastructure will be in place for FE-3 and FE-4 to build on.

---

## Background: Pipecat React SDK

The Pipecat React SDK provides:

| Export | Purpose |
|--------|---------|
| `PipecatClientProvider` | React context provider. Wraps the app and manages the Pipecat client instance. |
| `PipecatClientAudio` | Hidden `<audio>` element that plays the bot's audio output. Must be rendered inside the provider. |
| `usePipecatClient()` | Hook to access the client instance (connect, disconnect, get state). |
| `usePipecatConversation()` | Hook to access the conversation transcript (messages array). |
| `SmallWebRTCTransport` | Transport class passed to the provider — handles WebRTC signaling. |

### How Connection Works

1. User clicks "Connect" → calls `client.connect()`
2. `SmallWebRTCTransport` sends an SDP offer to the backend's `/api/offer` endpoint
3. Backend returns an SDP answer
4. WebRTC peer connection is established
5. Audio flows bidirectionally: mic → backend, backend → speaker

---

## Requirements

### 1. Transport Configuration

Create and configure the `SmallWebRTCTransport`:

```tsx
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";

const transport = new SmallWebRTCTransport();
```

The transport needs to know the signaling endpoint. Check the SDK docs — it may be:
- Passed to the transport constructor: `new SmallWebRTCTransport({ signalingUrl: "/api/offer" })`
- Passed at connect time: `client.connect({ endpoint: "/api/offer" })`
- Configured on the provider: `<PipecatClientProvider config={{ ... }}>`

**Verify with:**
```bash
# Check the package's README or types
cat node_modules/@pipecat-ai/small-webrtc-transport/README.md
# or
cat node_modules/@pipecat-ai/small-webrtc-transport/dist/index.d.ts
```

### 2. Provider Setup

Wrap the app with `PipecatClientProvider`:

```tsx
import { PipecatClientProvider, PipecatClientAudio } from "@pipecat-ai/client-react";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { ChatInterface } from "./components/ChatInterface";

function App() {
  const transport = new SmallWebRTCTransport();

  return (
    <PipecatClientProvider transport={transport}>
      <PipecatClientAudio />
      <main className="app">
        <h1>SpeakWell</h1>
        {/* ChatInterface will be built in FE-3 */}
        {/* AudioIndicator will be built in FE-4 */}
        <p>Ready to connect</p>
      </main>
    </PipecatClientProvider>
  );
}

export default App;
```

**Important considerations:**
- `PipecatClientAudio` renders a hidden `<audio>` element. Without it, you won't hear the bot's voice.
- The transport should ideally be created once (not on every render). Use `useMemo` or create outside the component:

```tsx
// Option A: outside component
const transport = new SmallWebRTCTransport();

function App() {
  return (
    <PipecatClientProvider transport={transport}>
      ...
    </PipecatClientProvider>
  );
}

// Option B: useMemo
function App() {
  const transport = useMemo(() => new SmallWebRTCTransport(), []);
  return (
    <PipecatClientProvider transport={transport}>
      ...
    </PipecatClientProvider>
  );
}
```

### 3. Verify Hooks Work

Create a temporary test component to verify the provider is working:

```tsx
function ConnectionStatus() {
  const client = usePipecatClient();

  // The client should exist (not null/undefined)
  // State should be "idle" or "disconnected" initially
  return <p>Client state: {client ? "initialized" : "not available"}</p>;
}
```

Place this inside the provider temporarily to verify it doesn't throw.

### 4. App Layout Structure

Set up the basic layout that FE-3 and FE-4 will build into:

```tsx
<PipecatClientProvider transport={transport}>
  <PipecatClientAudio />
  <main className="app">
    <header className="app-header">
      <h1>SpeakWell</h1>
      <p>Practice English with AI</p>
    </header>
    <section className="chat-container">
      {/* FE-3: ChatInterface goes here */}
    </section>
    <footer className="app-footer">
      {/* FE-4: AudioIndicator goes here */}
      {/* FE-3: Connect/Disconnect button goes here */}
    </footer>
  </main>
</PipecatClientProvider>
```

---

## API Reference

Check the actual types exported by the SDK. Expected (may vary by version):

```typescript
// @pipecat-ai/client-react
export function PipecatClientProvider(props: {
  transport: Transport;
  children: React.ReactNode;
}): JSX.Element;

export function PipecatClientAudio(): JSX.Element;

export function usePipecatClient(): {
  connect(options?: { endpoint?: string }): Promise<void>;
  disconnect(): Promise<void>;
  state: "idle" | "connecting" | "connected" | "disconnecting" | "disconnected";
};

export function usePipecatConversation(): {
  messages: Array<{
    role: "user" | "assistant";
    parts: Array<{ text: string | { spoken: string } }>;
  }>;
};
```

**Always check the actual package types** — the above is approximate.

---

## Testing

### Manual

1. `npm run dev` — app loads without React errors in console
2. No "missing provider" errors
3. Temporary `ConnectionStatus` component renders "initialized"
4. `PipecatClientAudio` renders (check DOM for a hidden `<audio>` element)

### Type Check

```bash
npx tsc --noEmit
# Should pass with no errors
```

---

## Acceptance Criteria

- [ ] `PipecatClientProvider` wraps the app with a `SmallWebRTCTransport` instance
- [ ] `PipecatClientAudio` is rendered inside the provider
- [ ] Transport instance is created once (not on every render)
- [ ] `usePipecatClient()` hook works inside child components (returns a client object)
- [ ] No console errors on page load
- [ ] Type check passes
- [ ] Basic app layout structure is in place for FE-3 and FE-4 to build into
