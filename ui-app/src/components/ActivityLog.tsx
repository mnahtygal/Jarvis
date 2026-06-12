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
              whiteSpace: "pre-wrap",
            }}
          >
            {log}
          </div>
        ))}
      </div>
    </div>
  );
}
