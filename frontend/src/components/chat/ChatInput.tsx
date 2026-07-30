import { useRef } from "react";
import {
  Paperclip,
  SendHorizontal,
} from "lucide-react";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onFileSelect?: (files: FileList | null) => void;
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  onFileSelect,
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="rounded-3xl border border-slate-200 bg-white shadow-lg">

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        multiple
        accept=".png,.jpg,.jpeg,.pdf"
        onChange={(e) => onFileSelect?.(e.target.files)}
      />

      <div className="flex items-end gap-3 p-4">

        {/* Attachment */}

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="rounded-full p-3 text-slate-500 transition hover:bg-slate-100 hover:text-blue-600"
        >
          <Paperclip size={20} />
        </button>

        {/* Input */}

        <textarea
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Describe the pharmaceutical complaint..."
          className="max-h-40 min-h-[48px] flex-1 resize-none border-none bg-transparent px-2 py-3 text-slate-700 outline-none placeholder:text-slate-400"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();

              if (value.trim()) {
                onSend();
              }
            }
          }}
        />

        {/* Send */}

        <button
          type="button"
          disabled={!value.trim()}
          onClick={onSend}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white transition-all hover:scale-105 hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          <SendHorizontal size={20} />
        </button>

      </div>

      <div className="border-t border-slate-100 px-5 py-2 text-xs text-slate-400">
        Press <strong>Enter</strong> to send • <strong>Shift + Enter</strong> for a new line
      </div>

    </div>
  );
}