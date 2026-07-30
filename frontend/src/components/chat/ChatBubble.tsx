import {
  Bot,
  User,
  FileText,
  Image as ImageIcon,
} from "lucide-react";

import type { ChatMessage } from "../../data/chat";

interface ChatBubbleProps {
  message: ChatMessage;
}

export default function ChatBubble({
  message,
}: ChatBubbleProps) {
  const isAI = message.sender === "ai";

  return (
    <div
      className={`flex items-end gap-3 ${
        isAI ? "justify-start" : "justify-end"
      }`}
    >
      {/* AI Avatar */}

      {isAI && (
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-600 text-white shadow">
          <Bot size={20} />
        </div>
      )}

      {/* Message */}

      <div
        className={`max-w-[75%] rounded-3xl px-5 py-4 shadow-sm transition-all ${
          isAI
            ? "rounded-bl-lg border border-slate-200 bg-white text-slate-800"
            : "rounded-br-lg bg-blue-600 text-white"
        }`}
      >
        <div className="mb-2 flex items-center justify-between gap-4">
          <span
            className={`text-xs font-semibold uppercase tracking-wide ${
              isAI ? "text-blue-600" : "text-blue-100"
            }`}
          >
            {isAI ? "AI Assistant" : "You"}
          </span>

          <span
            className={`text-xs ${
              isAI ? "text-slate-400" : "text-blue-100"
            }`}
          >
            {message.timestamp.toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>

        {message.text && (
          <p className="whitespace-pre-wrap leading-7">
            {message.text}
          </p>
        )}

        {message.attachments?.length ? (
          <div className="mt-4 space-y-3">
            {message.attachments.map((file, index) => {
              const isImage = file.type.startsWith("image/");

              return (
                <div key={`${file.name}-${index}`}>
                  {isImage ? (
                    <div className="overflow-hidden rounded-2xl border border-slate-200">
                      <img
                        src={URL.createObjectURL(file)}
                        alt={file.name}
                        className="max-h-64 w-full object-cover"
                      />

                      <div
                        className={`flex items-center gap-2 px-4 py-3 text-sm ${
                          isAI
                            ? "bg-slate-50"
                            : "bg-blue-500"
                        }`}
                      >
                        <ImageIcon size={16} />

                        <span className="truncate">
                          {file.name}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div
                      className={`flex items-center gap-3 rounded-xl px-4 py-3 ${
                        isAI
                          ? "bg-slate-100"
                          : "bg-blue-500"
                      }`}
                    >
                      <FileText size={18} />

                      <span className="truncate text-sm">
                        {file.name}
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : null}
      </div>

      {/* User Avatar */}

      {!isAI && (
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 text-white shadow">
          <User size={20} />
        </div>
      )}
    </div>
  );
}