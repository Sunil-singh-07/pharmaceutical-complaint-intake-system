import { createContext, useContext, useState } from "react";
import type { ComplaintState } from "../types/complaint";

interface ComplaintContextType {
  complaintState: ComplaintState | null;
  setComplaintState: (state: ComplaintState | null) => void;
}

const ComplaintContext = createContext<ComplaintContextType | undefined>(
  undefined
);

export function ComplaintProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [complaintState, setComplaintState] =
    useState<ComplaintState | null>(null);

  return (
    <ComplaintContext.Provider
      value={{
        complaintState,
        setComplaintState,
      }}
    >
      {children}
    </ComplaintContext.Provider>
  );
}

export function useComplaintContext() {
  const context = useContext(ComplaintContext);

  if (!context) {
    throw new Error(
      "useComplaintContext must be used inside ComplaintProvider"
    );
  }

  return context;
}