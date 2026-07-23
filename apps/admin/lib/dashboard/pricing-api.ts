/**
 * Admin pricing-management client → FastAPI `/api/admin/pricing/*`.
 *
 * Sends the JWT bearer when present (in dev the backend admits a synthetic admin,
 * so it works without one). 401 → clear session + /login. Every write is audited
 * and permission-checked server-side; the UI additionally hides actions the user
 * lacks (from `getMyPricingPermissions`) — UX only, the backend is the real gate.
 */
import { getToken, clearSession } from "./auth-token";

const BASE_URL =
  process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8101";

export interface PricingItem {
  item_code: string;
  category_code?: string | null;
  category_name?: string | null;
  service_code?: string | null;
  canonical_name: string;
  display_name?: string | null;
  description?: string | null;
  pricing_type: string;
  pricing_unit: string;
  current_price?: number | null;
  regular_price?: number | null;
  currency: string;
  is_starting_price: boolean;
  requires_inspection: boolean;
  active: boolean;
  effective_price?: number | null;
  price_source?: string;
  disclaimer?: string | null;
  internal_note?: string | null;
  sort_order?: number;
}

export interface CatalogueSnapshot {
  catalogue_version: number | null;
  market: string;
  items: PricingItem[];
}

export interface PricingVersion {
  id: string;
  version_number: number;
  status: string;
  is_current: boolean;
  market: string;
  change_summary?: string | null;
  source?: string | null;
  rollback_of_version?: number | null;
  created_by?: string | null;
  published_by?: string | null;
  created_at?: string | null;
  published_at?: string | null;
  effective_at?: string | null;
}

export interface DiffEntry {
  item_code: string;
  name?: string;
  change: "added" | "modified" | "removed";
  fields?: Record<string, { old: unknown; new: unknown }>;
}

export interface Promotion {
  id: string;
  item_code: string;
  name: string;
  promo_price: number;
  active: boolean;
  priority: number;
  starts_at?: string | null;
  ends_at?: string | null;
}

export interface HistoryEntry {
  action: string;
  entity_type: string;
  entity_ref?: string | null;
  field?: string | null;
  old_value?: string | null;
  new_value?: string | null;
  actor?: string | null;
  created_at?: string | null;
}

export interface SyncStatus {
  published_version: number | null;
  published_at?: string | null;
  sync: { target: string; version_number: number | null; status: string; detail?: string | null; attempted_at?: string | null }[];
}

export class PricingApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function detail(res: Response): Promise<string> {
  try {
    return (await res.json()).detail ?? `Request failed (${res.status}).`;
  } catch {
    return `Request failed (${res.status}).`;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    throw new PricingApiError(0, "Could not reach the server. Is the backend running?");
  }
  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined") window.location.assign("/login");
    throw new PricingApiError(401, "Your session has expired. Please sign in again.");
  }
  if (!res.ok) throw new PricingApiError(res.status, await detail(res));
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const getMyPricingPermissions = () =>
  req<{ role: string | null; permissions: string[] }>("/api/admin/pricing/permissions");
export const getCurrentItems = (market = "AE") =>
  req<CatalogueSnapshot>(`/api/admin/pricing/items?market=${market}`);
export const getVersions = (market = "AE") =>
  req<{ versions: PricingVersion[] }>(`/api/admin/pricing/versions?market=${market}`);
export const getVersion = (id: string) =>
  req<{ version: PricingVersion; items: PricingItem[]; diff: DiffEntry[] }>(`/api/admin/pricing/versions/${id}`);
export const createDraft = (change_summary?: string, market = "AE") =>
  req<PricingVersion>("/api/admin/pricing/versions", { method: "POST", body: JSON.stringify({ change_summary, market }) });
export const patchItem = (versionId: string, itemCode: string, changes: Record<string, unknown>, expected_updated?: string) =>
  req<PricingItem>(`/api/admin/pricing/versions/${versionId}/items/${encodeURIComponent(itemCode)}`, {
    method: "PATCH", body: JSON.stringify({ changes, expected_updated }),
  });
export const publishVersion = (versionId: string, effective_at?: string) =>
  req<PricingVersion>(`/api/admin/pricing/versions/${versionId}/publish`, { method: "POST", body: JSON.stringify({ effective_at }) });
export const rollbackTo = (versionNumber: number, reason?: string, market = "AE") =>
  req<PricingVersion>(`/api/admin/pricing/versions/${versionNumber}/rollback`, { method: "POST", body: JSON.stringify({ reason, market }) });
export const getPromotions = (market = "AE") =>
  req<{ promotions: Promotion[] }>(`/api/admin/pricing/promotions?market=${market}`);
export const createPromotion = (body: { item_code: string; name: string; promo_price: number; starts_at?: string; ends_at?: string; priority?: number; market?: string }) =>
  req<{ id: string }>("/api/admin/pricing/promotions", { method: "POST", body: JSON.stringify(body) });
export const endPromotion = (id: string) =>
  req<{ id: string; active: boolean }>(`/api/admin/pricing/promotions/${id}/end`, { method: "POST" });
export const getHistory = (limit = 100) =>
  req<{ history: HistoryEntry[] }>(`/api/admin/pricing/history?limit=${limit}`);
export const getSyncStatus = (market = "AE") =>
  req<SyncStatus>(`/api/admin/pricing/sync-status?market=${market}`);
