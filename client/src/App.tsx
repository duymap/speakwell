import { useMemo, useEffect, useState, useCallback } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import {
  PipecatClientProvider,
  PipecatClientAudio,
  usePipecatClientTransportState,
} from "@pipecat-ai/client-react";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { ChatInterface } from "./components/ChatInterface";
import { AudioIndicator } from "./components/AudioIndicator";
import "./App.css";

// ─── Theme hook ───────────────────────────────────────────────────────────────
type Theme = "dark" | "light";

function useTheme(): [Theme, () => void] {
  const getInitial = (): Theme => {
    const stored = localStorage.getItem("sw-theme") as Theme | null;
    if (stored) return stored;
    return window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  };

  const [theme, setTheme] = useState<Theme>(getInitial);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("sw-theme", theme);
  }, [theme]);

  const toggle = useCallback(
    () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    []
  );

  return [theme, toggle];
}

// ─── Inner shell (needs transport state) ─────────────────────────────────────
function AppShell() {
  const transportState = usePipecatClientTransportState();
  const [theme, toggleTheme] = useTheme();
  const isConnected =
    transportState === "connected" || transportState === "ready";

  return (
    <main className="app">
      <header className="app-header">
        <div className="app-header-left">
          <div className="app-header-icon">🎙</div>
          <div className="app-header-brand">
            <h1>
              Speak<span>Well</span>
            </h1>
            <p className="app-header-subtitle">AI English Tutor</p>
          </div>
        </div>

        <div className="app-header-right">
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>

          <div className={`app-header-status ${isConnected ? "status-online" : ""}`}>
            <span className="status-dot" />
            {isConnected ? "Live" : "Offline"}
          </div>
        </div>
      </header>

      <ChatInterface />

      <footer className="app-footer">
        <AudioIndicator />
      </footer>
    </main>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────
function App() {
  const client = useMemo(
    () =>
      new PipecatClient({
        transport: new SmallWebRTCTransport(),
        enableMic: true,
      }),
    []
  );

  return (
    <PipecatClientProvider client={client}>
      <PipecatClientAudio />
      <AppShell />
    </PipecatClientProvider>
  );
}

export default App;
