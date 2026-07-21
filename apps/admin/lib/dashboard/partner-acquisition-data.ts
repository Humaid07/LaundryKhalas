/**
 * Partner Acquisition mock data — the partnership / business-development
 * command center. Deterministic, LaundryKhalas-specific, mock-only.
 *
 * PRIVACY: business-level data only. No private personal emails or phone
 * numbers in broad tables; compliance documents are status-only.
 */
import type { KpiStat, Tone, TimeSeriesPoint } from "./types";

/* --------------------------------- Team roles ------------------------------- */

export interface RoleCard {
  role: string;
  owner: string;
  initials: string;
  region: string;
  pipeline: number;
  activeTasks: number;
  meetingsThisWeek: number;
  targets: string;
  status: "On track" | "At risk" | "Ahead";
  responsibility: string;
}

export const roleCards: RoleCard[] = [
  {
    role: "Head of Partnership",
    owner: "Unassigned — hiring",
    initials: "HP",
    region: "Global oversight",
    pipeline: 42,
    activeTasks: 9,
    meetingsThisWeek: 6,
    targets: "12 partners / quarter",
    status: "On track",
    responsibility:
      "Overall partner strategy, pipeline ownership, deal approval, onboarding quality, region expansion planning and commercial negotiation overview.",
  },
  {
    role: "Marketing Intelligence Analyst",
    owner: "Unassigned — hiring",
    initials: "MI",
    region: "Global research",
    pipeline: 0,
    activeTasks: 14,
    meetingsThisWeek: 2,
    targets: "8 market reports / month",
    status: "On track",
    responsibility:
      "Market mapping, competitor/partner research, demand/supply analysis, area opportunity scoring, partner lead enrichment and region intelligence reports.",
  },
  {
    role: "Partner Executive — MENA / Asia",
    owner: "Unassigned — hiring",
    initials: "MA",
    region: "UAE · Qatar · KSA · Kuwait · Bahrain · Oman · India · Pakistan · SEA",
    pipeline: 26,
    activeTasks: 11,
    meetingsThisWeek: 5,
    targets: "8 partners / quarter",
    status: "Ahead",
    responsibility:
      "Partner outreach across MENA & Asia, partner qualification, meetings and onboarding coordination.",
  },
  {
    role: "Partner Executive — EU / Americas",
    owner: "Unassigned — hiring",
    initials: "EA",
    region: "Europe · UK · USA · Canada · Latin America",
    pipeline: 16,
    activeTasks: 7,
    meetingsThisWeek: 3,
    targets: "6 partners / quarter",
    status: "At risk",
    responsibility:
      "Partner outreach across EU & Americas, B2B/commercial partner pipeline and regional expansion partner discovery.",
  },
];

export const roleStatusTone: Record<RoleCard["status"], Tone> = {
  "On track": "success",
  Ahead: "rose",
  "At risk": "warning",
};

/* --------------------------------- KPI cards -------------------------------- */

const spark = (n: number[]) => n;

export const partnerKpis: KpiStat[] = [
  { label: "Total Partner Leads", value: "184", delta: 12.4, tone: "rose", spark: spark([120, 132, 141, 156, 165, 176, 184]) },
  { label: "Qualified Partners", value: "68", delta: 9.1, tone: "success", spark: spark([48, 52, 55, 58, 62, 65, 68]) },
  { label: "Active Outreach", value: "41", delta: 5.7, tone: "info", spark: spark([30, 33, 34, 37, 38, 40, 41]) },
  { label: "Meetings Scheduled", value: "17", delta: 21.4, tone: "plum", spark: spark([8, 10, 11, 13, 14, 16, 17]) },
  { label: "Contracts Sent", value: "9", delta: 12.5, tone: "warning", spark: spark([4, 5, 6, 6, 7, 8, 9]) },
  { label: "Partners Onboarded", value: "12", delta: 20.0, tone: "success", spark: spark([6, 7, 8, 9, 10, 11, 12]) },
  { label: "Pending Compliance Review", value: "6", delta: 2.0, tone: "warning", spark: spark([3, 4, 4, 5, 5, 6, 6]) },
  { label: "Region Coverage", value: "8 / 14", delta: 0, tone: "info", hint: "Regions with ≥1 active partner" },
  { label: "Average Partner Score", value: "72", delta: 3.4, tone: "rose", spark: spark([64, 66, 67, 68, 70, 71, 72]) },
  { label: "Conversion Rate", value: "18.5%", delta: 1.8, tone: "success", spark: spark([14, 15, 15.5, 16, 17, 18, 18.5]) },
  { label: "High-Priority Markets", value: "5", delta: 0, tone: "danger", hint: "Dubai · Doha · Riyadh · London · Toronto" },
  { label: "Follow-ups Due Today", value: "7", delta: 4.0, tone: "warning", spark: spark([3, 4, 5, 5, 6, 6, 7]) },
];

