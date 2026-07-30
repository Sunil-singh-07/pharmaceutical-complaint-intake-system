interface DashboardLayoutProps {
  complaintPanel: React.ReactNode;
  aiPanel: React.ReactNode;
  chatPanel: React.ReactNode;
}

export default function DashboardLayout({
  complaintPanel,
  aiPanel,
  chatPanel,
}: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-slate-100">
      <main className="mx-auto max-w-7xl p-6">

        {/* Header */}

        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Pharma Complaint AI
            </h1>

            <p className="text-slate-500">
              AI-powered pharmaceutical complaint intake system
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-full bg-green-100 px-4 py-2">
            <span className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse" />

            <span className="text-sm font-semibold text-green-700">
              AI Online
            </span>
          </div>
        </div>

        {/* Top */}

        <div className="grid gap-6 lg:grid-cols-2">

          <section className="rounded-2xl border bg-white p-6 shadow-sm">
            {complaintPanel}
          </section>

          <section className="rounded-2xl border bg-white p-6 shadow-sm">
            {aiPanel}
          </section>

        </div>

        {/* Bottom */}

        <section className="mt-6 rounded-2xl border bg-white shadow-sm">

          <div className="border-b px-6 py-4">

            <h2 className="text-lg font-semibold">
              AI Conversation
            </h2>

            <p className="text-sm text-slate-500">
              Describe the complaint naturally.
            </p>

          </div>

          <div className="p-6">
            {chatPanel}
          </div>

        </section>

      </main>
    </div>
  );
}