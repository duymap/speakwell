import { useMemo } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import {
  PipecatClientProvider,
  PipecatClientAudio,
} from "@pipecat-ai/client-react";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { ChatInterface } from "./components/ChatInterface";
import { AudioIndicator } from "./components/AudioIndicator";
import "./App.css";

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
      <main className="app">
        <header className="app-header">
          <h1>SpeakWell</h1>
          <p>Practice English with AI</p>
        </header>
        <ChatInterface />
        <footer className="app-footer">
          <AudioIndicator />
        </footer>
      </main>
    </PipecatClientProvider>
  );
}

export default App;
