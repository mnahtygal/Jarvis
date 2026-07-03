import StatusDot from "./StatusDot";

type MissionSectionRow = {
  label: string;
  value: string;
  ok?: boolean;
};

type MissionSectionProps = {
  title: string;
  rows: MissionSectionRow[];
};

export default function MissionSection({ title, rows }: MissionSectionProps) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 20,
        padding: 20,
        minWidth: 0,
      }}
    >
      <h3 style={{ margin: "0 0 14px", fontSize: 18 }}>{title}</h3>
      <div style={{ display: "grid", gap: 10 }}>
        {rows.map((row) => (
          <div
            key={row.label}
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(130px, 0.8fr) minmax(0, 1.4fr)",
              gap: 12,
              alignItems: "center",
              padding: 12,
              borderRadius: 12,
              background: "rgba(0,0,0,0.22)",
              border: "1px solid rgba(255,255,255,0.06)",
              fontSize: 13,
            }}
          >
            <div style={{ opacity: 0.68 }}>{row.label}</div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                minWidth: 0,
                fontWeight: 700,
                overflowWrap: "anywhere",
              }}
            >
              <StatusDot ok={row.ok} />
              {row.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