/* ------------------------------ Partner pipeline ---------------------------- */

export type PartnerType =
  | "Laundry Facility"
  | "Dry Cleaning Facility"
  | "Driver / Logistics Partner"
  | "Hotel / Hospitality Partner"
  | "Corporate / B2B Partner"
  | "Building / Community Partner"
  | "Franchise / Expansion Partner"
  | "Vendor / Supplier Partner";

export const PARTNER_TYPES: PartnerType[] = [
  "Laundry Facility",
  "Dry Cleaning Facility",
  "Driver / Logistics Partner",
  "Hotel / Hospitality Partner",
  "Corporate / B2B Partner",
  "Building / Community Partner",
  "Franchise / Expansion Partner",
  "Vendor / Supplier Partner",
];

export type PipelineStage =
  | "New Lead"
  | "Researching"
  | "Contacted"
  | "Qualified"
  | "Meeting Scheduled"
  | "Proposal Sent"
  | "Contract Sent"
  | "Compliance Review"
  | "Onboarding"
  | "Active Partner"
  | "Rejected / Not Fit";

export const PIPELINE_STAGES: PipelineStage[] = [
  "New Lead",
  "Researching",
  "Contacted",
  "Qualified",
  "Meeting Scheduled",
  "Proposal Sent",
  "Contract Sent",
  "Compliance Review",
  "Onboarding",
  "Active Partner",
  "Rejected / Not Fit",
];

export type ComplianceStatus =
  | "Not Started"
  | "In Review"
  | "Docs Pending"
  | "Passed"
  | "Flagged";

export const stageTone: Record<PipelineStage, Tone> = {
  "New Lead": "neutral",
  Researching: "info",
  Contacted: "info",
  Qualified: "plum",
  "Meeting Scheduled": "plum",
  "Proposal Sent": "warning",
  "Contract Sent": "warning",
  "Compliance Review": "rose",
  Onboarding: "rose",
  "Active Partner": "success",
  "Rejected / Not Fit": "danger",
};

export const complianceTone: Record<ComplianceStatus, Tone> = {
  "Not Started": "neutral",
  "In Review": "info",
  "Docs Pending": "warning",
  Passed: "success",
  Flagged: "danger",
};

export const REGIONS_PA = ["MENA", "Asia", "Europe", "Americas", "GCC"] as const;
export const PARTNER_OWNERS = [
  "Head of Partnership",
  "Partner Exec — MENA / Asia",
  "Partner Exec — EU / Americas",
  "Marketing Intelligence",
] as const;

export interface Partner {
  id: string;
  name: string;
  type: PartnerType;
  region: string;
  country: string;
  city: string;
  owner: string;
  stage: PipelineStage;
  score: number;
  lastContact: string;
  nextStep: string;
  compliance: ComplianceStatus;
}

