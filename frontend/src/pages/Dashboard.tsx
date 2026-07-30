import { useState } from "react";
import DashboardLayout from "../components/layout/DashboardLayout";
import AIConversation from "../components/chat/AIConversation";
import ComplaintDetails from "../components/complaint/ComplaintDetails";
import AIAnalysis from "../components/analysis/AIAnalysis";
import { useComplaintContext } from "../context/ComplaintContext";
import { saveComplaint } from "../api/complaints";

export default function Dashboard() {
  const { complaintState } = useComplaintContext();

  return (
    <DashboardLayout
      complaintPanel={
        <ComplaintDetails
          complaint={complaintState?.complaint ?? null}
        />
      }
      aiPanel={
        <AIAnalysis
          ai={complaintState?.ai ?? null}
          risk={complaintState?.risk ?? null}
          validation={complaintState?.validation ?? null}
        />
      }
      chatPanel={<AIConversation />}
    />
  );
}