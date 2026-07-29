/**
 * Internal Facilities Management client → FastAPI `/api/internal/facilities/*`.
 *
 * Sends the JWT bearer when present (dev admits a synthetic admin, so it works
 * without one). 401 → clear session + /login. Every write is validated + audited
 * server-side; internal rates + quality score are internal-only and never leave
 * the internal API. Mirrors the pricing-api.ts template.
 */
import { getToken, clearSession } from "./auth-token";

const BASE_URL =
  process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8101";

export type OperatingStatus = "open" | "busy" | "paused" | "closed";
export type CapacityUnit = "orders_per_day" | "kg_per_day" | "pieces_per_day";

export const EMIRATES = [
  "Abu Dhabi", "Dubai", "Sharjah", "Ajman",
  "Umm Al Quwain", "Ras Al Khaimah", "Fujairah",
] as const;

export const CAPACITY_UNITS: { value: CapacityUnit; label: string }[] = [
  { value: "orders_per_day", label: "Orders / day" },
  { value: "kg_per_day", label: "Kilograms / day" },
  { value: "pieces_per_day", label: "Pieces / day" },
];

export const STATUS_TONE: Record<OperatingStatus, "success" | "warning" | "neutral" | "danger"> = {
  open: "success",
  busy: "warning",
  paused: "neutral",
  closed: "danger",
};

export interface Facility {
  id: string;
  code?: string | null;
  name: string;
  full_address?: string | null;
  area?: string | null;
  city?: string | null;
  emirate?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  service_radius_km?: number | null;
  capacity_daily?: number | null;
  capacity_unit?: CapacityUnit | null;
  accepts_orders?: boolean;
  operating_status: OperatingStatus;
  is_active?: boolean;
  onboarding_source?: string | null;
  notes?: string | null;
  contact_area?: string | null;
  // internal-only (admin views):
  quality_score?: number | null;
  market?: string | null;
  country?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  // list/detail extras:
  service_codes?: string[];
  open_days?: number;
}

export interface FacilitySummary {
  total: number;
  open: number;
  busy: number;
  paused: number;
  closed: number;
}

export interface FacilityTiming {
  day_of_week: number;
  opens_at?: string | null;
  closes_at?: string | null;
  is_closed?: boolean;
  is_24h?: boolean;
}

export interface FacilityRate {
  id?: string;
  service_code: string;
  rate: number | null;
  currency: string;
  active?: boolean;
}

export interface FacilityAudit {
  id: string;
  action: string;
  actor_type: string;
  source_app?: string | null;
  created_at: string;
}

export interface CatalogueCategory {
  code: string;
  name: string;
  description?: string | null;
}

export interface FacilityDetail {
  facility: Facility;
  services: string[];
  timings: FacilityTiming[];
  audit: FacilityAudit[];
  // Internal rates are admin-only and fetched separately via getFacilityRates.
}

export interface FacilityInput {
  name?: string;
  full_address?: string | null;
  area?: string | null;
  city?: string | null;
  emirate?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  service_radius_km?: number | null;
  capacity_daily?: number | null;
  capacity_unit?: CapacityUnit | null;
  operating_status?: OperatingStatus;
  accepts_orders?: boolean;
  quality_score?: number | null;
  market?: string | null;
  country?: string | null;
  notes?: string | null;
  contact_area?: string | null;
  services?: string[];
}

export class FacilitiesApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      // FastAPI validation errors → readable message.
      return body.detail
        .map((e: { loc?: unknown[]; msg?: string }) =>
          `${(e.loc ?? []).slice(1).join(".")}: ${e.msg ?? "invalid"}`)
        .join("; ");
    }
    return `Request failed (${res.status}).`;
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
    throw new FacilitiesApiError(0, "Could not reach the server. Is the backend running?");
  }
  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined") window.location.assign("/login");
    throw new FacilitiesApiError(401, "Your session has expired. Please sign in again.");
  }
  if (!res.ok) throw new FacilitiesApiError(res.status, await detail(res));
  if (res.status === 204) return undefined as T;
  return res.json();
}

export interface FacilityFilters {
  search?: string;
  status?: string;
  emirate?: string;
  service?: string;
}

export const listFacilities = (f: FacilityFilters = {}) => {
  const qs = new URLSearchParams();
  if (f.search) qs.set("search", f.search);
  if (f.status) qs.set("status", f.status);
  if (f.emirate) qs.set("emirate", f.emirate);
  if (f.service) qs.set("service", f.service);
  const q = qs.toString();
  return req<{ facilities: Facility[]; summary: FacilitySummary }>(
    `/api/internal/facilities${q ? `?${q}` : ""}`,
  );
};

export const getFacility = (id: string) =>
  req<FacilityDetail>(`/api/internal/facilities/${id}`);

export const createFacility = (body: FacilityInput) =>
  req<Facility>("/api/internal/facilities", { method: "POST", body: JSON.stringify(body) });

export const updateFacility = (id: string, patch: FacilityInput) =>
  req<Facility>(`/api/internal/facilities/${id}`, { method: "PATCH", body: JSON.stringify(patch) });

export const setFacilityStatus = (id: string, status: OperatingStatus) =>
  req<Facility>(`/api/internal/facilities/${id}/status`, {
    method: "PATCH", body: JSON.stringify({ status }),
  });

export const setFacilityServices = (id: string, services: string[]) =>
  req<{ services: string[] }>(`/api/internal/facilities/${id}/services`, {
    method: "PUT", body: JSON.stringify({ services }),
  });

export const setFacilityTimings = (id: string, timings: FacilityTiming[]) =>
  req<{ timings: FacilityTiming[] }>(`/api/internal/facilities/${id}/timings`, {
    method: "PUT", body: JSON.stringify({ timings }),
  });

export const getFacilityRates = (id: string) =>
  req<{ rates: FacilityRate[] }>(`/api/internal/facilities/${id}/rates`);

export const setFacilityRate = (id: string, body: FacilityRate) =>
  req<FacilityRate>(`/api/internal/facilities/${id}/rates`, {
    method: "PUT",
    body: JSON.stringify({ service_code: body.service_code, rate: body.rate, currency: body.currency }),
  });

export const deleteFacilityRate = (id: string, serviceCode: string) =>
  req<{ deleted: boolean }>(
    `/api/internal/facilities/${id}/rates/${encodeURIComponent(serviceCode)}`,
    { method: "DELETE" },
  );

export const getCatalogueCategories = () =>
  req<CatalogueCategory[]>("/api/catalogue/categories");
