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

export interface ClassificationDTO {
  id: string;
  conversation_id: string | null;
  message_id: string | null;
  classification_version: string;
  classifier_model: string | null;
  classifier_status: string;
  primary_intent: string;
  secondary_intents: string[];
  intent_confidence: number;
  service_domain: string;
  service_subtype: string | null;
  service_confidence: number;
  customer_goal: string;
  conversation_route: string;
  recommended_route: string | null;
  fixed_template_id: string | null;
  pricing_intent: string;
  payment_intent: string;
  repair_intent: string;
  complaint_type: string;
  sentiment: string;
  frustration_level: number;
  urgency: string;
  requires_human: boolean;
  human_reason: string | null;
  needs_clarification: boolean;
  clarification_topic: string | null;
  should_cancel_followups: boolean;
  reason_codes: string[];
  shadow_mode: boolean;
  latency_ms: number | null;
  estimated_cost: number;
  corrected_primary_intent: string | null;
  corrected_service_domain: string | null;
  corrected_complaint_type: string | null;
  corrected_human_label: string | null;
  corrected_by: string | null;
  corrected_at: string | null;
  correction_reason: string | null;
  created_at: string;
}

export interface ClassificationCorrectionPayload {
  corrected_by: string;
  primary_intent?: string | null;
  service_domain?: string | null;
  complaint_type?: string | null;
  human_label?: string | null;
  reason?: string | null;
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
 * An operational issue RAISED BY A FACILITY (from the separate facility app),
 * surfaced for the internal Operations team under Operations → Facility Facing.
 * PII-free by design: facility name + business order ref only — never a customer
 * phone/email/address. Backend: GET /api/internal/facility-issues.
 */
export interface FacilityIssueDTO {
  id: string;
  facility_id: string;
  facility_name: string;
  order_ref: string | null;
  issue_type: string;
  title: string;
  message: string;
  severity: string;   // critical | high | medium | low
  priority: string;   // urgent | high | medium | low
  status: string;     // open | acknowledged | waiting_on_facility | waiting_on_internal_team | resolved | closed
  assigned_internal_owner: string | null;
  created_at: string;
  updated_at: string;
}

/** A single message on a facility-issue thread (facility ↔ internal team). */
export interface FacilityIssueMessageDTO {
  id: string;
  sender_type: "facility" | "internal" | "system";
  sender_label: string;
  message: string;
  is_internal: boolean;   // true = internal-only note, not shown to the facility
  created_at: string;
}

/**
 * A single priced line on an order (from the backend catalogue-pricing layer).
 * All money is in `pricing.currency` (AED). `unit_price` / `line_total` are the
 * FINAL customer-facing amounts (the 5% adjustment is already included); the
 * accompanying `base_*` fields are the pre-adjustment amounts for INTERNAL
 * accounting only and must never be shown on customer-facing views.
 * Optional/nullable throughout so older payloads without item-level pricing
 * still type-check.
 */
export interface LineItemDTO {
  item_code: string;
  name: string;                 // canonical item name, e.g. "Shirt"
  quantity: number;
  pricing_unit: string;         // "ITEM" | "PAIR" | "BAG" | "KG" | "SQM"
  unit_price: number | null;    // AED, FINAL customer price
  is_starting_price: boolean;   // true = "From" price, not a guaranteed total
  requires_inspection: boolean;
  regular_price: number | null; // crossed-out earlier price, if any
  line_total: number | null;    // FINAL; null when pending inspection / no firm total
  line_kind: "exact" | "estimate" | "pending";
  base_unit_price?: number | null;  // INTERNAL accounting only — do not display
  base_line_total?: number | null;  // INTERNAL accounting only — do not display
}

/**
 * Order-level pricing roll-up returned alongside `line_items`.
 *
 * `final_price` is the customer-facing amount (5% already included) and is the
 * ONLY total to surface on customer-facing views. `subtotal_excluding_vat` /
 * `vat_amount` / `estimated_total_including_vat` remain for INTERNAL accounting
 * only and must NOT be rendered on any customer-facing surface.
 */
export interface OrderPricingDTO {
  currency: string;                          // "AED"
  final_price: number | null;                // FINAL customer-facing total
  is_estimated: boolean;                     // true => label total as "Estimated"
  has_pending_inspection: boolean;
  disclaimer: string;                        // e.g. "Prices may vary depending on item condition, material and brand."
  // --- INTERNAL accounting only (never shown to customers) ---
  vat_rate: number;                          // 0.05
  prices_include_vat: boolean;
  subtotal_excluding_vat: number | null;
  vat_amount: number | null;
  estimated_total_including_vat: number | null;
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
  // Order-discount snapshot (spec §§15, 29). Backend-authoritative.
  eligible_subtotal?: number | null;
  discount_percentage?: number | null;
  discount_amount?: number | null;
  discount_reason?: string | null;
  rule_version?: string | null;         // service rule-set version (spec §§17, 29)
  saved_address_reuse?: boolean | null; // reused a saved pickup address (spec §29)
  // Stripe-first payment surfacing (spec §§13, 29). Backend-authoritative.
  payment_preference?: "UNDECIDED" | "STRIPE" | "CASH_ON_DELIVERY";
  cash_on_delivery?: boolean;
  payment_status?: string;              // unpaid | pending | paid | failed | refunded | void
  payment_followup_stage?: number;
  stripe_hosted_invoice_url?: string | null;
  is_demo: boolean;
  // Order↔conversation link + dashboard-only fields (from /api/orders/search).
  conversation_id: string | null;
  customer_phone: string | null;
  assigned_persona?: string | null;     // customer's persistent AI persona (spec §29)
  customer_lifecycle?: string | null;   // §29 lifecycle stage
  facility_quote_status?: string | null;      // §29 cross-entity status
  facility_issue_status?: string | null;
  web_intent_status?: string | null;
  abandoned_followup_status?: string | null;
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

/**
 * A human-intervention (abuse/threat takeover) queue entry
 * (GET /api/human-intervention/queue). PII-safe: masked phone + a sanitized,
 * non-graphic preview only; the full message lives behind the conversation view.
 */
export interface HumanInterventionDTO {
  id: string;
  conversation_id: string;
  takeover_status:
    | "WAITING_FOR_HUMAN" | "ASSIGNED" | "HUMAN_ACTIVE" | "RESOLVED" | "RELEASED_TO_AI" | "CLOSED";
  takeover_reason: string;                 // ABUSIVE_LANGUAGE | THREAT | ...
  abuse_category: string | null;
  threat_severity: string | null;          // NONE | LOW | MEDIUM | HIGH | IMMINENT
  internal_priority: "NORMAL" | "MEDIUM" | "HIGH" | "CRITICAL";
  assigned_agent_id: string | null;
  assigned_agent_name: string | null;
  customer_notice_sent: boolean;
  flagged_at: string;
  accepted_at: string | null;
  sanitized_preview: string | null;
  customer_name: string | null;
  masked_phone: string | null;
  market: string | null;
  linked_order_id: string | null;
  unread_count: number;
  conversation_status: string;
}

export interface HumanInterventionMetrics {
  total?: number;
  waiting?: number;
  human_active?: number;
  resolved?: number;
  released_to_ai?: number;
  threats?: number;
  abusive?: number;
  critical?: number;
  avg_seconds_to_accept?: number | null;
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

/** GET binary content (an order photo) as a revocable object URL. The content
 *  endpoint is Bearer-guarded, so an <img src> can't hit it directly — fetch the
 *  bytes with the token and hand back a blob: URL the caller must revoke. */
async function requestObjectUrl(path: string): Promise<string> {
  let res: Response;
  const token = getToken();
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new AgentApiError(0, "Could not reach the WhatsApp agent backend. Is it running?");
  }
  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
    throw new AgentApiError(401, "Your session has expired. Please sign in again.");
  }
  if (!res.ok) throw new AgentApiError(res.status, res.statusText);
  return URL.createObjectURL(await res.blob());
}

/** PII-safe order-photo metadata (read-only ops view). Bytes fetched separately. */
export interface OrderPhotoDTO {
  id: string;
  stage: "intake" | "pre_dispatch" | string;
  file_name?: string | null;
  content_type?: string | null;
  file_size?: number | null;
  uploaded_by?: string | null;
  url?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
}

export interface OrderPhotosResponseDTO {
  photos: OrderPhotoDTO[];
  counts: { intake: number; pre_dispatch: number };
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

