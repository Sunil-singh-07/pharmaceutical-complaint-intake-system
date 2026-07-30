import { FileText, Image as ImageIcon, X } from "lucide-react";

interface FilePreviewProps {
  files: File[];
  onRemove: (index: number) => void;
}

export default function FilePreview({
  files,
  onRemove,
}: FilePreviewProps) {
  if (files.length === 0) return null;

  return (
    <div className="mb-3 space-y-2">
      {files.map((file, index) => {
        const isImage = file.type.startsWith("image/");

        return (
          <div
            key={`${file.name}-${index}`}
            className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
          >
            <div className="flex items-center gap-3">
              {isImage ? (
                <ImageIcon size={18} className="text-blue-600" />
              ) : (
                <FileText size={18} className="text-slate-600" />
              )}

              <div>
                <p className="font-medium text-slate-800">
                  {file.name}
                </p>

                <p className="text-xs text-slate-500">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
              </div>
            </div>

            <button
              onClick={() => onRemove(index)}
              className="rounded p-1 hover:bg-slate-200"
            >
              <X size={16} />
            </button>
          </div>
        );
      })}
    </div>
  );
}