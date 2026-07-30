import { useEffect, useRef, useState } from "react";

import { createComplaint } from "../../api/complaints";
import { useComplaintContext } from "../../context/ComplaintContext";

import type { ChatMessage } from "../../data/chat";
import { messages as initialMessages } from "../../data/chat";

import ChatBubble from "./ChatBubble";
import ChatInput from "./ChatInput";
import FilePreview from "./FilePreview";
import TypingIndicator from "./TypingIndicator";

export default function AIConversation() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [isTyping, setIsTyping] = useState(false);

  const {
    complaintState,
    setComplaintState,
  } = useComplaintContext();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, isTyping]);

  async function sendMessage() {
    if (!input.trim() && files.length === 0) return;

    const userMessage: ChatMessage = {
      id: Date.now(),
      sender: "user",
      text:
        input.trim() ||
        (files.length > 0
          ? `📄 Uploaded: ${files[0].name}`
          : ""),
      attachments: files,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    try {
      const response = await createComplaint({
        message: input.trim() || "Please analyze the attached PDF.",
        sessionId: complaintState?.session?.session_id,
        pdf: files.length > 0 ? files[0] : undefined,
      });

      setComplaintState(response.data);

      let aiResponse = "";

      if (response.data.ai.summary) {
        aiResponse = response.data.ai.summary;
      } else if (response.data.ai.missing_fields.length > 0) {
        aiResponse =
          "I've analyzed the complaint. I still need: " +
          response.data.ai.missing_fields.join(", ") +
          ".";
      } else {
        aiResponse =
          "Complaint analyzed successfully. Review the extracted information on the right.";
      }

      const aiMessage: ChatMessage = {
        id: Date.now() + 1,
        sender: "ai",
        text: aiResponse,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err) {
      console.error(err);

      const errorMessage: ChatMessage = {
        id: Date.now() + 1,
        sender: "ai",
        text: "Sorry, I couldn't analyze the complaint. Please try again.",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setInput("");
      setFiles([]);
      setIsTyping(false);
    }
  }

  return (
    <div className="flex h-[72vh] flex-col">
      <div className="flex-1 overflow-y-auto rounded-2xl bg-slate-50 p-6">
        <div className="space-y-5">
          {messages.map((message) => (
            <ChatBubble
              key={message.id}
              message={message}
            />
          ))}

          {isTyping && <TypingIndicator />}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {files.length > 0 && (
        <div className="mt-4">
          <FilePreview
            files={files}
            onRemove={(index) =>
              setFiles((prev) =>
                prev.filter((_, i) => i !== index)
              )
            }
          />
        </div>
      )}

      <div className="mt-5">
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={sendMessage}
          onFileSelect={(selectedFiles) => {
            if (!selectedFiles) return;

            setFiles((prev) => [
              ...prev,
              ...Array.from(selectedFiles),
            ]);
          }}
        />
      </div>
    </div>
  );
}