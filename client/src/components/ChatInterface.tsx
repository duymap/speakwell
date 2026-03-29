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

const ERROR_META: Record<
  Exclude<ErrorKind, null>,
  { icon: string; title: string; body: string; action: string }
> = {
  mic_denied: {
    icon: "🎤",
    title: "Microphone Access Required",
    body: "SpeakWell needs microphone access to have a conversation.",
    action: "Try Again",
  },
  server_error: {
    icon: "⚡",
    title: "Connection Failed",
    body: "Could not connect to the server. Please try again.",
    action: "Retry",
  },
  connection_lost: {
    icon: "🔌",
    title: "Connection Lost",
    body: "The conversation was interrupted. Your transcript is preserved above.",
    action: "Reconnect",
  },
};

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
        webrtcRequestParams: {
          endpoint: `${import.meta.env.VITE_API_BASE_URL}/api/offer`,
        },
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
    if (isConnecting) return "Connecting…";
    if (transportState === "disconnecting") return "Disconnecting…";
    if (isConnected) return "End Session";
    return "Start Conversation";
  };

  return (
    <div className="chat-interface">
      <div className="transcript" ref={transcriptRef}>
        {/* Connecting */}
        {isConnecting && (
          <div className="connecting-state">
            <div className="spinner" />
            <p>Setting up your conversation…</p>
          </div>
        )}

        {/* Idle empty state */}
        {!isConnected && !isConnecting && messages.length === 0 && !errorKind && (
          <div className="empty-state">
            <div className="empty-state-icon">💬</div>
            <p>
              Click <strong>"Start Conversation"</strong> to begin practicing
              English with your AI tutor.
            </p>
          </div>
        )}

        {/* Connected but no messages */}
        {isConnected && messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">🎙</div>
            <p>Listening… say hello to your tutor!</p>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, index) => {
          const text = getMessageText(msg);
          if (!text) return null;
          const isUser = msg.role === "user";
          return (
            <div key={index} className={`message message-${msg.role}`}>
              <div className="message-avatar">
                {isUser ? "Y" : "🤖"}
              </div>
              <div className="message-body">
                <div className="message-meta">
                  <span className="message-role">
                    {isUser ? "You" : "Tutor"}
                  </span>
                  {msg.createdAt && (
                    <span className="message-time">
                      {formatTime(msg.createdAt)}
                    </span>
                  )}
                </div>
                <div className="message-bubble">{text}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Error banners */}
      {errorKind && (() => {
        const meta = ERROR_META[errorKind];
        return (
          <div className="error-banner">
            <div className="error-header">
              <span className="error-icon">{meta.icon}</span>
              <span className="error-title">{meta.title}</span>
            </div>
            <p>{meta.body}</p>
            <div className="error-actions">
              <button className="btn-secondary" onClick={handleConnect}>
                {meta.action}
              </button>
            </div>
          </div>
        );
      })()}

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
