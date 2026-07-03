type PlaceholderPageProps = {
  title: string;
  description: string;
  items: string[];
};

export default function PlaceholderPage({ title, description, items }: PlaceholderPageProps) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 20,
        padding: 24,
      }}
    >
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <p style={{ opacity: 0.78, lineHeight: 1.5 }}>{description}</p>
      <div style={{ display: "grid", gap: 10, marginTop: 20 }}>
        {items.map((item) => (
          <div
            key={item}
            style={{
              padding: 12,
              borderRadius: 12,
              background: "rgba(0,0,0,0.22)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
