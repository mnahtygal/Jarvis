import React from "react";

export default function StatusCard({
  title,
  value,
  detail,
  icon,
  ok = true,
}: {
  title: string;
  value: string;
  detail?: string;
  icon: React.ReactNode;
  ok?: boolean;
}) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 16,
        padding: 16,
        minHeight: 115,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <div style={{ opacity: 0.75, fontSize: 13 }}>{title}</div>
        <div style={{ color: ok ? "#22c55e" : "#f97316" }}>{icon}</div>
      </div>
      <div style={{ marginTop: 10, fontSize: 21, fontWeight: 800 }}>{value}</div>
      {detail && (
        <div style={{ marginTop: 8, opacity: 0.75, fontSize: 13, lineHeight: 1.35 }}>
          {detail}
        </div>
      )}
    </div>
  );
}