export const partners: Partner[] = [
  { id: "PA-1001", name: "Dubai Marina Laundry Hub", type: "Laundry Facility", region: "GCC", country: "UAE", city: "Dubai", owner: "Partner Exec — MENA / Asia", stage: "Qualified", score: 84, lastContact: "2026-07-19T10:00:00Z", nextStep: "Send facility audit checklist", compliance: "In Review" },
  { id: "PA-1002", name: "Al Quoz Premium Cleaners", type: "Dry Cleaning Facility", region: "GCC", country: "UAE", city: "Dubai", owner: "Partner Exec — MENA / Asia", stage: "Contract Sent", score: 88, lastContact: "2026-07-18T13:30:00Z", nextStep: "Follow up on signed agreement", compliance: "Docs Pending" },
  { id: "PA-1003", name: "Doha West Bay Laundry Partner", type: "Laundry Facility", region: "GCC", country: "Qatar", city: "Doha", owner: "Partner Exec — MENA / Asia", stage: "Compliance Review", score: 79, lastContact: "2026-07-17T09:15:00Z", nextStep: "Verify trade license & insurance", compliance: "In Review" },
  { id: "PA-1004", name: "Riyadh Corporate Laundry Network", type: "Corporate / B2B Partner", region: "MENA", country: "Saudi Arabia", city: "Riyadh", owner: "Partner Exec — MENA / Asia", stage: "Meeting Scheduled", score: 76, lastContact: "2026-07-19T15:00:00Z", nextStep: "Commercial terms call Thu 11:00", compliance: "Not Started" },
  { id: "PA-1005", name: "London Hospitality Laundry Group", type: "Hotel / Hospitality Partner", region: "Europe", country: "United Kingdom", city: "London", owner: "Partner Exec — EU / Americas", stage: "Researching", score: 61, lastContact: "2026-07-15T11:00:00Z", nextStep: "Enrich contact + map demand", compliance: "Not Started" },
  { id: "PA-1006", name: "Toronto Condo Services Partner", type: "Building / Community Partner", region: "Americas", country: "Canada", city: "Toronto", owner: "Partner Exec — EU / Americas", stage: "Contacted", score: 58, lastContact: "2026-07-16T18:00:00Z", nextStep: "Await reply to intro email", compliance: "Not Started" },
  { id: "PA-1007", name: "Abu Dhabi Corniche Cleaners", type: "Laundry Facility", region: "GCC", country: "UAE", city: "Abu Dhabi", owner: "Partner Exec — MENA / Asia", stage: "Active Partner", score: 91, lastContact: "2026-07-14T08:30:00Z", nextStep: "Onboarding complete — monitor", compliance: "Passed" },
  { id: "PA-1008", name: "Mumbai Express Dhobi Network", type: "Driver / Logistics Partner", region: "Asia", country: "India", city: "Mumbai", owner: "Partner Exec — MENA / Asia", stage: "New Lead", score: 44, lastContact: "—", nextStep: "Qualify demand & capacity", compliance: "Not Started" },
  { id: "PA-1009", name: "Karachi Clifton Laundry Co.", type: "Laundry Facility", region: "Asia", country: "Pakistan", city: "Karachi", owner: "Partner Exec — MENA / Asia", stage: "Researching", score: 52, lastContact: "2026-07-13T12:00:00Z", nextStep: "Market readiness assessment", compliance: "Not Started" },
  { id: "PA-1010", name: "Manama Seef Dry Cleaning", type: "Dry Cleaning Facility", region: "GCC", country: "Bahrain", city: "Manama", owner: "Partner Exec — MENA / Asia", stage: "Proposal Sent", score: 73, lastContact: "2026-07-18T10:45:00Z", nextStep: "Review proposal feedback", compliance: "Not Started" },
  { id: "PA-1011", name: "Kuwait City Salmiya Laundry", type: "Laundry Facility", region: "GCC", country: "Kuwait", city: "Kuwait City", owner: "Partner Exec — MENA / Asia", stage: "Qualified", score: 70, lastContact: "2026-07-17T14:20:00Z", nextStep: "Schedule facility visit", compliance: "Not Started" },
  { id: "PA-1012", name: "New York Midtown Wash Partners", type: "Corporate / B2B Partner", region: "Americas", country: "USA", city: "New York", owner: "Partner Exec — EU / Americas", stage: "New Lead", score: 40, lastContact: "—", nextStep: "Research corporate demand", compliance: "Not Started" },
  { id: "PA-1013", name: "Singapore Marina Linen Services", type: "Hotel / Hospitality Partner", region: "Asia", country: "Singapore", city: "Singapore", owner: "Partner Exec — MENA / Asia", stage: "Contacted", score: 64, lastContact: "2026-07-16T07:00:00Z", nextStep: "Book intro meeting", compliance: "Not Started" },
  { id: "PA-1014", name: "Muscat Al Khuwair Cleaners", type: "Laundry Facility", region: "GCC", country: "Oman", city: "Muscat", owner: "Partner Exec — MENA / Asia", stage: "Onboarding", score: 82, lastContact: "2026-07-19T09:00:00Z", nextStep: "Complete payout & training setup", compliance: "Docs Pending" },
  { id: "PA-1015", name: "Sharjah Industrial Supply Co.", type: "Vendor / Supplier Partner", region: "GCC", country: "UAE", city: "Sharjah", owner: "Head of Partnership", stage: "Rejected / Not Fit", score: 31, lastContact: "2026-07-12T16:00:00Z", nextStep: "Archived — capacity too low", compliance: "Not Started" },
  { id: "PA-1016", name: "Berlin Mitte Laundry Franchise", type: "Franchise / Expansion Partner", region: "Europe", country: "Germany", city: "Berlin", owner: "Partner Exec — EU / Americas", stage: "Researching", score: 55, lastContact: "2026-07-15T13:00:00Z", nextStep: "Assess franchise model fit", compliance: "Not Started" },
];

