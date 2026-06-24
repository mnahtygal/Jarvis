type LogKind = "vision" | "camera" | "user" | "jarvis" | "system";

function getLogKind(log: string): LogKind {
  if (log.startsWith("Vision (") || log.startsWith("Vision analysis")) return "vision";
  if (log.startsWith("Camera") || log.startsWith("Analyzed snapshot")) return "camera";
  if (log.startsWith("You:")) return "user";
  if (log.startsWith("Jarvis:")) return "jarvis";
  return "system";
}

function formatLog(log: string) {
  const kind = getLogKind(log);

  if (kind === "vision" && log.startsWith("Vision (")) {
    const splitIndex = log.indexOf(": ");
    const title = splitIndex > -1 ? log.slice(0, splitIndex) : "Vision";
    const body = splitIndex > -1 ? log.slice(splitIndex + 2) : log;

    return {
      kind,
      title,
      body,
    };
  }

  if (kind === "user") {
    return {
      kind,
      title: "You",
      body: log.replace(/^You:\s*/, ""),
    };
  }

  if (kind === "jarvis") {
    return {
      kind,
      title: "Jarvis",
      body: log.replace(/^Jarvis:\s*/, ""),
    };
  }

  return {
    kind,
    title: kind === "camera" ? "Camera" : kind === "vision" ? "Vision" : "System",
    body: log,
  };
}

function getAccent(kind: LogKind) {
  if (kind === "vision") return "rgba(34,211,238,0.95)";
  if (kind === "camera") return "rgba(74,222,128,0.95)";
  if (kind === "user") return "rgba(250,204,21,0.95)";
  if (kind === "jarvis") return "rgba(96,165,250,0.95)";
  return "rgba(255,255,255,0.45)";
}

export default function ActivityLog({ logs }: { logs: string[] }) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 20,
        padding: 20,
        minHeight: 610,
      }}
    >
      <h3 style={{ marginTop: 0, marginBottom: 16 }}>Activity Log</h3>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          maxHeight: 560,
          overflowY: "auto",
          paddingRight: 4,
        }}
      >
        {logs.map((log, i) => {
          const formatted = formatLog(log);
          const accent = getAccent(formatted.kind);

          return (
            <div
              key={`${log}-${i}`}
              style={{
                padding: 12,
                borderRadius: 12,
                background: "rgba(0,0,0,0.22)",
                border: "1px solid rgba(255,255,255,0.06)",
                borderLeft: `3px solid ${accent}`,
                opacity: 0.94,
                lineHeight: 1.48,
                overflowWrap: "anywhere",
                wordBreak: "break-word",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 10,
                  marginBottom: 6,
                }}
              >
                <div
                  style={{
                    color: accent,
                    fontSize: 12,
                    fontWeight: 800,
                    letterSpacing: 0.4,
                    textTransform: "uppercase",
                  }}
                >
                  {formatted.title}
                </div>
              </div>

              <div
                style={{
                  whiteSpace: "pre-wrap",
                  fontSize: formatted.kind === "vision" ? 14 : 13,
                  color: "rgba(255,255,255,0.9)",
                }}
              >
                {formatted.body}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
