import client from "./client";

import type { ComplaintResponse } from "../types/complaint";

interface CreateComplaintRequest {
  message: string;
  sessionId?: string;
  pdf?: File;
}

export async function createComplaint(
  request: CreateComplaintRequest
): Promise<ComplaintResponse> {
  const formData = new FormData();

  formData.append("message", request.message);

  if (request.sessionId) {
    formData.append("session_id", request.sessionId);
  }

  if (request.pdf) {
    formData.append("pdf", request.pdf);
  }

  const response = await client.post<ComplaintResponse>(
    "/complaints",
    formData
  );

  return response.data;
}

export async function getComplaint(
  sessionId: string
): Promise<ComplaintResponse> {
  const response = await client.get<ComplaintResponse>(
    `/complaints/${sessionId}`
  );

  return response.data;
}

export async function saveComplaint(sessionId: string) {
  const response = await client.post(
    `/complaints/${sessionId}/save`
  );

  return response.data;
}