export const PARTNER_ACTIONS = [
  "View Partner",
  "Assign Owner",
  "Schedule Follow-up",
  "Move Stage",
  "Request Compliance Review",
  "Add Note",
  "Mark Onboarded",
  "Reject Lead",
];

/* ----------------------------- Market intelligence -------------------------- */

export interface MarketRow {
  country: string;
  city: string;
  region: string;
  opportunity: number; // 0–100
  demand: "Low" | "Medium" | "High" | "Very High";
  supply: "Scarce" | "Limited" | "Balanced" | "Saturated";
  competitors: number;
  suggestedCategory: PartnerType;
  readiness: "Explore" | "Warm" | "Ready" | "Priority";
}

export const marketIntel: MarketRow[] = [
  { country: "UAE", city: "Dubai", region: "GCC", opportunity: 92, demand: "Very High", supply: "Balanced", competitors: 14, suggestedCategory: "Laundry Facility", readiness: "Priority" },
  { country: "Qatar", city: "Doha", region: "GCC", opportunity: 81, demand: "High", supply: "Limited", competitors: 7, suggestedCategory: "Laundry Facility", readiness: "Ready" },
  { country: "Saudi Arabia", city: "Riyadh", region: "MENA", opportunity: 88, demand: "Very High", supply: "Limited", competitors: 9, suggestedCategory: "Corporate / B2B Partner", readiness: "Priority" },
  { country: "United Kingdom", city: "London", region: "Europe", opportunity: 74, demand: "High", supply: "Saturated", competitors: 22, suggestedCategory: "Hotel / Hospitality Partner", readiness: "Warm" },
  { country: "Canada", city: "Toronto", region: "Americas", opportunity: 66, demand: "Medium", supply: "Balanced", competitors: 11, suggestedCategory: "Building / Community Partner", readiness: "Warm" },
  { country: "India", city: "Mumbai", region: "Asia", opportunity: 71, demand: "High", supply: "Scarce", competitors: 6, suggestedCategory: "Driver / Logistics Partner", readiness: "Explore" },
  { country: "Pakistan", city: "Karachi", region: "Asia", opportunity: 63, demand: "Medium", supply: "Scarce", competitors: 4, suggestedCategory: "Laundry Facility", readiness: "Explore" },
  { country: "Singapore", city: "Singapore", region: "Asia", opportunity: 69, demand: "Medium", supply: "Limited", competitors: 8, suggestedCategory: "Hotel / Hospitality Partner", readiness: "Warm" },
];

