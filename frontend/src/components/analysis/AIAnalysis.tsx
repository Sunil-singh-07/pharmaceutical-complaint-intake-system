import Card from "../ui/Card";

import type {
  AI,
  Risk,
  Validation,
} from "../../types/complaint";

interface AIAnalysisProps {
  ai: AI | null;
  validation: Validation | null;
  risk: Risk | null;
}

function priorityColor(priority: string | null) {
  switch (priority?.toLowerCase()) {
    case "critical":
      return "bg-red-100 text-red-700";
    case "high":
      return "bg-orange-100 text-orange-700";
    case "medium":
      return "bg-yellow-100 text-yellow-700";
    case "low":
      return "bg-green-100 text-green-700";
    default:
      return "bg-slate-100 text-slate-600";
  }
}

function confidenceLabel(confidence: number) {
  if (confidence >= 90) return "Excellent";
  if (confidence >= 75) return "High";
  if (confidence >= 60) return "Moderate";
  if (confidence >= 40) return "Low";
  return "Needs Review";
}

function prettifyField(field: string) {
  return field
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AIAnalysis({
  ai,
  validation,
  risk,
}: AIAnalysisProps) {
  if (!ai || !validation || !risk) {
    return (
      <Card title="AI Intelligence">
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
          <div className="mb-3 text-5xl">🧠</div>

          <h3 className="text-lg font-semibold text-slate-800">
            Waiting for AI Analysis
          </h3>

          <p className="mt-2 text-sm text-slate-500">
            Start chatting with the AI to generate structured complaint
            analysis.
          </p>
        </div>
      </Card>
    );
  }

  const confidence = Math.round((ai.confidence ?? 0) * 100);
  const riskScore = Math.round(risk.score ?? 0);

  return (
    <Card title="AI Intelligence">
      <div className="space-y-6">

        {/* Executive Overview */}

        <section className="rounded-xl border border-slate-200 bg-slate-50 p-5">

          <div className="flex items-start justify-between">

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Risk Priority
              </p>

              <span
                className={`mt-3 inline-flex rounded-full px-3 py-1 text-sm font-semibold ${priorityColor(
                  risk.priority
                )}`}
              >
                ⚠ {risk.priority ?? "Unknown"}
              </span>

            </div>

            <div className="text-right">

              <div className="text-3xl font-bold text-red-700">
                   {riskScore}%
                </div>

             <div className="text-sm text-slate-500">
                 Risk Score
               </div>

            </div>

          </div>

          <div className="mt-6">

            <div className="mb-2 flex justify-between text-sm">

              <span className="text-slate-500">
                  Risk Score
                </span>

              <span className="font-semibold">
                {riskScore}%
              </span>

            </div>

            <div className="h-2 overflow-hidden rounded-full bg-slate-200">

              <div
                className="h-full rounded-full bg-blue-600 transition-all duration-500"
                style={{
                  width: `${riskScore}%`,
                }}
              />

            </div>

          </div>

          <div className="mt-6 border-t border-slate-200 pt-4">

            <span
              className={`rounded-full px-3 py-1 text-sm font-semibold ${
                validation.is_valid
                  ? "bg-green-100 text-green-700"
                  : "bg-red-100 text-red-700"
              }`}
            >
              {validation.is_valid
                ? "✔ Validation Passed"
                : "✖ Validation Failed"}
            </span>

          </div>

        </section>

        {/* AI Summary */}

        <section>

          <h3 className="mb-3 text-lg font-semibold text-slate-900">
            📝 AI Summary
          </h3>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">

            <p className="whitespace-pre-line leading-7 text-slate-700">
              {ai.summary || "No summary generated."}
            </p>

          </div>

        </section>

        {/* Insights */}

        <section>

          <h3 className="mb-3 text-lg font-semibold text-slate-900">
            📌 Insights
          </h3>

          <div className="space-y-4"> 

                      {/* Missing Information */}

          <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4">

            <h4 className="mb-3 font-semibold text-yellow-800">
              ⚠ Missing Information
            </h4>

            {ai.missing_fields.length === 0 ? (
              <p className="text-sm text-green-700">
                ✅ All required fields extracted successfully.
              </p>
            ) : (
              <div className="space-y-2">
                {ai.missing_fields.map((field) => (
                  <div
                    key={field}
                    className="rounded-lg bg-white px-3 py-2 text-sm"
                  >
                    {prettifyField(field)}
                  </div>
                ))}
              </div>
            )}

          </div>

          {/* Validation Warnings */}

          {validation.warnings.length > 0 && (

            <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4">

              <h4 className="mb-3 font-semibold text-yellow-800">
                ⚠ Validation Warnings
              </h4>

              <div className="space-y-2">

                {validation.warnings.map((warning) => (
                  <div
                    key={warning}
                    className="rounded-lg bg-white px-3 py-2 text-sm"
                  >
                    {warning}
                  </div>
                ))}

              </div>

            </div>

          )}

          {/* Validation Errors */}

          {validation.errors.length > 0 && (

            <div className="rounded-xl border border-red-200 bg-red-50 p-4">

              <h4 className="mb-3 font-semibold text-red-800">
                ❌ Validation Errors
              </h4>

              <div className="space-y-2">

                {validation.errors.map((error) => (
                  <div
                    key={error.field}
                    className="rounded-lg bg-white px-3 py-2 text-sm"
                  >
                    <strong>{prettifyField(error.field)}</strong>

                    <div className="mt-1 text-slate-600">
                      {error.message}
                    </div>

                  </div>
                ))}

              </div>

            </div>

          )}

          {/* Risk Factors */}

          {risk.reasons.length > 0 && (

            <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">

              <h4 className="mb-3 font-semibold text-orange-800">
                🔶 Risk Factors
              </h4>

              <div className="space-y-2">

                {risk.reasons.map((reason) => (
                  <div
                    key={reason}
                    className="rounded-lg bg-white px-3 py-2 text-sm"
                  >
                    {reason}
                  </div>
                ))}

              </div>

            </div>

          )}

        </div>

      </section>

      {/* Recommended Actions */}

      <section>

        <h3 className="mb-3 text-lg font-semibold text-slate-900">
          ✅ Recommended Actions
        </h3>

        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">

          {risk.recommended_actions.length === 0 ? (

            <p className="text-sm text-slate-600">
              No recommendations available.
            </p>

          ) : (

            <div className="space-y-2">

              {risk.recommended_actions.map((action) => (
                <div
                  key={action}
                  className="rounded-lg bg-white px-3 py-2 text-sm"
                >
                  {action}
                </div>
              ))}

            </div>

          )}

        </div>

      </section>

    </div>

  </Card>

  );
}