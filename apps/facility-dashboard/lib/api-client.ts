/**
 * Client for the LaundryKhalas FastAPI backend (:8100).
 *
 * The facility dashboard talks ONLY to this backend — never Supabase directly.
 * Every request injects `Authorization: Bearer <token>` from the stored session;
 * a 401 clears the session and bounces to /login. Types are intentionally
 * permissive — the backend returns plain JSON dicts and we only type the fields
 * the UI renders, so older/newer payloads still type-check.
 */
import { clearSession, getToken } from "./auth-token";

const BASE_URL = process.env.NEXT_PUBLIC_FACILITY_API_URL ?? "http://localhost:8100";

export class FacilityApiError extends Error {
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
    throw new FacilityApiError(
      0,
      "Could not reach the LaundryKhalas backend (:8100). Is it running?",
    );
  }
  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    }
    throw new FacilityApiError(401, "Your session has expired. Please sign in again.");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new FacilityApiError(res.status, detail);
  }
  // 204 No Content → return undefined cast to T.
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

function qs(params: Record<string, unknown> = {}): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

/* ----------------------------------------------------------- Normalizers ----
 * The backend was built in parallel with this app, so several payloads use
 * different field names / envelope shapes than the UI reads. These helpers
 * adapt the ACTUAL backend responses into the shapes the pages consume, so the
 * page components stay simple and never crash on a missing key.
 */

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

/** "08:00:00" → "08:00" for <input type="time">; null-safe. */
function hhmm(t?: string | null): string | null {
  if (!t || typeof t !== "string") return null;
  return t.slice(0, 5);
}

