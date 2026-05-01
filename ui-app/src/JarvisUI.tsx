import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Mic,
  Camera,
  Activity,
  Power,
  Clock3,
  MessageSquare,
  Volume2,
  VolumeX,
  RefreshCw,
} from "lucide-react";

type AskResponse = {
  heard: string;
  response: string;
};

function GlowRing({
  listening,
  processing,
}: {
  listening: boolean;
  processing: boolean;
}) {
  const active = listening || processing;

  return (
    <div
      style={{
        position: "relative",
        height: 260,
        width: 260,
        margin: "0 auto",
      }}
    >
      <motion.div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: "rgba(34,211,238,0.12)",
          filter: "blur(40px)",
        }}
        animate={{ scale: active ? [1, 1.16, 1] : [1, 1.04, 1] }}
        transition={{ repeat: Infinity, duration: active ? 1.2 : 3 }}
      />

      <motion.div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          border: "1px solid rgba(34,211,238,0.3)",
        }}
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 12, ease: "linear" }}
      />

      <motion.div
        style={{
          position: "absolute",
          top: 30,
          left: 30,
          right: 30,
          bottom: 30,
          borderRadius: "50%",
          background: "linear-gradient(135deg, #22d3ee, #0ea5e9, #1e3a8a)",
          boxShadow: active
            ? "0 0 55px rgba(34,211,238,0.65)"
            : "0 0 30px rgba(34,211,238,0.35)",
        }}
        animate={{ scale: active ? [1, 1.08, 1] : [1, 1.02, 1] }}
        transition={{ repeat: Infinity, duration: active ? 1.1 : 2.5 }}
      />

      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          color: "white",
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 22, letterSpacing: 4, fontWeight: 700 }}>
          JARVIS
        </div>
        <div style={{ fontSize: 12, opacity: 0.8, marginTop: 4 }}>
          {listening ? "Listening..." : processing ? "Processing..." : "Standby"}
        </div>
      </div>
    </div>
  );
}

function ControlButton({
  onClick,
  label,
  icon,
  disabled = false,
}: {
  onClick?: () => void;
  label: string;
  icon: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "10px 14px",
        borderRadius: 12,
        border: "1px solid rgba(255,255,255,0.12)",
        background: disabled ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.08)",
        color: "white",
        cursor: disabled ? "not-allowed" : "pointer",
        display: "flex",
        alignItems: "center",
        gap: 8,
      }}
    >
      {icon}
      {label}
    </button>
  );
}