export const readinessTone: Record<MarketRow["readiness"], Tone> = {
  Explore: "neutral",
  Warm: "info",
  Ready: "rose",
  Priority: "success",
};

/* ------------------------------ Outreach tracker ---------------------------- */

export interface OutreachRow {
  region: string;
  sent: number;
  replies: number;
  meetings: number;
  followupsDue: number;
  responseRate: number;
}

export const outreach: OutreachRow[] = [
  { region: "GCC", sent: 86, replies: 41, meetings: 11, followupsDue: 4, responseRate: 47.7 },
  { region: "MENA", sent: 52, replies: 19, meetings: 4, followupsDue: 2, responseRate: 36.5 },
  { region: "Asia", sent: 44, replies: 12, meetings: 3, followupsDue: 1, responseRate: 27.3 },
  { region: "Europe", sent: 38, replies: 9, meetings: 2, followupsDue: 0, responseRate: 23.7 },
  { region: "Americas", sent: 29, replies: 6, meetings: 1, followupsDue: 0, responseRate: 20.7 },
];

/* --------------------------- Meetings & follow-ups -------------------------- */

export interface MeetingRow {
  id: string;
  partner: string;
  owner: string;
  datetime: string;
  type: "Intro Call" | "Facility Visit" | "Commercial Terms" | "Onboarding" | "Follow-up";
  nextAction: string;
  status: "Scheduled" | "Confirmed" | "Awaiting Reply" | "Done";
  // Geo mirrored from the matched partner (see `partners`) so global filters slice meetings.
  region: string;
  country: string;
  city: string;
}

export const meetings: MeetingRow[] = [
  { id: "MTG-201", partner: "Riyadh Corporate Laundry Network", owner: "Partner Exec — MENA / Asia", datetime: "2026-07-23T08:00:00Z", type: "Commercial Terms", nextAction: "Prepare pricing sheet", status: "Confirmed", region: "MENA", country: "Saudi Arabia", city: "Riyadh" },
  { id: "MTG-202", partner: "Dubai Marina Laundry Hub", owner: "Partner Exec — MENA / Asia", datetime: "2026-07-22T11:30:00Z", type: "Facility Visit", nextAction: "Run quality checklist on site", status: "Scheduled", region: "GCC", country: "UAE", city: "Dubai" },
  { id: "MTG-203", partner: "Singapore Marina Linen Services", owner: "Partner Exec — MENA / Asia", datetime: "2026-07-24T04:00:00Z", type: "Intro Call", nextAction: "Confirm timezone with partner", status: "Awaiting Reply", region: "Asia", country: "Singapore", city: "Singapore" },
  { id: "MTG-204", partner: "Muscat Al Khuwair Cleaners", owner: "Partner Exec — MENA / Asia", datetime: "2026-07-21T09:30:00Z", type: "Onboarding", nextAction: "Walk through payout setup", status: "Confirmed", region: "GCC", country: "Oman", city: "Muscat" },
  { id: "MTG-205", partner: "London Hospitality Laundry Group", owner: "Partner Exec — EU / Americas", datetime: "2026-07-25T10:00:00Z", type: "Intro Call", nextAction: "Send agenda + deck", status: "Scheduled", region: "Europe", country: "United Kingdom", city: "London" },
  { id: "MTG-206", partner: "Abu Dhabi Corniche Cleaners", owner: "Partner Exec — MENA / Asia", datetime: "2026-07-20T08:00:00Z", type: "Follow-up", nextAction: "Confirm first-week volumes", status: "Done", region: "GCC", country: "UAE", city: "Abu Dhabi" },
];

export const meetingStatusTone: Record<MeetingRow["status"], Tone> = {
  Scheduled: "info",
  Confirmed: "success",
  "Awaiting Reply": "warning",
  Done: "neutral",
};

/* ------------------------------ Compliance queue ---------------------------- */

export type DocState = "Pending" | "Received" | "Verified" | "Expired" | "N/A";