/** A backend period like "2026-07-23 00:00:00+00:00" → "23 Jul". */
function periodLabel(period?: string | null): string {
  if (!period) return "—";
  const d = new Date(String(period).replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return String(period);
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

type AnyRec = Record<string, unknown>;

/** Adapt a backend order (list item or detail) to the FacilityOrder shape.
 *  Crucially: backend orders have NO `id` — only `order_id` — so we alias it,
 *  because routing + list keys are built from `order.id`. */
function normalizeOrder(raw: AnyRec): FacilityOrderDetail {
  const o = raw as Record<string, unknown> & {
    order_id?: string;
    id?: string;
    items?: Array<{ name?: string; quantity?: unknown; measure?: unknown; note?: string | null }>;
    timeline?: FacilityOrderEvent[];
    events?: FacilityOrderEvent[];
    related_issues?: FacilityIssue[];
    issues?: FacilityIssue[];
    notes?: FacilityNote[];
  };
  // Line items come straight from a Supabase order snapshot, so field shapes are
  // untrusted: `measure` is usually a number (sqm/kg), `quantity` may be a float.
  // Keep raw values here (no coercion) and let the render layer format defensively.
  const items = Array.isArray(o.items) ? o.items : [];
  const lineItems: FacilityLineItem[] = items.map((it) => ({
    name: typeof it?.name === "string" ? it.name : undefined,
    quantity: typeof it?.quantity === "number" ? it.quantity : undefined,
    pricing_unit: (it?.measure ?? null) as string | number | null,
    note: it?.note ?? null,
  }));
  const orderId = (o.order_id ?? o.id) as string;
  return {
    ...(o as AnyRec),
    id: (o.id ?? o.order_id) as string,
    order_id: orderId,
    service_display_name:
      (o.service_display_name as string | undefined) ?? (o.service as string | undefined) ?? null,
    expected_at:
      (o.expected_at as string | undefined) ?? (o.pickup_start_time as string | undefined) ?? null,
    pickup_area: (o.pickup_area as string | undefined) ?? (o.area as string | undefined) ?? null,
    item_count:
      (o.item_count as number | undefined) ?? (items.length > 0 ? items.length : null),
    amount: (o.amount as number | undefined) ?? (o.order_value as number | undefined) ?? null,
    turnaround:
      (o.turnaround as string | undefined) ?? (o.turnaround_text as string | undefined) ?? null,
    line_items: (o.line_items as FacilityLineItem[] | undefined) ?? lineItems,
    events: (o.events as FacilityOrderEvent[] | undefined) ?? o.timeline ?? [],
    issues: (o.issues as FacilityIssue[] | undefined) ?? o.related_issues ?? [],
    notes: (o.notes as FacilityNote[] | undefined) ?? [],
  } as FacilityOrderDetail;
}

/* ---------------------------------------------------------------- Types ---- */

export type FacilityOperatingStatus = "accepting" | "paused" | "closed";

export interface FacilityProfile {
  id?: string;
  name?: string;
  area?: string | null;
  city?: string | null;
  operating_status?: FacilityOperatingStatus | string;
  role?: string;
  [key: string]: unknown;
}

export interface FacilityOverview {
  orders_in_today?: number;
  orders_out_today?: number;
  upcoming_count?: number;
  needs_attention_count?: number;
  service_value_today?: number;
  currency?: string;
  top_service_this_week?: string | null;
  top_service_orders?: number | null;
  next_arrival?: {
    order_id?: string;
    expected_at?: string | null;
    service?: string | null;
  } | null;
  latest_issue?: {
    id?: string;
    title?: string | null;
    status?: string | null;
    created_at?: string | null;
  } | null;
  operating_status?: FacilityOperatingStatus | string;
  [key: string]: unknown;
}

export interface FacilityLineItem {
  name?: string;
  quantity?: number;
  /** Unit label ("kg") OR a numeric measure (30 sqm) from the order snapshot —
   *  the value is not guaranteed to be a string. Render via `formatPricingUnit`. */
  pricing_unit?: string | number | null;
  note?: string | null;
  [key: string]: unknown;
}

export interface FacilityOrder {
  id: string;
  order_id?: string;
  service?: string | null;
  service_display_name?: string | null;
  status?: string | null;
  status_label?: string | null;
  bucket?: string | null;
  sla_status?: "on_track" | "due_soon" | "overdue" | string | null;
  expected_at?: string | null;
  pickup_area?: string | null;
  delivery_area?: string | null;
  item_count?: number | null;
  turnaround?: string | null;
  instructions?: string | null;
  amount?: number | null;
  currency?: string | null;
  line_items?: FacilityLineItem[];
  created_at?: string | null;
  updated_at?: string | null;
  [key: string]: unknown;
}

export interface FacilityOrderEvent {
  id?: string;
  event_type?: string;
  label?: string | null;
  notes?: string | null;
  actor_name?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
}

export interface FacilityNote {
  id?: string;
  note?: string;
  author?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
}

export interface FacilityOrderDetail extends FacilityOrder {
  events?: FacilityOrderEvent[];
  notes?: FacilityNote[];
  cleaning_details?: Record<string, unknown> | null;
  available_actions?: string[];
  issues?: FacilityIssue[];
  driver_assignment?: DriverAssignment | null;
  driver?: FacilityDriver | null;
}

export interface FacilityFinanceSummary {
  // Actual backend fields.
  currency?: string;
  order_count?: number;
  revenue_total?: number;
  revenue_total_display?: string;
  average_order_value?: number;
  average_order_value_display?: string;
  payout_status?: string;
  payout_amount?: number | null;
  date_from?: string;
  date_to?: string;
  // Aliases injected by the client for the pages that read these names.
  service_value_today?: number;
  service_value_week?: number;
  service_value_month?: number;
  completed_orders_value?: number;
  avg_order_value?: number;
  completed_orders?: number;
  pending_payout?: number | null;
  pending_payout_note?: string | null;
  [key: string]: unknown;
}

export interface FacilityRevenuePoint {
  label: string;
  value: number;
  [key: string]: string | number;
}

export interface FacilityServiceMix {
  service: string;
  value: number;
  orders?: number;
  [key: string]: unknown;
}

export interface FacilityPayout {
  id?: string;
  period?: string;
  amount?: number | null;
  status?: string;
  note?: string | null;
  [key: string]: unknown;
}

/** The payouts endpoint returns a single status object (not a list). */
export interface FacilityPayoutInfo {
  payout_status?: string;
  payout_amount?: number | null;
  currency?: string;
  note?: string | null;
  payouts?: FacilityPayout[];
  [key: string]: unknown;
}

export interface FacilityTeamMember {
  id?: string;
  name?: string;
  role?: string;
  masked_phone?: string | null;
  active?: boolean;
  [key: string]: unknown;
}

export interface FacilityTiming {
  day?: string;
  open?: string | null;
  close?: string | null;
  closed?: boolean;
  [key: string]: unknown;
}

export interface FacilityNotificationContact {
  id?: string;
  name?: string;
  channel?: string;
  masked_target?: string | null;
  types?: string[];
  enabled?: boolean;
  [key: string]: unknown;
}

export interface FacilityPriceRow {
  item?: string;
  category?: string | null;
  unit?: string | null;
  price?: number | null;
  currency?: string | null;
  [key: string]: unknown;
}

export interface FacilityIssue {
  id: string;
  issue_type?: string;
  title?: string | null;
  message?: string | null;
  status?: string;
  severity?: string | null;
  priority?: string | null;
  related_order_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  [key: string]: unknown;
}

export interface FacilityIssueMessage {
  id?: string;
  author_type?: "facility" | "internal" | "system" | string;
  author_name?: string | null;
  message?: string;
  created_at?: string | null;
  [key: string]: unknown;
}

export interface FacilityNotification {
  id: string;
  title?: string | null;
  body?: string | null;
  type?: string | null;
  read?: boolean;
  created_at?: string | null;
  related_order_id?: string | null;
  issue_id?: string | null;
  [key: string]: unknown;
}

/* ---------------------------------------------------------------- Drivers --- */

export type DriverTaskType = "pickup" | "facility_handoff" | "delivery" | "return";
export type DriverEffectiveStatus = "free" | "on_job" | "on_break" | "offline" | "issue";
export type DriverAssignmentStatus =
  | "assigned"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "issue";

export interface DriverAssignment {
  id: string;
  driver_id: string;
  order_id: string | null;
  order_ref: string | null;
  task_type: DriverTaskType;
  service_summary: string | null;
  status: DriverAssignmentStatus;
  assigned_at: string;
  started_at: string | null;
  completed_at: string | null;
  expected_completion_at: string | null;
  area: string | null;
  notes: string | null;
  [key: string]: unknown;
}

export interface FacilityDriver {
  id: string;
  facility_id: string;
  user_id: string | null;
  name: string;
  masked_phone: string | null;
  role: "driver" | "runner" | "pickup_partner";
  status: string;
  vehicle_type: string | null;
  area: string | null;
  active: boolean;
  last_active_at: string | null;
  created_at: string;
  updated_at: string;
  effective_status?: DriverEffectiveStatus;
  is_free?: boolean;
  current_assignment?: DriverAssignment | null;
  current_order_ref?: string | null;
  current_task?: string | null;
  [key: string]: unknown;
}

export interface FacilityDriverDetail extends FacilityDriver {
  assignments?: DriverAssignment[];
}

export interface DriverSummary {
  total: number;
  free: number;
  on_job: number;
  pickup: number;
  delivery: number;
  on_break: number;
  offline: number;
  issues: number;
  [key: string]: unknown;
}

export interface DriversResponse {
  drivers: FacilityDriver[];
  summary: DriverSummary;
}

export interface CreateDriverPayload {
  name: string;
  phone_e164?: string;
  role?: string;
  vehicle_type?: string;
  area?: string;
  active?: boolean;
}

export interface UpdateDriverPayload {
  name?: string;
  role?: string;
  phone_e164?: string;
  vehicle_type?: string;
  area?: string;
  active?: boolean;
}

export interface SetDriverStatusPayload {
  status: string;
  note?: string;
}

export interface CreateAssignmentPayload {
  driver_id: string;
  order_id: string;
  task_type?: DriverTaskType | string;
  expected_completion_at?: string;
  notes?: string;
}

export interface AssignDriverToOrderPayload {
  driver_id: string;
  task_type?: DriverTaskType | string;
  expected_completion_at?: string;
  notes?: string;
}

export interface AssignmentResult {
  assignment: DriverAssignment;
  driver: FacilityDriver;
}

const EMPTY_DRIVER_SUMMARY: DriverSummary = {
  total: 0,
  free: 0,
  on_job: 0,
  pickup: 0,
  delivery: 0,
  on_break: 0,
  offline: 0,
  issues: 0,
};

/* ------------------------------------------------------------- Requests ---- */

export interface OrderQuery {
  bucket?: string;
  range?: string;
  from?: string;
  to?: string;
  service?: string;
  status?: string;
}

export interface RaiseIssuePayload {
  issue_type: string;
  message: string;
  severity?: string;
  priority?: string;
  related_order_id?: string;
}

export const facilityApi = {
  baseUrl: BASE_URL,

  // --- Identity / overview ---
  me: () => request<FacilityProfile>("/api/facility/me"),
  overview: () => request<FacilityOverview>("/api/facility/overview"),

  // --- Orders ---
  // The backend returns a paginated envelope { orders, total, ... }; unwrap to
  // the array the UI consumes (tolerant of a bare-array response too).
  orders: async (params: OrderQuery = {}): Promise<FacilityOrder[]> => {
    const res = await request<{ orders?: AnyRec[] } | AnyRec[]>(
      `/api/facility/orders${qs(params as Record<string, unknown>)}`,
    );
    const list = Array.isArray(res) ? res : res?.orders ?? [];
    return list.map(normalizeOrder);
  },
  order: async (id: string): Promise<FacilityOrderDetail> => {
    const res = await request<AnyRec>(`/api/facility/orders/${id}`);
    return normalizeOrder(res);
  },
  updateOrderStatus: (id: string, action: string) =>
    request<FacilityOrderDetail>(`/api/facility/orders/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ action }),
    }),
  addOrderNote: (id: string, note: string) =>
    request<FacilityNote>(`/api/facility/orders/${id}/notes`, {
      method: "POST",
      body: JSON.stringify({ note }),
    }),
  raiseOrderIssue: (id: string, payload: RaiseIssuePayload) =>
    request<FacilityIssue>(`/api/facility/orders/${id}/issues`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // --- Finance ---
  // Backend summary uses revenue_total/order_count/average_order_value; alias to
  // the completed_orders_* / avg_order_value names the finance pages read.
  financeSummary: async (params: { range?: string } = {}): Promise<FacilityFinanceSummary> => {
    const s = await request<AnyRec>(`/api/facility/finance/summary${qs(params)}`);
    const revenueTotal = (s.revenue_total as number | undefined) ?? 0;
    const orderCount = (s.order_count as number | undefined) ?? 0;
    const avg = (s.average_order_value as number | undefined) ?? 0;
    return {
      ...(s as AnyRec),
      completed_orders_value: revenueTotal,
      completed_orders: orderCount,
      avg_order_value: avg,
      service_value_today: revenueTotal,
      service_value_week: revenueTotal,
      service_value_month: revenueTotal,
      pending_payout: (s.payout_amount as number | null | undefined) ?? null,
    } as FacilityFinanceSummary;
  },
  // Backend returns { granularity, series:[{period,count,value}] } → chart points.
  financeRevenue: async (
    params: { range?: string; granularity?: string } = {},
  ): Promise<FacilityRevenuePoint[]> => {
    const res = await request<{ series?: Array<AnyRec> } | AnyRec[]>(
      `/api/facility/finance/revenue${qs(params)}`,
    );
    const series = Array.isArray(res) ? res : res?.series ?? [];
    return series.map((p) => ({
      label: periodLabel(p.period as string | undefined),
      value: (p.value as number | undefined) ?? 0,
      count: (p.count as number | undefined) ?? 0,
    }));
  },
  // Backend returns { services:[{category,count,value}] } → service mix rows.
  financeServices: async (params: { range?: string } = {}): Promise<FacilityServiceMix[]> => {
    const res = await request<{ services?: Array<AnyRec> } | AnyRec[]>(
      `/api/facility/finance/services${qs(params)}`,
    );
    const rows = Array.isArray(res) ? res : res?.services ?? [];
    return rows.map((r) => ({
      service: (r.category as string | undefined) ?? (r.service as string | undefined) ?? "—",
      value: (r.value as number | undefined) ?? 0,
      orders: (r.count as number | undefined) ?? 0,
    }));
  },
  // Backend returns a single status object (payout intentionally pending).
  financePayouts: (params: { range?: string } = {}) =>
    request<FacilityPayoutInfo>(`/api/facility/finance/payouts${qs(params)}`),

  // --- Settings ---
  getProfileSettings: () => request<FacilityProfile>("/api/facility/settings/profile"),
  updateProfileSettings: (patch: Partial<FacilityProfile>) =>
    request<FacilityProfile>("/api/facility/settings/profile", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  getOperationsSettings: () =>
    request<Record<string, unknown>>("/api/facility/settings/operations"),
  updateOperationsSettings: (patch: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/facility/settings/operations", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  // Backend: { timings:[{day_of_week,opens_at,closes_at,is_closed,...}] }.
  getTimings: async (): Promise<FacilityTiming[]> => {
    const res = await request<{ timings?: Array<AnyRec> } | Array<AnyRec>>(
      "/api/facility/settings/timings",
    );
    const rows = Array.isArray(res) ? res : res?.timings ?? [];
    return rows.map((t) => ({
      ...(t as AnyRec),
      day: WEEKDAYS[(t.day_of_week as number | undefined) ?? 0] ?? String(t.day_of_week ?? ""),
      open: hhmm(t.opens_at as string | undefined),
      close: hhmm(t.closes_at as string | undefined),
      closed: (t.is_closed as boolean | undefined) ?? false,
    }));
  },
  updateTimings: (patch: { timings?: FacilityTiming[]; blackout_dates?: string[] }) =>
    request<FacilityTiming[]>("/api/facility/settings/timings", {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  // Backend: { items:[{item_code,name,category,unit,current_price,currency}] }.
  getPrices: async (): Promise<FacilityPriceRow[]> => {
    const res = await request<{ items?: Array<AnyRec> } | Array<AnyRec>>(
      "/api/facility/settings/prices",
    );
    const rows = Array.isArray(res) ? res : res?.items ?? [];
    return rows.map((r) => ({
      ...(r as AnyRec),
      item: (r.name as string | undefined) ?? (r.item as string | undefined) ?? "—",
      category: (r.category as string | undefined) ?? null,
      unit: (r.unit as string | undefined) ?? null,
      price: (r.current_price as number | undefined) ?? (r.price as number | undefined) ?? null,
      currency: (r.currency as string | undefined) ?? "AED",
    }));
  },
  requestPriceChange: (payload: { item?: string; requested_price?: number; reason: string }) =>
    request<{ ok: boolean }>("/api/facility/settings/prices/change-request", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // Backend: { team:[{name,role,phone_masked,status,...}] }.
  getTeam: async (): Promise<FacilityTeamMember[]> => {
    const res = await request<{ team?: Array<AnyRec> } | Array<AnyRec>>(
      "/api/facility/settings/team",
    );
    const rows = Array.isArray(res) ? res : res?.team ?? [];
    return rows.map((m) => ({
      ...(m as AnyRec),
      id: m.id as string | undefined,
      name: m.name as string | undefined,
      role: m.role as string | undefined,
      masked_phone:
        (m.masked_phone as string | undefined) ?? (m.phone_masked as string | undefined) ?? null,
      active: (m.active as boolean | undefined) ?? (m.status as string | undefined) !== "inactive",
    }));
  },
  addTeamMember: (payload: Partial<FacilityTeamMember>) =>
    request<FacilityTeamMember>("/api/facility/settings/team", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTeamMember: (id: string, patch: Partial<FacilityTeamMember>) =>
    request<FacilityTeamMember>(`/api/facility/settings/team/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  // Backend: { contacts:[{name,role,mobile_masked,notification_types,active}] }.
  getNotificationSettings: async (): Promise<FacilityNotificationContact[]> => {
    const res = await request<{ contacts?: Array<AnyRec> } | Array<AnyRec>>(
      "/api/facility/settings/notifications",
    );
    const rows = Array.isArray(res) ? res : res?.contacts ?? [];
    return rows.map((c) => ({
      ...(c as AnyRec),
      id: c.id as string | undefined,
      name: c.name as string | undefined,
      masked_target:
        (c.masked_target as string | undefined) ?? (c.mobile_masked as string | undefined) ?? null,
      types: (c.types as string[] | undefined) ?? (c.notification_types as string[] | undefined) ?? [],
      enabled: (c.enabled as boolean | undefined) ?? (c.active as boolean | undefined) ?? true,
    }));
  },
  addNotificationContact: (payload: Partial<FacilityNotificationContact>) =>
    request<FacilityNotificationContact>("/api/facility/settings/notifications", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateNotificationContact: (id: string, patch: Partial<FacilityNotificationContact>) =>
    request<FacilityNotificationContact>(`/api/facility/settings/notifications/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  // --- Issues ---
  // Backend returns a bare array; alias order_ref → related_order_id for links.
  issues: async (params: { status?: string } = {}): Promise<FacilityIssue[]> => {
    const res = await request<{ issues?: Array<AnyRec> } | Array<AnyRec>>(
      `/api/facility/issues${qs(params)}`,
    );
    const rows = Array.isArray(res) ? res : res?.issues ?? [];
    return rows.map((i) => ({
      ...(i as AnyRec),
      id: i.id as string,
      related_order_id:
        (i.related_order_id as string | undefined) ?? (i.order_ref as string | undefined) ?? null,
    }));
  },
  issue: async (id: string): Promise<FacilityIssue> => {
    const i = await request<AnyRec>(`/api/facility/issues/${id}`);
    return {
      ...(i as AnyRec),
      id: i.id as string,
      related_order_id:
        (i.related_order_id as string | undefined) ?? (i.order_ref as string | undefined) ?? null,
    };
  },
  createIssue: (payload: RaiseIssuePayload) =>
    request<FacilityIssue>("/api/facility/issues", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // Backend messages use sender_type/sender_label; alias to author_*.
  issueMessages: async (id: string): Promise<FacilityIssueMessage[]> => {
    const res = await request<{ messages?: Array<AnyRec> } | Array<AnyRec>>(
      `/api/facility/issues/${id}/messages`,
    );
    const rows = Array.isArray(res) ? res : res?.messages ?? [];
    return rows.map((m) => ({
      ...(m as AnyRec),
      id: m.id as string | undefined,
      author_type:
        (m.author_type as string | undefined) ?? (m.sender_type as string | undefined) ?? "facility",
      author_name:
        (m.author_name as string | undefined) ?? (m.sender_label as string | undefined) ?? null,
      message: m.message as string | undefined,
      created_at: m.created_at as string | undefined,
    }));
  },
  postIssueMessage: (id: string, message: string) =>
    request<FacilityIssueMessage>(`/api/facility/issues/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  resolveIssue: (id: string) =>
    request<FacilityIssue>(`/api/facility/issues/${id}/resolve`, { method: "POST" }),

  // --- Notifications ---
  // Backend: { notifications:[...], unread }.
  notifications: async (): Promise<FacilityNotification[]> => {
    const res = await request<{ notifications?: FacilityNotification[] } | FacilityNotification[]>(
      "/api/facility/notifications",
    );
    return Array.isArray(res) ? res : res?.notifications ?? [];
  },
  markNotificationRead: (id: string) =>
    request<{ ok: boolean }>(`/api/facility/notifications/${id}/read`, { method: "POST" }),
  // Backend: { unread }. Alias to { count } for the header/nav badge.
  unreadCount: async (): Promise<{ count: number }> => {
    const res = await request<{ unread?: number; count?: number }>(
      "/api/facility/notifications/unread-count",
    );
    return { count: res?.count ?? res?.unread ?? 0 };
  },

  // --- Drivers ---
  // Backend: { drivers:[...decorated], summary }. Tolerant of a bare array.
  drivers: async (): Promise<DriversResponse> => {
    const res = await request<{ drivers?: FacilityDriver[]; summary?: DriverSummary } | FacilityDriver[]>(
      "/api/facility/drivers",
    );
    if (Array.isArray(res)) return { drivers: res, summary: EMPTY_DRIVER_SUMMARY };
    return {
      drivers: res?.drivers ?? [],
      summary: res?.summary ?? EMPTY_DRIVER_SUMMARY,
    };
  },
  driversSummary: async (): Promise<DriverSummary> => {
    const res = await request<DriverSummary>("/api/facility/drivers/summary");
    return { ...EMPTY_DRIVER_SUMMARY, ...(res ?? {}) };
  },
  driver: (id: string) => request<FacilityDriverDetail>(`/api/facility/drivers/${id}`),
  driverAssignments: async (id: string): Promise<DriverAssignment[]> => {
    const res = await request<{ assignments?: DriverAssignment[] } | DriverAssignment[]>(
      `/api/facility/drivers/${id}/assignments`,
    );
    return Array.isArray(res) ? res : res?.assignments ?? [];
  },
  createDriver: (body: CreateDriverPayload) =>
    request<FacilityDriver>("/api/facility/drivers", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateDriver: (id: string, body: UpdateDriverPayload) =>
    request<FacilityDriver>(`/api/facility/drivers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  setDriverStatus: (id: string, body: SetDriverStatusPayload) =>
    request<FacilityDriver>(`/api/facility/drivers/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  createDriverAssignment: (body: CreateAssignmentPayload) =>
    request<AssignmentResult>("/api/facility/driver-assignments", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateAssignmentStatus: (id: string, body: { status: DriverAssignmentStatus | string }) =>
    request<DriverAssignment>(`/api/facility/driver-assignments/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  assignDriverToOrder: (orderId: string, body: AssignDriverToOrderPayload) =>
    request<AssignmentResult>(`/api/facility/orders/${orderId}/assign-driver`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
