# FE-1: Project Scaffold

**Directory:** `client/`
**Depends on:** None
**Team:** Frontend

---

## Objective

Set up the React + TypeScript + Vite project with all required dependencies and configuration. After this task, the frontend should compile and show a blank page at `http://localhost:5173`.

---

## Requirements

### 1. Create Vite Project

```bash
cd speakwell
npm create vite@latest client -- --template react-ts
cd client
npm install
```

### 2. Install Pipecat Dependencies

```bash
npm install @pipecat-ai/client-js @pipecat-ai/client-react @pipecat-ai/small-webrtc-transport
```

These packages provide:
- `@pipecat-ai/client-js` — Core Pipecat client library
- `@pipecat-ai/client-react` — React hooks and providers (`PipecatClientProvider`, `usePipecatClient`, `usePipecatConversation`)
- `@pipecat-ai/small-webrtc-transport` — WebRTC transport that connects to the backend's SmallWebRTC server

### 3. Vite Config — API Proxy

Configure Vite to proxy `/api` requests to the backend server (port 7860). This avoids CORS issues during development.

**`client/vite.config.ts`:**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:7860",
        changeOrigin: true,
      },
    },
  },
});
```

**Why the proxy?**
- The frontend runs on `localhost:5173` (Vite dev server)
- The backend runs on `localhost:7860` (FastAPI)
- Without the proxy, browser requests to `/api/offer` would go to port 5173 and fail
- The proxy rewrites `/api/*` → `http://localhost:7860/api/*`

### 4. Clean Up Default Vite Content

Remove the default Vite boilerplate:
- Clear `src/App.tsx` — replace with a minimal component (will be built out in FE-2)
- Clear `src/App.css` — empty or minimal reset styles
- Clear `src/index.css` — keep only CSS reset/base styles
- Remove `src/assets/react.svg` and the Vite logo reference

**Minimal `src/App.tsx`:**

```tsx
function App() {
  return (
    <div className="app">
      <h1>SpeakWell</h1>
      <p>English conversation practice with AI</p>
    </div>
  );
}

export default App;
```

**Minimal `src/main.tsx`:**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

### 5. Base CSS Reset

**`src/index.css`:**

```css
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html,
body {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#root {
  height: 100%;
}
```

### 6. TypeScript Config

The default Vite TypeScript config should be fine. Verify that `tsconfig.json` has `"strict": true` and proper module resolution.

### 7. Project Structure

After setup, the `client/` directory should look like:

```
client/
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json (or tsconfig.app.json)
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── App.css
│   ├── index.css
│   ├── components/      ← create empty directory
│   │   └── .gitkeep
│   └── vite-env.d.ts
└── public/
```

---

## Verification

```bash
cd client

# Install dependencies
npm install

# Type check
npx tsc --noEmit

# Dev server starts
npm run dev
# → Opens at http://localhost:5173
# → Should show "SpeakWell" heading

# Build succeeds
npm run build
```

---

## Acceptance Criteria

- [ ] `npm install` completes without errors
- [ ] `npm run dev` starts dev server at `http://localhost:5173`
- [ ] Page shows "SpeakWell" heading (no Vite boilerplate)
- [ ] `npx tsc --noEmit` passes with no type errors
- [ ] `npm run build` succeeds
- [ ] Vite proxy is configured: requests to `/api/*` forward to `localhost:7860`
- [ ] Pipecat packages are installed (`@pipecat-ai/client-js`, `@pipecat-ai/client-react`, `@pipecat-ai/small-webrtc-transport`)
- [ ] `src/components/` directory exists for future components