export interface ComplianceRow {
  partner: string;
  country: string;
  // City + region inferred from the matched partner (see `partners`) so global filters slice the queue.
  city: string;
  region: string;
  tradeLicense: DocState;
  bankPayout: DocState;
  qualityChecklist: DocState;
  agreement: DocState;
  insurance: DocState;
  pending: number;
  status: ComplianceStatus;
}

export const complianceQueue: ComplianceRow[] = [
  { partner: "Al Quoz Premium Cleaners", country: "UAE", city: "Dubai", region: "GCC", tradeLicense: "Verified", bankPayout: "Received", qualityChecklist: "Verified", agreement: "Pending", insurance: "Received", pending: 1, status: "Docs Pending" },
  { partner: "Doha West Bay Laundry Partner", country: "Qatar", city: "Doha", region: "GCC", tradeLicense: "Received", bankPayout: "Pending", qualityChecklist: "Received", agreement: "Pending", insurance: "Pending", pending: 3, status: "In Review" },
  { partner: "Dubai Marina Laundry Hub", country: "UAE", city: "Dubai", region: "GCC", tradeLicense: "Received", bankPayout: "Pending", qualityChecklist: "Pending", agreement: "N/A", insurance: "Pending", pending: 3, status: "In Review" },
  { partner: "Muscat Al Khuwair Cleaners", country: "Oman", city: "Muscat", region: "GCC", tradeLicense: "Verified", bankPayout: "Pending", qualityChecklist: "Verified", agreement: "Received", insurance: "Pending", pending: 2, status: "Docs Pending" },
  { partner: "Abu Dhabi Corniche Cleaners", country: "UAE", city: "Abu Dhabi", region: "GCC", tradeLicense: "Verified", bankPayout: "Verified", qualityChecklist: "Verified", agreement: "Verified", insurance: "Verified", pending: 0, status: "Passed" },
  { partner: "Sharjah Industrial Supply Co.", country: "UAE", city: "Sharjah", region: "GCC", tradeLicense: "Expired", bankPayout: "N/A", qualityChecklist: "Pending", agreement: "N/A", insurance: "Pending", pending: 3, status: "Flagged" },
];

export const docStateTone: Record<DocState, Tone> = {
  Pending: "warning",
  Received: "info",
  Verified: "success",
  Expired: "danger",
  "N/A": "neutral",
};

/* ------------------------------ Regional coverage --------------------------- */

export interface CoverageRow {
  region: string;
  activePartners: number;
  pipeline: number;
  targetMarkets: number;
  covered: number;
  status: "Strong" | "Building" | "Early" | "Gap";
}

export const regionalCoverage: CoverageRow[] = [
  { region: "GCC", activePartners: 9, pipeline: 21, targetMarkets: 6, covered: 6, status: "Strong" },
  { region: "UAE", activePartners: 5, pipeline: 8, targetMarkets: 3, covered: 3, status: "Strong" },
  { region: "Qatar", activePartners: 1, pipeline: 3, targetMarkets: 1, covered: 1, status: "Building" },
  { region: "Saudi Arabia", activePartners: 1, pipeline: 4, targetMarkets: 3, covered: 1, status: "Building" },
  { region: "MENA", activePartners: 2, pipeline: 9, targetMarkets: 8, covered: 3, status: "Building" },
  { region: "Asia", activePartners: 0, pipeline: 7, targetMarkets: 6, covered: 0, status: "Early" },
  { region: "Europe", activePartners: 0, pipeline: 5, targetMarkets: 5, covered: 0, status: "Early" },
  { region: "Americas", activePartners: 0, pipeline: 4, targetMarkets: 4, covered: 0, status: "Gap" },
];

export const coverageStatusTone: Record<CoverageRow["status"], Tone> = {
  Strong: "success",
  Building: "rose",
  Early: "info",
  Gap: "warning",
};

/* -------------------------- Partner performance preview --------------------- */

export interface PerformancePreviewRow {
  partner: string;
  city: string;
  ordersHandled: number;
  avgTurnaround: string;
  qualityScore: number;
  complaintRate: number;
  revenueShare: number;
}

