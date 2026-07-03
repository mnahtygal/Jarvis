interface StatusDotProps {
  ok?: boolean;
}

export default function StatusDot({ ok }: StatusDotProps) {
  if (ok === undefined) {
    return null;
  }

  return (
    <span
      style={{
        width: 8,
        height: 8,
        borderRadius: 999,
        background: ok ? "#22c55e" : "#f97316",
        flex: "0 0 auto",
      }}
    />
  );
}
