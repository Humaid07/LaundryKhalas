/**
 * Internal Ratings client → FastAPI `/api/internal/*` rating endpoints.
 *
 * Authorized internal operators rate facilities + drivers. The OFFICIAL overall
 * score is computed on the backend from the factor scores; the form shows a live
 * preview only. Internal notes stay internal; the partner-visible summary is a
 * separate, partner-safe field.
 */
import { getToken, clearSession } from "./auth-token";

const BASE_URL =
  process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8101";

export class RatingsApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "RatingsApiError";
  }
}

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return (body?.detail as string) ?? `Request failed (${res.status}).`;
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
    throw new RatingsApiError(0, "Could not reach the server. Is the backend running?");
  }
  if (res.status === 401) {
    clearSession();
    if (typeof window !== "undefined") window.location.assign("/login");
    throw new RatingsApiError(401, "Your session has expired. Please sign in again.");
  }
  if (!res.ok) throw new RatingsApiError(res.status, await detail(res));
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ------------------------------------------------------------------- types
export interface RatingFactorDef { key: string; label: string; weight: number }
export interface RatingFactorsResponse {
  scale: { min: number; max: number };
  facility_factors: RatingFactorDef[];
  driver_factors: RatingFactorDef[];
}
export interface EvaluationFactor {
  factor_key: string; factor_label: string; score: number;
  weight?: number; weighted_score?: number;
}
export interface InternalEvaluation {
  id: string;
  overall_score: number | null;
  partner_visible_summary?: string | null;
  internal_notes?: string | null;
  created_by_user_id?: string | null;
  updated_by_user_id?: string | null;
  evaluation_date?: string | null;
  evaluation_period_start?: string | null;
  evaluation_period_end?: string | null;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  factors: EvaluationFactor[];
}
export interface RatingFactorAverage {
  factor_key: string; factor_label: string; average: number; count: number;
}
export interface RatingSummary {
  overall_score: number | null;
  evaluation_count: number;
  latest_evaluation_date: string | null;
  factor_averages: RatingFactorAverage[];
  trend: { date?: string | null; overall_score: number }[];
}
export interface EvaluationInput {
  factors: { factor_key: string; score: number }[];
  evaluation_date?: string | null;
  evaluation_period_start?: string | null;
  evaluation_period_end?: string | null;
  partner_visible_summary?: string | null;
  internal_notes?: string | null;
  status?: string | null;
}
export interface DriverRow {
  id: string;
  name?: string | null;
  role?: string | null;
  phone_masked?: string | null;
  status?: string | null;
}

// --------------------------------------------------------------- factor defs
export const getRatingFactors = () =>
  req<RatingFactorsResponse>("/api/internal/rating-factors");

// ------------------------------------------------------------------ facility
export const getFacilityRating = (id: string) =>
  req<RatingSummary>(`/api/internal/facilities/${id}/rating`);

export const listFacilityEvaluations = (
  id: string, opts: { status?: string; limit?: number; offset?: number } = {},
) => {
  const q = new URLSearchParams();
  if (opts.status) q.set("status", opts.status);
  if (opts.limit != null) q.set("limit", String(opts.limit));
  if (opts.offset != null) q.set("offset", String(opts.offset));
  const qs = q.toString();
  return req<{ evaluations: InternalEvaluation[]; total: number; limit: number; offset: number }>(
    `/api/internal/facilities/${id}/evaluations${qs ? `?${qs}` : ""}`,
  );
};

export const createFacilityEvaluation = (id: string, body: EvaluationInput) =>
  req<InternalEvaluation>(`/api/internal/facilities/${id}/evaluations`, {
    method: "POST", body: JSON.stringify(body),
  });

export const updateFacilityEvaluation = (id: string, evaluationId: string, body: Partial<EvaluationInput>) =>
  req<InternalEvaluation>(`/api/internal/facilities/${id}/evaluations/${evaluationId}`, {
    method: "PATCH", body: JSON.stringify(body),
  });

export const getFacilityDrivers = (id: string) =>
  req<{ drivers: DriverRow[] }>(`/api/internal/facilities/${id}/drivers`);

// -------------------------------------------------------------------- driver
export const getDriverRating = (driverId: string) =>
  req<RatingSummary>(`/api/internal/drivers/${driverId}/rating`);

export const listDriverEvaluations = (
  driverId: string, opts: { status?: string; limit?: number; offset?: number } = {},
) => {
  const q = new URLSearchParams();
  if (opts.status) q.set("status", opts.status);
  if (opts.limit != null) q.set("limit", String(opts.limit));
  if (opts.offset != null) q.set("offset", String(opts.offset));
  const qs = q.toString();
  return req<{ evaluations: InternalEvaluation[]; total: number; limit: number; offset: number }>(
    `/api/internal/drivers/${driverId}/evaluations${qs ? `?${qs}` : ""}`,
  );
};

export const createDriverEvaluation = (driverId: string, body: EvaluationInput) =>
  req<InternalEvaluation>(`/api/internal/drivers/${driverId}/evaluations`, {
    method: "POST", body: JSON.stringify(body),
  });

export const updateDriverEvaluation = (driverId: string, evaluationId: string, body: Partial<EvaluationInput>) =>
  req<InternalEvaluation>(`/api/internal/drivers/${driverId}/evaluations/${evaluationId}`, {
    method: "PATCH", body: JSON.stringify(body),
  });
