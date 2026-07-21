import { ADMIN_API_KEY, API_BASE_URL } from "./constants";
import type {
  AIActionLog,
  ConversationDetail,
  HumanApproval,
  Market,
  MockInboundResponse,
  Order,
  OrderEvent,
  RunAgentResponse,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API error ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; admin?: boolean; params?: Record<string, string | undefined> } = {}
): Promise<T> {
  const { method = "GET", body, admin = false, params } = options;

  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") url.searchParams.set(key, value);
    }
  }

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (admin) headers["X-Admin-Api-Key"] = ADMIN_API_KEY;

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Could not reach the backend API. Is it running at " + API_BASE_URL + "?");
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail ?? JSON.stringify(data);
    } catch {
      // ignore parse failure, fall back to statusText
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  listMarkets: () => request<Market[]>("/api/admin/markets", { admin: true }),

  mockWhatsappInbound: (payload: {
    market_code: string;
    phone_number: string;
    customer_name?: string;
    message: string;
  }) => request<MockInboundResponse>("/api/mock-whatsapp/inbound", { method: "POST", body: payload }),

  listConversations: () =>
    request<ConversationDetail[]>("/api/admin/conversations", { admin: true }),

  getConversation: (id: string) =>
    request<ConversationDetail>(`/api/admin/conversations/${id}`, { admin: true }),

  listMessages: (conversationId: string) =>
    request<ConversationDetail["messages"]>(`/api/admin/conversations/${conversationId}/messages`, {
      admin: true,
    }),

  manualTakeover: (conversationId: string, takenOverBy: string) =>
    request<ConversationDetail>(`/api/admin/conversations/${conversationId}/manual-takeover`, {
      method: "POST",
      admin: true,
      body: { taken_over_by: takenOverBy },
    }),

  releaseTakeover: (conversationId: string) =>
    request<ConversationDetail>(`/api/admin/conversations/${conversationId}/release-takeover`, {
      method: "POST",
      admin: true,
    }),

  manualReply: (conversationId: string, text: string) =>
    request(`/api/admin/conversations/${conversationId}/manual-reply`, {
      method: "POST",
      admin: true,
      body: { text },
    }),

  runAgent: (conversationId: string) =>
    request<RunAgentResponse>(`/api/admin/conversations/${conversationId}/run-agent`, {
      method: "POST",
      admin: true,
    }),

  listOrders: () => request<Order[]>("/api/admin/orders", { admin: true }),

  getOrder: (id: string) => request<Order>(`/api/admin/orders/${id}`, { admin: true }),

  listOrderEvents: (id: string) =>
    request<OrderEvent[]>(`/api/admin/orders/${id}/events`, { admin: true }),

  listApprovals: (status?: string) =>
    request<HumanApproval[]>("/api/admin/approvals", { admin: true, params: { status } }),

  getApproval: (id: string) => request<HumanApproval>(`/api/admin/approvals/${id}`, { admin: true }),

  approveApproval: (id: string, decidedBy: string, decisionNote?: string) =>
    request<HumanApproval>(`/api/admin/approvals/${id}/approve`, {
      method: "POST",
      admin: true,
      body: { decided_by: decidedBy, decision_note: decisionNote },
    }),

  rejectApproval: (id: string, decidedBy: string, decisionNote?: string) =>
    request<HumanApproval>(`/api/admin/approvals/${id}/reject`, {
      method: "POST",
      admin: true,
      body: { decided_by: decidedBy, decision_note: decisionNote },
    }),

  listAiActionLogs: (params?: { conversation_id?: string; order_id?: string; limit?: string }) =>
    request<AIActionLog[]>("/api/admin/ai-action-logs", { admin: true, params }),
};
