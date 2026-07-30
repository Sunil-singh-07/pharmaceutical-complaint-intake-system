import { Bot, LoaderCircle } from "lucide-react";

export default function TypingIndicator() {
  return (
    <div className="flex items-end gap-3">

      {/* AI Avatar */}

      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-white shadow">
        <Bot size={20} />
      </div>

      {/* Thinking Bubble */}

      <div className="max-w-md rounded-3xl rounded-bl-lg border border-slate-200 bg-white px-5 py-4 shadow-sm">

        <div className="mb-3 flex items-center gap-2">

          <LoaderCircle
            size={16}
            className="animate-spin text-blue-600"
          />

          <span className="text-xs font-semibold uppercase tracking-wide text-blue-600">
            AI Assistant
          </span>

        </div>

        <div className="space-y-3">

          <ProcessingStep
            text="Extracting complaint details..."
            delay="0ms"
          />

          <ProcessingStep
            text="Validating information..."
            delay="250ms"
          />

          <ProcessingStep
            text="Assessing risk level..."
            delay="500ms"
          />

        </div>

      </div>

    </div>
  );
}

interface ProcessingStepProps {
  text: string;
  delay: string;
}

function ProcessingStep({
  text,
  delay,
}: ProcessingStepProps) {
  return (
    <div
      className="flex items-center gap-3 animate-pulse"
      style={{
        animationDelay: delay,
      }}
    >
      <span className="h-2 w-2 rounded-full bg-blue-500" />

      <span className="text-sm text-slate-600">
        {text}
      </span>
    </div>
  );
}