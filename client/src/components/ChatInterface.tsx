import { useState, useRef, useEffect } from "react";
import {
  usePipecatClient,
  usePipecatConversation,
  usePipecatClientTransportState,
} from "@pipecat-ai/client-react";
import type { ConversationMessage } from "@pipecat-ai/client-react";
import "./ChatInterface.css";

type ErrorKind = "mic_denied" | "server_error" | "connection_lost" | null;

function getMessageText(msg: ConversationMessage): string {
  return (
    msg.parts
      ?.map((part) => {
        if (typeof part.text === "string") return part.text;
        if (part.text && typeof part.text === "object" && "spoken" in part.text)
          return (part.text as { spoken: string }).spoken;
        return "";
      })
      .join("") ?? ""
  );
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export function ChatInterface() {
  const client = usePipecatClient();
  const transportState = usePipecatClientTransportState();
  const { messages } = usePipecatConversation();
  const [errorKind, setErrorKind] = useState<ErrorKind>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const prevStateRef = useRef(transportState);

  const isConnected =
    transportState === "connected" || transportState === "ready";
  const isConnecting =
    transportState === "connecting" ||
    transportState === "initializing" ||
    transportState === "authenticating";
  const isTransitioning = isConnecting || transportState === "disconnecting";

  // Detect unexpected disconnection
  useEffect(() => {
    const prev = prevStateRef.current;
    if (
      (prev === "connected" || prev === "ready") &&
      transportState === "disconnected"
    ) {
      setErrorKind("connection_lost");
    }
    prevStateRef.current = transportState;
  }, [transportState]);

  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [messages]);

  const handleConnect = async () => {
    if (!client) return;
    setErrorKind(null);
    try {
      await client.connect({
        webrtcRequestParams: { endpoint: `${import.meta.env.VITE_API_BASE_URL}/api/offer` },
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setErrorKind("mic_denied");
      } else {
        setErrorKind("server_error");
      }
    }
  };

  const handleDisconnect = async () => {
    if (!client) return;
    await client.disconnect();
    setErrorKind(null);
  };

  const getButtonText = () => {
    if (isConnecting) return "Connecting...";
    if (transportState === "disconnecting") return "Disconnecting...";
    if (isConnected) return "End Conversation";
    return "Start Conversation";
  };

  return (
    <div className="chat-interface">
      <div className="transcript" ref={transcriptRef}>
        {/* Connecting spinner */}
        {isConnecting && (
          <div className="connecting-state">
            <div className="spinner" />
            <p>Setting up your conversation...</p>
          </div>
        )}

        {/* Empty: not connected */}
        {!isConnected && !isConnecting && messages.length === 0 && !errorKind && (
          <div className="empty-state">
            <p>
              Click &ldquo;Start Conversation&rdquo; to begin practicing
              English with your AI tutor.
            </p>
          </div>
        )}

        {/* Empty: connected but no messages yet */}
        {isConnected && messages.length === 0 && (
          <div className="empty-state">
            <p>Listening... Say hello!</p>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, index) => {
          const text = getMessageText(msg);
          if (!text) return null;
          return (
            <div key={index} className={`message message-${msg.role}`}>
              <div className="message-header">
                <span className="message-role">
                  {msg.role === "user" ? "You" : "Tutor"}
                </span>
                {msg.createdAt && (
                  <span className="message-time">
                    {formatTime(msg.createdAt)}
                  </span>
                )}
              </div>
              <div className="message-text">{text}</div>
            </div>
          );
        })}
      </div>

      {/* Error states */}
      {errorKind === "mic_denied" && (
        <div className="error-banner">
          <div className="error-title">Microphone Access Required</div>
          <p>SpeakWell needs microphone access to have a conversation.</p>
          <div className="error-actions">
            <button className="btn-secondary" onClick={handleConnect}>
              Try Again
            </button>
          </div>
        </div>
      )}

      {errorKind === "server_error" && (
        <div className="error-banner">
          <div className="error-title">Connection Failed</div>
          <p>Could not connect to the server. Please try again.</p>
          <div className="error-actions">
            <button className="btn-secondary" onClick={handleConnect}>
              Retry
            </button>
          </div>
        </div>
      )}

      {errorKind === "connection_lost" && (
        <div className="error-banner">
          <div className="error-title">Connection Lost</div>
          <p>The conversation was interrupted. Your transcript is preserved above.</p>
          <div className="error-actions">
            <button className="btn-secondary" onClick={handleConnect}>
              Reconnect
            </button>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="controls">
        <button
          onClick={isConnected ? handleDisconnect : handleConnect}
          disabled={isTransitioning || !client}
          className={`connect-btn ${isConnected ? "connected" : ""}`}
        >
          {getButtonText()}
        </button>
      </div>
    </div>
  );
}
