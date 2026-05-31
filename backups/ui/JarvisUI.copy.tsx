import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Mic, Camera, Cpu, Activity, Terminal, Wifi, Power, Clock3, MessageSquare } from "lucide-react";

function GlowRing({ listening }: { listening: boolean }) {
  return (
    <div style={{ position: "relative", height: 260, width: 260, margin: "0 auto" }}>
      <motion.div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: "rgba(34,211,238,0.1)",
          filter: "blur(40px)",
        }}
        animate={{ scale: listening ? [1, 1.15, 1] : [1, 1.05, 1] }}
        transition={{ repeat: Infinity, duration: listening ? 1.2 : 3 }}
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
          boxShadow: "0 0 40px rgba(34,211,238,0.5)",
        }}
        animate={{ scale: listening ? [1, 1.08, 1] : [1, 1.03, 1] }}
        transition={{ repeat: Infinity, duration: 1.2 }}
      />

      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", color: "white" }}>
        <div style={{ fontSize: 22, letterSpacing: 4 }}>JARVIS</div>
        <div style={{ fontSize: 12, opacity: 0.7 }}>{listening ? "Listening" : "Standby"}</div>
      </div>
    </div>
  );
}

export default function JarvisUI() {
  const [listening, setListening] = useState(false);
  const [command, setCommand] = useState("");
  const [logs, setLogs] = useState<string[]>([
    "System ready",
    "Mic connected",
    "Camera ready",
  ]);

  const time = useMemo(() => new Date().toLocaleTimeString(), []);

  const sendCommand = () => {
    if (!command) return;
    setLogs([`You: ${command}`, `Jarvis: Processing...`, ...logs]);
    setCommand("");
  };

  return (
    <div style={{ minHeight: "100vh", background: "#020617", color: "white", padding: 20 }}>
      <h1 style={{ fontSize: 32, marginBottom: 10 }}>Jarvis Command Center</h1>
      <div style={{ opacity: 0.6, marginBottom: 20 }}>Time: {time}</div>

      <GlowRing listening={listening} />

      <div style={{ marginTop: 20, display: "flex", gap: 10 }}>
        <button onClick={() => setListening(!listening)} style={{ padding: 10 }}>
          <Mic size={16} /> {listening ? "Stop" : "Listen"}
        </button>
        <button style={{ padding: 10 }}><Camera size={16} /> Camera</button>
        <button style={{ padding: 10 }}><Activity size={16} /> Status</button>
        <button style={{ padding: 10 }}><Power size={16} /> Power</button>
      </div>

      <div style={{ marginTop: 20 }}>
        <input
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendCommand()}
          placeholder="Type command..."
          style={{ padding: 10, width: "70%" }}
        />
        <button onClick={sendCommand} style={{ padding: 10, marginLeft: 10 }}>
          <MessageSquare size={16} /> Send
        </button>
      </div>

      <div style={{ marginTop: 30 }}>
        <h3>Activity Log</h3>
        <div>
          {logs.map((log, i) => (
            <div key={i} style={{ padding: 6, opacity: 0.8 }}>{log}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