  // --- Human intervention (abuse/threat takeover) queue + actions ---
  humanInterventionQueue: (params: { status?: string; reason?: string; severity?: string;
    assigned_agent_id?: string; market?: string } = {}) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    const q = qs.toString();
    return request<HumanInterventionDTO[]>(`/api/human-intervention/queue${q ? `?${q}` : ""}`);
  },
  humanInterventionMetrics: () =>
    request<HumanInterventionMetrics>("/api/human-intervention/metrics"),
  claimIntervention: (id: string) =>
    request<HumanInterventionDTO>(`/api/human-intervention/${id}/claim`, { method: "POST" }),
  resolveIntervention: (id: string, resolution_reason?: string, close?: boolean) =>
    request<HumanInterventionDTO>(`/api/human-intervention/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ resolution_reason, close }),
    }),
  releaseInterventionToAi: (id: string) =>
    request<HumanInterventionDTO>(`/api/human-intervention/${id}/release-to-ai`, { method: "POST" }),

  // --- Flags ---
  listFlags: (status?: string) =>
    request<AgentFlagDTO[]>(`/api/flags${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  resolveFlag: (flagId: string) =>
    request<AgentFlagDTO>(`/api/flags/${flagId}/resolve`, { method: "POST" }),

  // --- Facility-raised issues (Operations → Facility Facing) ---
  listFacilityIssues: (status?: string) =>
    request<FacilityIssueDTO[]>(`/api/internal/facility-issues${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  getFacilityIssue: (id: string) =>
    request<FacilityIssueDTO>(`/api/internal/facility-issues/${id}`),
  getFacilityIssueMessages: (id: string) =>
    request<FacilityIssueMessageDTO[]>(`/api/internal/facility-issues/${id}/messages`),
  replyFacilityIssue: (id: string, message: string, isInternal?: boolean) =>
    request<FacilityIssueMessageDTO>(`/api/internal/facility-issues/${id}/reply`, {
      method: "POST",
      body: JSON.stringify({ message, is_internal: isInternal }),
    }),
  setFacilityIssueStatus: (id: string, status: string, owner?: string) =>
    request<FacilityIssueDTO>(`/api/internal/facility-issues/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, assigned_internal_owner: owner }),
    }),

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
  // Read-only ops view of an order's facility photos (intake + pre-dispatch).
  getOrderPhotos: (id: string) =>
    request<OrderPhotosResponseDTO>(`/api/orders/${id}/photos`),
  orderPhotoObjectUrl: (id: string, photoId: string) =>
    requestObjectUrl(`/api/orders/${id}/photos/${photoId}/content`),
  updateOrderStatus: (id: string, status: string, actor_name?: string) =>
    request<OrderDTO>(`/api/orders/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, actor_name }),
    }),

  // --- Intent classifier (read + Operations correction) ---
  listClassifications: (conversationId: string) =>
    request<ClassificationDTO[]>(`/api/conversations/${conversationId}/classifications`),
  correctClassification: (
    conversationId: string,
    classificationId: string,
    payload: ClassificationCorrectionPayload,
  ) =>
    request<ClassificationDTO>(
      `/api/conversations/${conversationId}/classifications/${classificationId}/correction`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
};
