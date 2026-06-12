import { motion } from "framer-motion";

export default function GlowRing({
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
