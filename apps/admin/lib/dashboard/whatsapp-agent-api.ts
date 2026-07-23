/**
 * Client for the standalone WhatsApp Agent backend (apps/whatsapp-agent, :8101).
 * This is an existing *local mock* service (LLM + WhatsApp both in mock mode) —
 * no live third-party calls. Used by the Operations → WhatsApp Agent tab.
 */

import { clearSession, getToken } from "./auth-token";

const BASE_URL = process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8101";

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

/**
 * A single priced line on an order (from the backend catalogue-pricing layer).
 * All money is in `pricing.currency` (AED) and EXCLUDES VAT. Optional/nullable
 * throughout so older payloads without item-level pricing still type-check.
 */
export interface LineItemDTO {
  item_code: string;
  name: string;                 // canonical item name, e.g. "Shirt"
  quantity: number;
  pricing_unit: string;         // "ITEM" | "PAIR" | "BAG" | "KG" | "SQM"
  unit_price: number | null;    // AED, excludes VAT
  is_starting_price: boolean;   // true = "From" price, not a guaranteed total
  requires_inspection: boolean;
  regular_price: number | null; // crossed-out earlier price, if any
  line_total: number | null;    // null when pending inspection / no firm total
  line_kind: "exact" | "estimate" | "pending";
}

/** Order-level pricing roll-up returned alongside `line_items`. */
export interface OrderPricingDTO {
  currency: string;                          // "AED"
  vat_rate: number;                          // 0.05
  prices_include_vat: boolean;               // false
  subtotal_excluding_vat: number | null;
  vat_amount: number | null;
  estimated_total_including_vat: number | null;
  is_estimated: boolean;                     // true => label total as "Estimated"
  has_pending_inspection: boolean;
  disclaimer: string;                        // e.g. "Prices may vary depending on item condition, material and brand."
}

export interface OrderDTO {
  id: string;
  order_id: string;
  customer_name: string | null;
  service_type: string | null;
  // Canonical 8-service taxonomy fields the backend now returns alongside the
  // raw service_type. Optional so older payloads still type-check.
  service_id: string | null;
  service_display_name: string | null;
  unit_type: string | null;
  requires_manual_quote: boolean;
  status: string;
  status_label: string;
  city: string | null;
  pickup_area: string | null;
  // WhatsApp booking state-machine fields (booking flow).
  pickup_date: string | null;
  pickup_time: string | null;
  pickup_instructions: string | null;
  booking_state: string | null;
  pickup_address: string | null;
  amount: number | null;
  currency: string;
  // Item-level catalogue pricing (optional — only orders priced against the
  // catalogue carry these; `amount` == `pricing.estimated_total_including_vat`).
  line_items?: LineItemDTO[];
  catalogue_category?: string | null;   // e.g. "Clean & Press"
  pricing?: OrderPricingDTO;
  payment: string | null;
  is_demo: boolean;
  // Order↔conversation link + dashboard-only fields (from /api/orders/search).
  conversation_id: string | null;
  customer_phone: string | null;
  needs_attention: boolean;
  human_takeover: boolean;
  conversation_status: string | null;
  source_channel: string;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
}

/** Paginated order list (GET /api/orders/search). */
export interface OrderPageDTO {
  orders: OrderDTO[];
  total: number;
  page: number;
  page_size: number;
}

/** Order audit event (GET /api/orders/{id}/events). */
export interface OrderEventDTO {
  id: string;
  order_id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  actor_type: string | null;
  actor_name: string | null;
  notes: string | null;
  created_at: string;
}

/** Real Orders-section metric cards (GET /api/orders/metrics/summary). */
export interface OrderMetricsSummary {
  new_today: number;
  active_orders: number;
  confirmed_pickups: number;
  completed: number;
  cancelled: number;
  needs_attention: number;
}

/** Filters for the Orders section list. */
export interface OrderSearchParams {
  search?: string;
  status?: string;
  service_id?: string;
  pickup_date?: string;
  source?: string;
  needs_attention?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}

/**
 * Service-taxonomy sync health (GET /api/service-taxonomy/health). The backend
 * compares its live surfaces against the canonical catalog; `in_sync: false`
 * means one or more surfaces drifted. `mismatches` entries may be plain surface
 * strings or small objects — the UI renders either.
 */
export interface ServiceTaxonomyHealth {
  in_sync: boolean;
  mismatches: Array<string | { surface?: string; name?: string; detail?: string }>;
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
  const token = getToken();
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new AgentApiError(0, "Could not reach the WhatsApp agent backend (:8101). Is it running?");
  }
  if (res.status === 401) {
    // Token missing/expired — drop it and bounce to the login screen so the
    // session can be re-established.
    clearSession();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
    throw new AgentApiError(401, "Your session has expired. Please sign in again.");
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

  // --- Service taxonomy health ---
  serviceTaxonomyHealth: () =>
    request<ServiceTaxonomyHealth>("/api/service-taxonomy/health"),

  // --- Orders ---
  listOrders: () => request<OrderDTO[]>("/api/orders"),
  listActiveOrders: () => request<OrderDTO[]>("/api/orders/active"),
  listCompletedOrders: () => request<OrderDTO[]>("/api/orders/completed"),
  getOrder: (id: string) => request<OrderDTO>(`/api/orders/${id}`),
  // Orders section (filtered/paginated, backend-backed).
  searchOrders: (params: OrderSearchParams = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    const q = qs.toString();
    return request<OrderPageDTO>(`/api/orders/search${q ? `?${q}` : ""}`);
  },
  orderMetricsSummary: () => request<OrderMetricsSummary>("/api/orders/metrics/summary"),
  getOrderEvents: (id: string) => request<OrderEventDTO[]>(`/api/orders/${id}/events`),
  getOrderConversation: (id: string) =>
    request<InboxConversationDTO>(`/api/orders/${id}/conversation`),
  updateOrderStatus: (id: string, status: string, actor_name?: string) =>
    request<OrderDTO>(`/api/orders/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, actor_name }),
    }),
};
