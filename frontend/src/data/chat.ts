export interface ChatMessage {
  id: number;
  sender: "ai" | "user";
  text: string;
  attachments?: File[];
  timestamp: Date;
}

export const messages: ChatMessage[] = [
  {
    id: 1,
    sender: "ai",
    text: "Can you tell me when the symptoms started?",
    timestamp: new Date(),
  },
  {
    id: 2,
    sender: "user",
    text: "Approximately two hours after taking the first tablet.",
    timestamp: new Date(),
  },
  {
    id: 3,
    sender: "ai",
    text: "Did the patient require hospitalization?",
    timestamp: new Date(),
  },
];