export const performancePreview: PerformancePreviewRow[] = [
  { partner: "Abu Dhabi Corniche Cleaners", city: "Abu Dhabi", ordersHandled: 412, avgTurnaround: "22h", qualityScore: 94, complaintRate: 1.2, revenueShare: 8.4 },
  { partner: "Muscat Al Khuwair Cleaners", city: "Muscat", ordersHandled: 61, avgTurnaround: "28h", qualityScore: 88, complaintRate: 2.1, revenueShare: 1.3 },
];

/* ---------------------------------- Charts ---------------------------------- */

export const leadsByRegion: TimeSeriesPoint[] = [
  { label: "GCC", value: 74 },
  { label: "MENA", value: 38 },
  { label: "Asia", value: 34 },
  { label: "Europe", value: 22 },
  { label: "Americas", value: 16 },
];

export const pipelineByStage: TimeSeriesPoint[] = [
  { label: "New Lead", value: 22 },
  { label: "Researching", value: 18 },
  { label: "Contacted", value: 16 },
  { label: "Qualified", value: 14 },
  { label: "Meeting", value: 9 },
  { label: "Proposal", value: 7 },
  { label: "Contract", value: 5 },
  { label: "Compliance", value: 6 },
  { label: "Onboarding", value: 3 },
  { label: "Active", value: 12 },
];

export const scoreDistribution: TimeSeriesPoint[] = [
  { label: "0–40", value: 18 },
  { label: "41–60", value: 46 },
  { label: "61–75", value: 62 },
  { label: "76–90", value: 44 },
  { label: "91–100", value: 14 },
];

export const meetingsOverTime: TimeSeriesPoint[] = [
  { label: "Wk 1", Meetings: 4 },
  { label: "Wk 2", Meetings: 7 },
  { label: "Wk 3", Meetings: 9 },
  { label: "Wk 4", Meetings: 11 },
  { label: "Wk 5", Meetings: 14 },
  { label: "Wk 6", Meetings: 17 },
];

export const outreachConversion: TimeSeriesPoint[] = outreach.map((o) => ({ label: o.region, value: o.responseRate }));

export const complianceBreakdown: TimeSeriesPoint[] = [
  { label: "Passed", value: 12 },
  { label: "In Review", value: 9 },
  { label: "Docs Pending", value: 6 },
  { label: "Not Started", value: 28 },
  { label: "Flagged", value: 3 },
];

export const partnerTypeBreakdown: TimeSeriesPoint[] = [
  { label: "Laundry Facility", value: 62 },
  { label: "Dry Cleaning", value: 28 },
  { label: "Logistics", value: 18 },
  { label: "Hospitality", value: 22 },
  { label: "Corporate / B2B", value: 26 },
  { label: "Building / Community", value: 14 },
  { label: "Franchise", value: 8 },
  { label: "Vendor / Supplier", value: 6 },
];

export const marketReadiness: TimeSeriesPoint[] = marketIntel.map((m) => ({ label: m.city, value: m.opportunity }));

/* --------------------------------- Activity --------------------------------- */

export interface PartnerActivity {
  id: string;
  title: string;
  detail: string;
  time: string;
  tone: Tone;
}

export const partnerActivity: PartnerActivity[] = [
  { id: "pa1", title: "Contract sent", detail: "Al Quoz Premium Cleaners · awaiting signature", time: "2026-07-20T09:20:00Z", tone: "warning" },
  { id: "pa2", title: "New qualified partner", detail: "Kuwait City Salmiya Laundry moved to Qualified", time: "2026-07-20T08:50:00Z", tone: "success" },
  { id: "pa3", title: "Compliance flagged", detail: "Sharjah Industrial Supply Co. · trade license expired", time: "2026-07-20T08:10:00Z", tone: "danger" },
  { id: "pa4", title: "Meeting confirmed", detail: "Riyadh Corporate Laundry Network · Thu 11:00", time: "2026-07-19T16:30:00Z", tone: "plum" },
  { id: "pa5", title: "Market report published", detail: "Asia demand/supply mapping — Mumbai & Karachi", time: "2026-07-19T14:00:00Z", tone: "info" },
];
