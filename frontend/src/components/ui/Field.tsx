interface FieldProps {
  label: string;
  value: string;
}

export default function Field({
  label,
  value,
}: FieldProps) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </p>

      <p className="mt-1 font-medium text-slate-800">
        {value}
      </p>
    </div>
  );
}