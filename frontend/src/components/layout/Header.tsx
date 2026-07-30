import Badge from "../ui/Badge";

type HeaderProps = {
  onSave?: () => void;
  saving?: boolean;
};


export default function Header({
  onSave,
  saving = false,
}: HeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <div>
          <h1 className="text-lg font-semibold">
            Pharma Complaint Intake
          </h1>

          <p className="text-sm text-slate-500">
            AI-Assisted Pharmaceutical Complaint Management
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Badge>AI Ready</Badge>

          <button
            onClick={onSave}
            disabled={saving}
            className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "💾 Save Complaint"}
          </button>
        </div>
      </div>
    </header>
  );
}