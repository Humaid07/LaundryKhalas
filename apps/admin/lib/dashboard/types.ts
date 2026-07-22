/** Shared types for the internal dashboard (mock domain model). */

export type Market = "UAE" | "Qatar" | "Saudi Arabia" | "Kuwait" | "Bahrain" | "Oman";

export type City =
  | "Dubai"
  | "Abu Dhabi"
  | "Sharjah"
  | "Doha"
  | "Riyadh"
  | "Kuwait City"
  | "Manama"
  | "Muscat";

export type Channel = "WhatsApp" | "Website" | "App" | "Walk-in" | "B2B";

// Canonical LaundryKhalas 8-service taxonomy (mirror of service-catalog.ts /
// the backend catalog). These exact display names are the values used by every
// mock Order.service field and the global Service filter.
export type ServiceType =
  | "Premium Wash & Fold"
  | "Boutique Clean & Press"
  | "Steam Pressing Only"
  | "Luxe Bed & Bath Care"
  | "Artisan Shoe Restoration"
  | "Luxury Bag Spa"
  | "Tailoring & Alterations"
  | "Deep Carpet & Curtain Care";

export type OrderStatus =
  | "New"
  | "Pickup Scheduled"
  | "Driver Assigned"
  | "Picked Up"
  | "In Cleaning"
  | "Ready for Delivery"
  | "Out for Delivery"
  | "Delivered"
  | "Cancelled"
  | "Concern Raised";

export type PaymentStatus = "Paid" | "Pending" | "Refunded" | "Failed";

export type AgentStatus =
  | "Active"
  | "Scheduled"
  | "Needs Review"
  | "Awaiting Approval"
  | "Paused"
  | "Failed";

export type Tone = "rose" | "success" | "warning" | "danger" | "info" | "neutral" | "plum";

export interface KpiStat {
  label: string;
  value: string;
  raw?: number;
  delta?: number; // percent change vs previous period
  deltaLabel?: string;
  spark?: number[];
  tone?: Tone;
  hint?: string;
}

export interface Order {
  id: string;
  customer: string;
  phone: string;
  service: ServiceType;
  channel: Channel;
  city: City;
  market: Market;
  status: OrderStatus;
  pickupSlot: string;
  driver: string | null;
  facility: string;
  amount: number;
  payment: PaymentStatus;
  createdAt: string;
  items: { name: string; qty: number }[];
}

export interface Conversation {
  id: string;
  customer: string;
  phone: string;
  city: City;
  lastMessage: string;
  status: "AI handling" | "Awaiting reply" | "Human takeover" | "Resolved";
  mode: "AI" | "Human";
  assignedOrder: string | null;
  suggestedAction: string;
  updatedAt: string;
  unread: number;
}

export interface Ticket {
  id: string;
  subject: string;
  category: "Delay" | "Damage" | "Billing" | "Quality" | "Lost Item" | "General";
  priority: "Urgent" | "High" | "Medium" | "Low";
  source: Channel;
  status: "Open" | "In Progress" | "Waiting" | "Resolved";
  assignee: string;
  slaMinutesLeft: number;
  city: City;
  createdAt: string;
}

export interface Approval {
  id: string;
  type: "WhatsApp Reply" | "Refund" | "Discount" | "Marketing Post" | "SEO Change" | "Cancellation";
  summary: string;
  requestedBy: string;
  channel: string;
  createdAt: string;
  risk: "Low" | "Medium" | "High";
}

export interface SeoAgent {
  name: string;
  status: AgentStatus;
  lastRun: string;
  nextRun: string;
  outputs: number;
  openIssues: number;
  approvalRequired: boolean;
  category: "Technical" | "Content" | "Authority" | "Intelligence";
}

export interface SeoTask {
  id: string;
  task: string;
  agent: string;
  priority: "Urgent" | "High" | "Medium" | "Low";
  url: string;
  status: "Todo" | "In Progress" | "Needs Review" | "Done";
  suggestedAction: string;
  approvalRequired: boolean;
  // Geo context for global filtering: a market/city-specific page carries `city`;
  // site-wide tasks (sitewide linking, service/blog pages) are tagged global.
  city?: City;
  scope?: "global" | "geo";
}

export interface PlatformStat {
  platform: string;
  connected: boolean;
  followers: number;
  reach: number;
  engagement: number;
  clicks: number;
  leads: number;
  delta: number;
}

export interface MarketingApproval {
  id: string;
  platform: string;
  caption: string;
  assetType: "Image" | "Carousel" | "Reel" | "Video" | "Story";
  status: "Awaiting Approval" | "Scheduled" | "Changes Requested";
  createdBy: string;
  scheduledFor: string;
}

export interface CostLine {
  category: string;
  amount: number;
  pctOfCost: number;
  delta: number;
  note: string;
  tone: Tone;
}

export interface ReportCardData {
  name: string;
  audience: string;
  frequency: string;
  lastGenerated: string;
  status: "Ready" | "Generating" | "Scheduled";
  summary: string;
}

export interface TimeSeriesPoint {
  label: string;
  [key: string]: string | number;
}

export interface ActivityEvent {
  id: string;
  title: string;
  detail: string;
  time: string;
  tone: Tone;
  actor: "AI Agent" | "Ops Team" | "System" | "Customer";
}

export interface ConnectedApp {
  name: string;
  category: string;
  status: "Connected" | "Not connected" | "Coming soon" | "Needs approval";
}
