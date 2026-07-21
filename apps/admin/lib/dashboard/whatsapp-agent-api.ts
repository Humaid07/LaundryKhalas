/**
 * Client for the standalone WhatsApp Agent backend (apps/whatsapp-agent, :8100).
 * This is an existing *local mock* service (LLM + WhatsApp both in mock mode) —
 * no live third-party calls. Used by the Operations → WhatsApp Agent tab.
 */

const BASE_URL = process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8100";

export type DomainStatus = "in_domain" | "out_of_domain" | "uncertain";

export interface AgentAction {
  id: string;
  label: string;
  type: string;
}

export interface AgentReply {
  conversation_id: string;
  user_message: string;
  agent_reply: string;
  domain: DomainStatus;
  mode: "mock" | "live";
  provider: string;
  actions: AgentAction[];
}

export interface AgentSettingsStatus {
  app_env: string;
  agent_mode: string;
  llm_provider: string;
  llm_live_ready: boolean;
  whatsapp_mode: string;
  whatsapp_live_ready: boolean;
  database_kind: string;
}

export interface DbHealth {
  status: string;
  mode: string; // "sqlite" | "supabase"
  backend?: string;
  connected?: boolean;
  app_env?: string;
  database_env?: string;
  supabase_project_type?: string;
  error?: string;
}

/**
 * Supabase-backed inbox conversation (GET /api/conversations). Field names
 * mirror the FastAPI/Supabase shape. `is_test_data` / `is_demo` drive the
 * "Test Data" / "Demo Conversation" dashboard badges — seeded rows only.
 */
export interface InboxConversationDTO {
  id: string;
  customer_name: string | null;
  masked_phone: string | null;
  channel: string;
  status: "bot" | "human_needed" | "human_takeover" | "resolved";
  priority: "urgent" | "high" | "medium" | "low" | null;
  human_intervention_required: boolean;
  handoff_reason: string | null;
  assigned_team: string | null;
  linked_order_id: string | null;
  city: string | null;
  area: string | null;
  last_message: string | null;
  last_message_at: string | null;
  unread_count: number;
  is_test_data: boolean;
  is_demo: boolean;
  environment: string;
  test_scenario_id: string | null;
}

export interface InboxMessageDTO {
  id: string;
  conversation_id: string;
  sender_type: "customer" | "agent" | "human" | "system";
  message_text: string;
  is_internal: boolean;
  status: string | null;
  is_test_data: boolean;
  is_demo: boolean;
  created_at: string;
}

export interface AgentFlagDTO {
  id: string;
  conversation_id: string | null;
  order_id: string | null;
  flag_type: string;
  priority: string | null;
  assigned_team: string | null;
  human_intervention_required: boolean;
  reason: string | null;
  suggested_reply: string | null;
  suggested_action: string | null;
  status: string;
  is_test_data: boolean;
  is_demo: boolean;
  created_at: string;
  resolved_at: string | null;
}

export interface OrderDTO {
  id: string;
  order_id: string;
  customer_name: string | null;
  service_type: string | null;
  status: string;
  status_label: string;
  city: string | null;
  pickup_area: string | null;
  amount: number | null;
  currency: string;
  payment: string | null;
  is_demo: boolean;
  [key: string]: unknown;
}

export class AgentApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new AgentApiError(0, "Could not reach the WhatsApp agent backend (:8100). Is it running?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new AgentApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const agentApi = {
  baseUrl: BASE_URL,

  health: () => request<{ status: string }>("/health"),

  settingsStatus: () => request<AgentSettingsStatus>("/api/settings/status"),

  sendMessage: (payload: {
    conversation_id?: string;
    sender_name?: string;
    phone_number?: string;
    message: string;
    action_id?: string;
  }) =>
    request<AgentReply>("/api/test-chat/message", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // --- Database health ---
  dbHealth: () => request<DbHealth>("/health/db"),

  // --- Inbox conversations (Supabase-backed; empty list in local SQLite mode) ---
  listConversations: (status?: string) =>
    request<InboxConversationDTO[]>(`/api/conversations${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  getConversation: (id: string) => request<InboxConversationDTO>(`/api/conversations/${id}`),
  getMessages: (id: string) => request<InboxMessageDTO[]>(`/api/conversations/${id}/messages`),
  startHumanTakeover: (id: string, operator_name?: string) =>
    request<InboxConversationDTO>(`/api/conversations/${id}/human-takeover`, {
      method: "POST",
      body: JSON.stringify({ operator_name }),
    }),
  returnToBot: (id: string) =>
    request<InboxConversationDTO>(`/api/conversations/${id}/return-to-bot`, { method: "POST" }),
  sendHumanMessage: (id: string, text: string, operator_name?: string) =>
    request<InboxMessageDTO>(`/api/conversations/${id}/human-message`, {
      method: "POST",
      body: JSON.stringify({ text, operator_name }),
    }),
  resolveConversation: (id: string) =>
    request<InboxConversationDTO>(`/api/conversations/${id}/resolve`, { method: "POST" }),

  // --- Flags ---
  listFlags: (status?: string) =>
    request<AgentFlagDTO[]>(`/api/flags${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  resolveFlag: (flagId: string) =>
    request<AgentFlagDTO>(`/api/flags/${flagId}/resolve`, { method: "POST" }),

  // --- Orders ---
  listOrders: () => request<OrderDTO[]>("/api/orders"),
  listActiveOrders: () => request<OrderDTO[]>("/api/orders/active"),
  listCompletedOrders: () => request<OrderDTO[]>("/api/orders/completed"),
  getOrder: (id: string) => request<OrderDTO>(`/api/orders/${id}`),
};
