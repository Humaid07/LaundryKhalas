import type { Message, SettingsStatus, TestChatResponse } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8100";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API error ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Could not reach the WhatsApp agent backend.");
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  sendTestMessage: (payload: {
    conversation_id?: string;
    sender_name?: string;
    phone_number?: string;
    message: string;
    action_id?: string;
  }) =>
    request<TestChatResponse>("/api/test-chat/message", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getMessages: (conversationId: string) =>
    request<Message[]>(`/api/messages?conversation_id=${encodeURIComponent(conversationId)}`),

  getSettingsStatus: () => request<SettingsStatus>("/api/settings/status"),

  getHealth: () => request<{ status: string }>("/health"),
};
