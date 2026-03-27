import { useState, useCallback } from "react";
import { RTVIEvent } from "@pipecat-ai/client-js";
import {
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react";
import "./AudioIndicator.css";

type AudioState = "idle" | "listening" | "userSpeaking" | "botSpeaking";

interface AudioIndicatorProps {
  audioState?: AudioState;
}

export function AudioIndicator({ audioState: overrideState }: AudioIndicatorProps) {
  const transportState = usePipecatClientTransportState();
  const [userSpeaking, setUserSpeaking] = useState(false);
  const [botSpeaking, setBotSpeaking] = useState(false);

  useRTVIClientEvent(
    RTVIEvent.UserStartedSpeaking,
    useCallback(() => setUserSpeaking(true), [])
  );
  useRTVIClientEvent(
    RTVIEvent.UserStoppedSpeaking,
    useCallback(() => setUserSpeaking(false), [])
  );
  useRTVIClientEvent(
    RTVIEvent.BotStartedSpeaking,
    useCallback(() => setBotSpeaking(true), [])
  );
  useRTVIClientEvent(
    RTVIEvent.BotStoppedSpeaking,
    useCallback(() => setBotSpeaking(false), [])
  );

  const isConnected =
    transportState === "connected" || transportState === "ready";

  const audioState: AudioState =
    overrideState ??
    (!isConnected
      ? "idle"
      : userSpeaking
        ? "userSpeaking"
        : botSpeaking
          ? "botSpeaking"
          : "listening");

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
