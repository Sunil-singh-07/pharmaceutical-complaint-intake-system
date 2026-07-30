import Card from "../ui/Card";
import type { Complaint } from "../../types/complaint";

interface ComplaintDetailsProps {
  complaint: Complaint | null;
}

function displayValue(value: string | null | undefined) {
  return value && value.trim() !== "" ? value : "Not provided";
}

function badgeColor(severity: string | null | undefined) {
  switch (severity?.toLowerCase()) {
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

export default function ComplaintDetails({
  complaint,
}: ComplaintDetailsProps) {
  if (!complaint) {
    return (
      <Card title="Complaint Details">
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
          <div className="mb-3 text-5xl">📋</div>

          <h3 className="text-lg font-semibold text-slate-800">
            No Complaint Yet
          </h3>

          <p className="mt-2 text-sm text-slate-500">
            Start chatting with the AI to extract structured complaint
            information.
          </p>
        </div>
      </Card>
    );
  }

  return (
  <Card title="Complaint Record">
    <div className="space-y-8">

      {/* Product Information */}

      <section>

        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          📦 Product Information
        </h3>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">

          <DetailRow
            label="Company"
            value={displayValue(complaint.company_name)}
          />

          <DetailRow
            label="Manufacturer"
            value={displayValue(complaint.manufacturer)}
          />

          <DetailRow
            label="Product"
            value={displayValue(complaint.product_name)}
          />

          <DetailRow
            label="Generic Name"
            value={displayValue(complaint.generic_name)}
          />

          <DetailRow
            label="Strength"
            value={displayValue(complaint.strength)}
          />

          <DetailRow
            label="Dosage Form"
            value={displayValue(complaint.dosage_form)}
          />

        </div>

      </section>

      {/* Batch Information */}

      <section>

        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          📋 Batch Information
        </h3>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">

          <DetailRow
            label="Batch Number"
            value={displayValue(complaint.batch_number)}
          />

          <DetailRow
            label="Pack Size"
            value={displayValue(complaint.pack_size)}
          />

          <DetailRow
            label="Quantity"
            value={displayValue(complaint.quantity)}
          />

          <DetailRow
            label="MFG Date"
            value={displayValue(complaint.manufacturing_date)}
          />

          <DetailRow
            label="Expiry Date"
            value={displayValue(complaint.expiry_date)}
          />

        </div>

      </section>

      {/* Complaint Information */}

      <section>

        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          ⚠ Complaint Information
        </h3>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">

          <DetailRow
            label="Category"
            value={displayValue(complaint.complaint_category)}
          />

          <DetailRow
            label="Type"
            value={displayValue(complaint.complaint_type)}
          />

          <DetailRow
            label="Defect"
            value={displayValue(complaint.defect_type)}
          />

          <DetailRow
            label="Reported Event"
            value={displayValue(complaint.reported_event)}
          />

          <DetailRow
            label="Symptoms"
            value={
              complaint.symptoms.length > 0
                ? complaint.symptoms.join(", ")
                : "Not provided"
            }
          />

          <div className="mt-4 flex items-center justify-between">

            <span className="text-sm font-medium text-slate-500">
              Severity
            </span>

            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeColor(
                complaint.severity
              )}`}
            >
              {displayValue(complaint.severity)}
            </span>

          </div>

        </div>

      </section>

      {/* Description */}

      <section>

        <h3 className="mb-4 text-lg font-semibold text-slate-900">
          📝 Complaint Description
        </h3>

        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">

          <p className="whitespace-pre-wrap leading-7 text-slate-700">
            {displayValue(complaint.complaint_description)}
          </p>

        </div>

      </section>

    </div>
  </Card>
    );

}

    function DetailRow({
    label,
    value,
    }: {
    label: string;
    value: string;
    }) {
    return (
        <div className="flex justify-between gap-4 border-b border-slate-100 py-2 last:border-0">
        <span className="text-sm font-medium text-slate-500">
            {label}
        </span>

        <span className="max-w-[60%] text-right text-sm font-semibold text-slate-800 break-words">
            {value}
        </span>
        </div>
    );
    }