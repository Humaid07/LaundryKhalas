/**
 * Sales mock data for the new focused subsections (conversion funnel, channel
 * conversion, B2B accounts). Core sales arrays (salesKpis, salesByMarket,
 * revenueByService, topCustomers…) stay in mock-data.ts. Mock-only.
 */
import type { TimeSeriesPoint, Tone } from "./types";

export interface FunnelStage {
  stage: string;
  count: number;
  pctOfTop: number;
  tone: Tone;
}

export const conversionFunnel: FunnelStage[] = [
  { stage: "Leads", count: 4820, pctOfTop: 100, tone: "info" },
  { stage: "Inquiries", count: 2610, pctOfTop: 54, tone: "plum" },
  { stage: "Bookings", count: 1490, pctOfTop: 31, tone: "rose" },
  { stage: "Completed Orders", count: 1284, pctOfTop: 27, tone: "success" },
  { stage: "Lost / Cancelled", count: 206, pctOfTop: 4, tone: "danger" },
];

export const channelConversion: TimeSeriesPoint[] = [
  { label: "WhatsApp", value: 22.4 },
  { label: "Website", value: 15.1 },
  { label: "App", value: 18.6 },
  { label: "Manual", value: 27.0 },
  { label: "B2B", value: 31.2 },
];

export interface BusinessAccount {
  name: string;
  type: "Hotel" | "Corporate" | "Building" | "Facility";
  city: string;
  monthlyRevenue: number;
  orders: number;
  status: "Active" | "Onboarding" | "At Risk";
}

export const businessAccounts: BusinessAccount[] = [
  { name: "Grand Bay Hotel", type: "Hotel", city: "Doha", monthlyRevenue: 38600, orders: 92, status: "Active" },
  { name: "Noor Villas", type: "Building", city: "Dubai", monthlyRevenue: 21400, orders: 64, status: "Active" },
  { name: "Olaya Business Tower", type: "Corporate", city: "Riyadh", monthlyRevenue: 16800, orders: 48, status: "Active" },
  { name: "Marina Residences", type: "Building", city: "Dubai", monthlyRevenue: 12200, orders: 41, status: "At Risk" },
  { name: "Seef Boutique Hotel", type: "Hotel", city: "Manama", monthlyRevenue: 9400, orders: 28, status: "Onboarding" },
];

export const businessAccountStatusTone: Record<BusinessAccount["status"], Tone> = {
  Active: "success",
  Onboarding: "info",
  "At Risk": "warning",
};
