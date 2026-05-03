export function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="metric">
      <strong>{String(value)}</strong>
      <span>{label}</span>
    </div>
  );
}