export default function JarvisUI() {
  const apiBase = useMemo(() => "http://127.0.0.1:5000", []);
  const [listening, setListening] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [command, setCommand] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [apiStatus, setApiStatus] = useState("Checking API...");
  const [logs, setLogs] = useState<string[]>([
    "Jarvis UI online",
    "Ready for voice or typed commands",
  ]);

  const [time, setTime] = useState(
    new Date().toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    })
  );

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(
        new Date().toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const prependLogs = (entries: string[]) => {
    setLogs((prev) => [...entries, ...prev]);
  };

  const checkApi = async () => {
    try {
      const res = await fetch(`${apiBase}/health`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setApiStatus("API connected");
      prependLogs(["Backend health check passed"]);
    } catch (error) {
      console.error(error);
      setApiStatus("API offline");
      prependLogs(["Backend health check failed"]);
    }
  };

  useEffect(() => {
    checkApi();
  }, []);

  const runVoiceAsk = async () => {
    if (listening || processing) return;

    setListening(true);
    prependLogs(["Listening requested from UI"]);

    try {
      const res = await fetch(`${apiBase}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          use_voice: voiceEnabled,
        }),
      });

      const data: AskResponse = await res.json();

      setListening(false);
      setProcessing(true);

      prependLogs([
        `You: ${data.heard || "(nothing heard)"}`,
        `Jarvis: ${data.response || "(no response)"}`,
      ]);
    } catch (error) {
      console.error(error);
      setListening(false);
      prependLogs(["Jarvis API call failed"]);
    } finally {
      setProcessing(false);
    }
  };

  const sendTypedCommand = async () => {
    const trimmed = command.trim();
    if (!trimmed || listening || processing) return;

    setProcessing(true);
    prependLogs([`You: ${trimmed}`]);

    try {
      const res = await fetch(`${apiBase}/text`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          command: trimmed,
          use_voice: voiceEnabled,
        }),
      });

      const data: AskResponse = await res.json();
      prependLogs([`Jarvis: ${data.response || "(no response)"}`]);
      setCommand("");
    } catch (error) {
      console.error(error);
      prependLogs(["Failed to send typed command"]);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(circle at top, rgba(34,211,238,0.14), transparent 25%), #020617",
        color: "white",
        padding: 20,
        fontFamily: "Arial, Helvetica, sans-serif",
      }}
    >
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
        }}
      >
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: 34, marginBottom: 8 }}>Jarvis Command Center</h1>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 16,
              opacity: 0.8,
              fontSize: 14,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Clock3 size={16} />
              {time}
            </div>
            <div>API: {apiStatus}</div>
            <div>Voice: {voiceEnabled ? "On" : "Off"}</div>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.4fr 1fr",
            gap: 20,
          }}
        >
          <div
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 20,
              padding: 24,
            }}
          >
            <GlowRing listening={listening} processing={processing} />

            <div
              style={{
                marginTop: 24,
                display: "flex",
                flexWrap: "wrap",
                gap: 10,
              }}
            >
              <ControlButton
                onClick={runVoiceAsk}
                disabled={listening || processing}
                label={listening ? "Listening..." : processing ? "Working..." : "Listen"}
                icon={<Mic size={16} />}
              />
              <ControlButton
                label="Camera"
                icon={<Camera size={16} />}
                disabled
              />
              <ControlButton
                onClick={checkApi}
                label="Status"
                icon={<Activity size={16} />}
              />
              <ControlButton
                label="Power"
                icon={<Power size={16} />}
                disabled
              />
              <ControlButton
                onClick={() => setVoiceEnabled((v) => !v)}
                label={voiceEnabled ? "Voice On" : "Voice Off"}
                icon={voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
              />
              <ControlButton
                onClick={() => window.location.reload()}
                label="Refresh"
                icon={<RefreshCw size={16} />}
              />
            </div>

            <div style={{ marginTop: 24 }}>
              <div style={{ marginBottom: 10, opacity: 0.85 }}>Typed command</div>
              <div style={{ display: "flex", gap: 10 }}>
                <input
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendTypedCommand()}
                  placeholder="Type command... try: what time is it"
                  style={{
                    flex: 1,
                    padding: 12,
                    borderRadius: 12,
                    border: "1px solid rgba(255,255,255,0.12)",
                    background: "rgba(0,0,0,0.22)",
                    color: "white",
                    outline: "none",
                  }}
                />
                <button
                  onClick={sendTypedCommand}
                  disabled={processing || listening}
                  style={{
                    padding: "12px 16px",
                    borderRadius: 12,
                    border: "1px solid rgba(255,255,255,0.12)",
                    background: "white",
                    color: "#020617",
                    fontWeight: 700,
                    cursor: processing || listening ? "not-allowed" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <MessageSquare size={16} />
                  Send
                </button>
              </div>
            </div>
          </div>

          <div
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 20,
              padding: 20,
              minHeight: 520,
            }}
          >
            <h3 style={{ marginTop: 0, marginBottom: 16 }}>Activity Log</h3>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 10,
                maxHeight: 470,
                overflowY: "auto",
              }}
            >
              {logs.map((log, i) => (
                <div
                  key={`${log}-${i}`}
                  style={{
                    padding: 10,
                    borderRadius: 10,
                    background: "rgba(0,0,0,0.22)",
                    border: "1px solid rgba(255,255,255,0.06)",
                    opacity: 0.92,
                    lineHeight: 1.4,
                  }}
                >
                  {log}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
