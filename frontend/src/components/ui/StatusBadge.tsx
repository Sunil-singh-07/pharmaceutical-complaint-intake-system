interface StatusBadgeProps {
  value: string;
}

export default function StatusBadge({
  value,
}: StatusBadgeProps) {
  const colors = {
    High: "bg-red-100 text-red-700",
    Medium: "bg-yellow-100 text-yellow-700",
    Low: "bg-green-100 text-green-700",
    Positive: "bg-green-100 text-green-700",
    Negative: "bg-red-100 text-red-700",
    Neutral: "bg-slate-100 text-slate-700",
  };

  return (
    <span
      className={`rounded-full px-3 py-1 text-sm font-medium ${
        colors[value as keyof typeof colors] ??
        "bg-slate-100 text-slate-700"
      }`}
    >
      {value}
    </span>
  );
}