/**
 * LaundryKhalas mock data — deterministic, domain-specific, mock-only.
 * Nothing here is a real order, customer, price, or metric. It exists to
 * exercise the dashboard UI. No live data, no PII, no invented promises.
 */
import type {
  ActivityEvent,
  Approval,
  ConnectedApp,
  Conversation,
  CostLine,
  KpiStat,
  MarketingApproval,
  Order,
  PlatformStat,
  ReportCardData,
  SeoAgent,
  SeoTask,
  Ticket,
  TimeSeriesPoint,
} from "./types";

export const MARKETS = ["UAE", "Qatar", "Saudi Arabia", "Kuwait", "Bahrain", "Oman"] as const;
export const CITIES = [
  "Dubai",
  "Abu Dhabi",
  "Sharjah",
  "Doha",
  "Riyadh",
  "Kuwait City",
  "Manama",
  "Muscat",
] as const;
export const CHANNELS = ["WhatsApp", "Website", "App", "Walk-in", "B2B"] as const;
export const SERVICES = [
  "Wash & Fold",
  "Dry Cleaning",
  "Ironing / Pressing",
  "Blankets / Duvets",
  "Curtains / Upholstery",
  "Business Laundry",
] as const;
// Continental region model — the single global Region taxonomy shared by every
// section (ops markets roll up to GCC; partner leads span the other regions).
export const REGIONS = ["GCC", "MENA", "Asia", "Europe", "Americas"] as const;

const spark = (seed: number[]) => seed;

/* ---------------------------------- Overview --------------------------------- */

export const overviewKpis: KpiStat[] = [
  { label: "Total Orders", value: "3,482", raw: 3482, delta: 12.4, tone: "rose", spark: spark([28, 31, 30, 35, 33, 39, 42]), hint: "All channels, last 30 days" },
  { label: "WhatsApp Orders", value: "1,914", raw: 1914, delta: 18.9, tone: "success", spark: spark([12, 15, 14, 18, 19, 22, 24]) },
  { label: "Website Orders", value: "986", raw: 986, delta: 6.1, tone: "info", spark: spark([9, 10, 9, 11, 10, 12, 12]) },
  { label: "Pending Pickups", value: "74", raw: 74, delta: -8.2, tone: "warning", spark: spark([9, 8, 10, 7, 8, 6, 7]) },
  { label: "Orders In Cleaning", value: "218", raw: 218, delta: 4.5, tone: "info", spark: spark([18, 20, 19, 21, 22, 21, 22]) },
  { label: "Out for Delivery", value: "63", raw: 63, delta: 9.3, tone: "rose", spark: spark([5, 6, 5, 6, 7, 6, 7]) },
  { label: "Delivered Today", value: "241", raw: 241, delta: 15.0, tone: "success", spark: spark([16, 18, 20, 19, 22, 23, 24]) },
  { label: "Revenue (30d)", value: "AED 612K", raw: 612000, delta: 11.2, tone: "rose", spark: spark([48, 52, 50, 56, 58, 60, 62]) },
  { label: "Profit (30d)", value: "AED 173K", raw: 173000, delta: 8.7, tone: "success", spark: spark([14, 15, 14, 16, 16, 17, 17]) },
  { label: "Active Tickets", value: "38", raw: 38, delta: -5.0, tone: "warning", spark: spark([6, 5, 5, 4, 5, 4, 4]) },
  { label: "AI Conversations", value: "1,264", raw: 1264, delta: 22.8, tone: "plum", spark: spark([80, 92, 88, 104, 110, 118, 126]) },
  { label: "Campaigns Active", value: "9", raw: 9, delta: 2.0, tone: "info", spark: spark([6, 7, 7, 8, 8, 9, 9]) },
];

export const ordersOverTime: TimeSeriesPoint[] = [
  { label: "Jul 01", WhatsApp: 42, Website: 24, App: 12 },
  { label: "Jul 04", WhatsApp: 48, Website: 26, App: 14 },
  { label: "Jul 07", WhatsApp: 45, Website: 22, App: 13 },
  { label: "Jul 10", WhatsApp: 58, Website: 28, App: 16 },
  { label: "Jul 13", WhatsApp: 62, Website: 31, App: 18 },
  { label: "Jul 16", WhatsApp: 69, Website: 30, App: 21 },
  { label: "Jul 19", WhatsApp: 74, Website: 34, App: 22 },
];

export const revenueOverTime: TimeSeriesPoint[] = [
  { label: "Jul 01", Revenue: 18200, Profit: 5100 },
  { label: "Jul 04", Revenue: 20400, Profit: 5900 },
  { label: "Jul 07", Revenue: 19100, Profit: 5300 },
  { label: "Jul 10", Revenue: 23600, Profit: 6800 },
  { label: "Jul 13", Revenue: 25200, Profit: 7200 },
  { label: "Jul 16", Revenue: 27100, Profit: 7900 },
  { label: "Jul 19", Revenue: 29400, Profit: 8600 },
];

export const ordersByChannel: TimeSeriesPoint[] = [
  { label: "WhatsApp", value: 1914 },
  { label: "Website", value: 986 },
  { label: "App", value: 412 },
  { label: "Walk-in", value: 98 },
  { label: "B2B", value: 72 },
];

export const ordersByCity: TimeSeriesPoint[] = [
  { label: "Dubai", value: 1284 },
  { label: "Abu Dhabi", value: 642 },
  { label: "Doha", value: 498 },
  { label: "Riyadh", value: 421 },
  { label: "Sharjah", value: 288 },
  { label: "Kuwait City", value: 176 },
  { label: "Manama", value: 98 },
  { label: "Muscat", value: 75 },
];

export const serviceDemand: TimeSeriesPoint[] = [
  { label: "Wash & Fold", value: 1420 },
  { label: "Dry Cleaning", value: 864 },
  { label: "Ironing / Pressing", value: 512 },
  { label: "Blankets / Duvets", value: 318 },
  { label: "Curtains / Upholstery", value: 214 },
  { label: "Business Laundry", value: 154 },
];

export const ticketsByCategory: TimeSeriesPoint[] = [
  { label: "Delay", value: 14 },
  { label: "Quality", value: 9 },
  { label: "Billing", value: 6 },
  { label: "Damage", value: 5 },
  { label: "Lost Item", value: 3 },
  { label: "General", value: 1 },
];

export const automationRate: TimeSeriesPoint[] = [
  { label: "Jul 01", Automated: 62, Human: 38 },
  { label: "Jul 04", Automated: 65, Human: 35 },
  { label: "Jul 07", Automated: 67, Human: 33 },
  { label: "Jul 10", Automated: 70, Human: 30 },
  { label: "Jul 13", Automated: 72, Human: 28 },
  { label: "Jul 16", Automated: 74, Human: 26 },
  { label: "Jul 19", Automated: 76, Human: 24 },
];

/* ---------------------------------- Orders ----------------------------------- */

export const orders: Order[] = [
  { id: "LK-24817", customer: "Aisha Rahman", phone: "+971 50 220 4471", service: "Wash & Fold", channel: "WhatsApp", city: "Dubai", market: "UAE", status: "Out for Delivery", pickupSlot: "Today 14:00–16:00", driver: "Bilal K.", facility: "Marina Hub", amount: 86, payment: "Paid", createdAt: "2026-07-20T09:12:00Z", items: [{ name: "Shirts", qty: 6 }, { name: "Trousers", qty: 4 }] },
  { id: "LK-24816", customer: "Omar Haddad", phone: "+971 55 771 9930", service: "Dry Cleaning", channel: "Website", city: "Abu Dhabi", market: "UAE", status: "In Cleaning", pickupSlot: "Today 10:00–12:00", driver: "Yusuf A.", facility: "Khalidiya Plant", amount: 142, payment: "Paid", createdAt: "2026-07-20T08:40:00Z", items: [{ name: "Suits", qty: 2 }, { name: "Blazer", qty: 1 }] },
  { id: "LK-24815", customer: "Fatima Al-Suwaidi", phone: "+974 33 118 2245", service: "Blankets / Duvets", channel: "WhatsApp", city: "Doha", market: "Qatar", status: "Pickup Scheduled", pickupSlot: "Tomorrow 09:00–11:00", driver: null, facility: "West Bay Hub", amount: 120, payment: "Pending", createdAt: "2026-07-20T07:55:00Z", items: [{ name: "King Duvet", qty: 1 }, { name: "Blankets", qty: 2 }] },
  { id: "LK-24814", customer: "Noor Villas (B2B)", phone: "+971 4 559 8820", service: "Business Laundry", channel: "B2B", city: "Dubai", market: "UAE", status: "Driver Assigned", pickupSlot: "Today 16:00–18:00", driver: "Rashid M.", facility: "Al Quoz Plant", amount: 940, payment: "Pending", createdAt: "2026-07-20T07:20:00Z", items: [{ name: "Bed linen sets", qty: 40 }, { name: "Towels", qty: 60 }] },
  { id: "LK-24813", customer: "Layla Kareem", phone: "+966 55 402 1189", service: "Ironing / Pressing", channel: "App", city: "Riyadh", market: "Saudi Arabia", status: "Delivered", pickupSlot: "Yesterday 12:00–14:00", driver: "Salem H.", facility: "Olaya Hub", amount: 54, payment: "Paid", createdAt: "2026-07-19T11:05:00Z", items: [{ name: "Thobes", qty: 5 }] },
  { id: "LK-24812", customer: "Hassan Ali", phone: "+971 52 664 7712", service: "Curtains / Upholstery", channel: "Website", city: "Sharjah", market: "UAE", status: "Concern Raised", pickupSlot: "Yesterday 15:00–17:00", driver: "Bilal K.", facility: "Industrial Area Plant", amount: 320, payment: "Paid", createdAt: "2026-07-19T09:30:00Z", items: [{ name: "Curtain panels", qty: 8 }] },
  { id: "LK-24811", customer: "Mariam Zayed", phone: "+973 33 909 1120", service: "Wash & Fold", channel: "WhatsApp", city: "Manama", market: "Bahrain", status: "Ready for Delivery", pickupSlot: "Today 11:00–13:00", driver: "Ahmed R.", facility: "Seef Hub", amount: 72, payment: "Paid", createdAt: "2026-07-20T06:10:00Z", items: [{ name: "Mixed load", qty: 1 }] },
  { id: "LK-24810", customer: "Khalid Nasser", phone: "+965 99 220 8841", service: "Dry Cleaning", channel: "App", city: "Kuwait City", market: "Kuwait", status: "New", pickupSlot: "Tomorrow 13:00–15:00", driver: null, facility: "Salmiya Hub", amount: 96, payment: "Pending", createdAt: "2026-07-20T09:45:00Z", items: [{ name: "Dresses", qty: 3 }] },
  { id: "LK-24809", customer: "Sara Juma", phone: "+968 92 551 3307", service: "Wash & Fold", channel: "WhatsApp", city: "Muscat", market: "Oman", status: "Picked Up", pickupSlot: "Today 08:00–10:00", driver: "Tariq S.", facility: "Qurum Hub", amount: 64, payment: "Paid", createdAt: "2026-07-20T05:30:00Z", items: [{ name: "Shirts", qty: 8 }] },
  { id: "LK-24808", customer: "Grand Bay Hotel (B2B)", phone: "+974 4 118 7654", service: "Business Laundry", channel: "B2B", city: "Doha", market: "Qatar", status: "In Cleaning", pickupSlot: "Today 07:00–09:00", driver: "Yusuf A.", facility: "Industrial City Plant", amount: 1680, payment: "Pending", createdAt: "2026-07-20T04:50:00Z", items: [{ name: "Table linen", qty: 120 }, { name: "Napkins", qty: 240 }] },
  { id: "LK-24807", customer: "Reem Fahad", phone: "+966 56 771 2093", service: "Blankets / Duvets", channel: "Website", city: "Riyadh", market: "Saudi Arabia", status: "Cancelled", pickupSlot: "Yesterday 10:00–12:00", driver: null, facility: "Olaya Hub", amount: 0, payment: "Refunded", createdAt: "2026-07-19T08:15:00Z", items: [{ name: "Comforter", qty: 1 }] },
  { id: "LK-24806", customer: "Yousef Baladi", phone: "+971 50 883 4410", service: "Ironing / Pressing", channel: "WhatsApp", city: "Dubai", market: "UAE", status: "Delivered", pickupSlot: "Yesterday 09:00–11:00", driver: "Rashid M.", facility: "Marina Hub", amount: 48, payment: "Paid", createdAt: "2026-07-19T06:40:00Z", items: [{ name: "Shirts", qty: 10 }] },
];

/* ------------------------------- Conversations ------------------------------- */

export const conversations: Conversation[] = [
  { id: "c-9001", customer: "Aisha Rahman", phone: "+971 50 220 4471", city: "Dubai", lastMessage: "Perfect, thank you! What time will the driver arrive?", status: "AI handling", mode: "AI", assignedOrder: "LK-24817", suggestedAction: "Share delivery window", updatedAt: "2026-07-20T09:40:00Z", unread: 0 },
  { id: "c-9002", customer: "Hassan Ali", phone: "+971 52 664 7712", city: "Sharjah", lastMessage: "One of the curtains came back with a mark on it.", status: "Human takeover", mode: "Human", assignedOrder: "LK-24812", suggestedAction: "Escalate to quality team", updatedAt: "2026-07-20T09:22:00Z", unread: 2 },
  { id: "c-9003", customer: "Khalid Nasser", phone: "+965 99 220 8841", city: "Kuwait City", lastMessage: "Can I get a pickup tomorrow afternoon?", status: "Awaiting reply", mode: "AI", assignedOrder: "LK-24810", suggestedAction: "Confirm 13:00–15:00 slot", updatedAt: "2026-07-20T09:05:00Z", unread: 1 },
  { id: "c-9004", customer: "Mariam Zayed", phone: "+973 33 909 1120", city: "Manama", lastMessage: "Great, order received. See you soon!", status: "Resolved", mode: "AI", assignedOrder: "LK-24811", suggestedAction: "No action needed", updatedAt: "2026-07-20T08:12:00Z", unread: 0 },
  { id: "c-9005", customer: "Sara Juma", phone: "+968 92 551 3307", city: "Muscat", lastMessage: "Do you clean traditional dishdasha?", status: "AI handling", mode: "AI", assignedOrder: null, suggestedAction: "Offer Dry Cleaning service", updatedAt: "2026-07-20T07:58:00Z", unread: 0 },
  { id: "c-9006", customer: "Omar Haddad", phone: "+971 55 771 9930", city: "Abu Dhabi", lastMessage: "Is my order ready yet?", status: "Awaiting reply", mode: "AI", assignedOrder: "LK-24816", suggestedAction: "Share status: In Cleaning", updatedAt: "2026-07-20T07:30:00Z", unread: 1 },
];

/* ---------------------------------- Tickets ---------------------------------- */

export const tickets: Ticket[] = [
  { id: "T-4412", subject: "Curtain returned with a mark", category: "Damage", priority: "High", source: "WhatsApp", status: "In Progress", assignee: "Quality — Huda", slaMinutesLeft: 84, city: "Sharjah", createdAt: "2026-07-20T09:20:00Z" },
  { id: "T-4411", subject: "Delivery running late", category: "Delay", priority: "Medium", source: "App", status: "Open", assignee: "Ops — Faris", slaMinutesLeft: 32, city: "Dubai", createdAt: "2026-07-20T08:55:00Z" },
  { id: "T-4410", subject: "Charged twice for one order", category: "Billing", priority: "Urgent", source: "Website", status: "Open", assignee: "Finance — Dana", slaMinutesLeft: 12, city: "Riyadh", createdAt: "2026-07-20T08:40:00Z" },
  { id: "T-4409", subject: "Missing one shirt from order", category: "Lost Item", priority: "High", source: "WhatsApp", status: "Waiting", assignee: "Ops — Faris", slaMinutesLeft: 140, city: "Doha", createdAt: "2026-07-20T07:15:00Z" },
  { id: "T-4408", subject: "Stain not fully removed", category: "Quality", priority: "Medium", source: "WhatsApp", status: "In Progress", assignee: "Quality — Huda", slaMinutesLeft: 210, city: "Abu Dhabi", createdAt: "2026-07-20T06:30:00Z" },
  { id: "T-4407", subject: "Requesting pickup reschedule", category: "General", priority: "Low", source: "B2B", status: "Resolved", assignee: "Ops — Layan", slaMinutesLeft: 0, city: "Kuwait City", createdAt: "2026-07-19T15:10:00Z" },
];

/* --------------------------------- Approvals --------------------------------- */

export const approvals: Approval[] = [
  { id: "a-501", type: "WhatsApp Reply", summary: "Reply to Omar with 'In Cleaning' status + ready-by estimate", requestedBy: "WhatsApp Agent", channel: "WhatsApp · Abu Dhabi", createdAt: "2026-07-20T09:38:00Z", risk: "Low" },
  { id: "a-502", type: "Refund", summary: "AED 320 refund for marked curtain (order LK-24812)", requestedBy: "Ops — Faris", channel: "Ticket T-4412", createdAt: "2026-07-20T09:25:00Z", risk: "High" },
  { id: "a-503", type: "Marketing Post", summary: "Instagram reel — 'Eid fresh linen' campaign", requestedBy: "Marketing Agent", channel: "Instagram · UAE", createdAt: "2026-07-20T08:50:00Z", risk: "Medium" },
  { id: "a-504", type: "SEO Change", summary: "Publish hyperlocal page: 'Dry cleaning in Al Nahda, Sharjah'", requestedBy: "Hyperlocal Area Page Agent", channel: "SEO", createdAt: "2026-07-20T08:15:00Z", risk: "Medium" },
  { id: "a-505", type: "Discount", summary: "15% first-order discount for B2B lead 'Grand Bay Hotel'", requestedBy: "Sales — Nada", channel: "B2B · Doha", createdAt: "2026-07-20T07:40:00Z", risk: "Medium" },
];

/* ------------------------------- Activity feed ------------------------------- */

export const activityFeed: ActivityEvent[] = [
  { id: "e1", title: "New order created", detail: "LK-24817 · Wash & Fold · Dubai Marina", time: "2026-07-20T09:40:00Z", tone: "rose", actor: "AI Agent" },
  { id: "e2", title: "Reply drafted, awaiting approval", detail: "Conversation with Omar Haddad", time: "2026-07-20T09:38:00Z", tone: "warning", actor: "AI Agent" },
  { id: "e3", title: "Human takeover started", detail: "Hassan Ali · curtain quality concern", time: "2026-07-20T09:22:00Z", tone: "info", actor: "Ops Team" },
  { id: "e4", title: "Facility assigned", detail: "LK-24814 → Al Quoz Plant", time: "2026-07-20T07:25:00Z", tone: "neutral", actor: "System" },
  { id: "e5", title: "SEO agent flagged ranking drop", detail: "'laundry service dubai marina' −4 positions", time: "2026-07-20T06:50:00Z", tone: "danger", actor: "AI Agent" },
  { id: "e6", title: "Delivery completed", detail: "LK-24806 · Ironing · Dubai", time: "2026-07-19T10:20:00Z", tone: "success", actor: "System" },
];

/* ----------------------------------- Sales ----------------------------------- */

export const salesKpis: KpiStat[] = [
  { label: "Total Sales", value: "AED 612K", delta: 11.2, tone: "rose", spark: spark([48, 52, 50, 56, 58, 60, 62]) },
  { label: "Sales Growth", value: "+11.2%", delta: 3.1, tone: "success", spark: spark([6, 7, 8, 8, 9, 10, 11]) },
  { label: "New Customers", value: "842", delta: 14.8, tone: "info", spark: spark([90, 96, 102, 110, 118, 126, 134]) },
  { label: "Returning Customers", value: "2,106", delta: 9.4, tone: "plum", spark: spark([280, 292, 300, 312, 320, 331, 340]) },
  { label: "Avg Order Value", value: "AED 176", delta: 2.7, tone: "rose", spark: spark([168, 170, 169, 172, 174, 175, 176]) },
  { label: "Conversion Rate", value: "6.8%", delta: 0.6, tone: "success", spark: spark([6.1, 6.2, 6.3, 6.4, 6.5, 6.7, 6.8]) },
  { label: "Top City", value: "Dubai", tone: "rose", hint: "1,284 orders · 37% of volume" },
  { label: "Top Service", value: "Wash & Fold", tone: "info", hint: "1,420 orders · 41% of volume" },
  { label: "B2B Revenue", value: "AED 184K", delta: 21.5, tone: "plum", spark: spark([120, 130, 140, 152, 164, 176, 184]) },
  { label: "B2C Revenue", value: "AED 428K", delta: 7.8, tone: "success", spark: spark([360, 372, 380, 396, 408, 420, 428]) },
];

// LaundryKhalas currently operates only in GCC markets, so the region breakdown
// is a single GCC bar under the continental region model. Selecting a non-GCC
// global Region correctly yields an empty state here.
export const salesByRegion: TimeSeriesPoint[] = [
  { label: "GCC", value: 612000 },
];

export const salesByMarket: TimeSeriesPoint[] = [
  { label: "UAE", value: 318000 },
  { label: "Qatar", value: 112000 },
  { label: "Saudi Arabia", value: 96000 },
  { label: "Kuwait", value: 44000 },
  { label: "Bahrain", value: 24000 },
  { label: "Oman", value: 18000 },
];

export const salesByChannel: TimeSeriesPoint[] = [
  { label: "WhatsApp", value: 286000 },
  { label: "Website", value: 172000 },
  { label: "App", value: 88000 },
  { label: "B2B", value: 52000 },
  { label: "Walk-in", value: 14000 },
];

export const revenueByService: TimeSeriesPoint[] = [
  { label: "Wash & Fold", value: 214000 },
  { label: "Dry Cleaning", value: 158000 },
  { label: "Business Laundry", value: 96000 },
  { label: "Blankets / Duvets", value: 62000 },
  { label: "Ironing / Pressing", value: 48000 },
  { label: "Curtains / Upholstery", value: 34000 },
];

export const acquisitionTrend: TimeSeriesPoint[] = [
  { label: "Feb", New: 520, Returning: 1480 },
  { label: "Mar", New: 610, Returning: 1620 },
  { label: "Apr", New: 680, Returning: 1740 },
  { label: "May", New: 720, Returning: 1880 },
  { label: "Jun", New: 790, Returning: 1990 },
  { label: "Jul", New: 842, Returning: 2106 },
];

export const b2bVsB2c: TimeSeriesPoint[] = [
  { label: "B2C", value: 428000 },
  { label: "B2B", value: 184000 },
];

export const topCities: { city: string; orders: number; revenue: number; growth: number }[] = [
  { city: "Dubai", orders: 1284, revenue: 232000, growth: 12.8 },
  { city: "Abu Dhabi", orders: 642, revenue: 118000, growth: 9.1 },
  { city: "Doha", orders: 498, revenue: 94000, growth: 15.4 },
  { city: "Riyadh", orders: 421, revenue: 76000, growth: 18.2 },
  { city: "Sharjah", orders: 288, revenue: 42000, growth: 6.6 },
];

export const topServices: { service: string; orders: number; revenue: number; share: number }[] = [
  { service: "Wash & Fold", orders: 1420, revenue: 214000, share: 41 },
  { service: "Dry Cleaning", orders: 864, revenue: 158000, share: 25 },
  { service: "Ironing / Pressing", orders: 512, revenue: 48000, share: 15 },
  { service: "Blankets / Duvets", orders: 318, revenue: 62000, share: 9 },
  { service: "Business Laundry", orders: 154, revenue: 96000, share: 6 },
];

export const topCustomers: { name: string; type: "B2B" | "B2C"; orders: number; revenue: number }[] = [
  { name: "Grand Bay Hotel", type: "B2B", orders: 62, revenue: 74000 },
  { name: "Noor Villas", type: "B2B", orders: 48, revenue: 52000 },
  { name: "Aisha Rahman", type: "B2C", orders: 22, revenue: 3200 },
  { name: "Marina Residences", type: "B2B", orders: 31, revenue: 28000 },
  { name: "Omar Haddad", type: "B2C", orders: 18, revenue: 2600 },
];

/* --------------------------------- SEO Agents -------------------------------- */

export const seoAgents: SeoAgent[] = [
  { name: "Crawl-State / Site Inventory", status: "Active", lastRun: "2026-07-20T06:00:00Z", nextRun: "2026-07-21T06:00:00Z", outputs: 1284, openIssues: 0, approvalRequired: false, category: "Technical" },
  { name: "GSC Performance Monitor", status: "Active", lastRun: "2026-07-20T05:30:00Z", nextRun: "2026-07-20T17:30:00Z", outputs: 96, openIssues: 2, approvalRequired: false, category: "Intelligence" },
  { name: "Indexing Agent", status: "Needs Review", lastRun: "2026-07-20T04:00:00Z", nextRun: "2026-07-21T04:00:00Z", outputs: 34, openIssues: 5, approvalRequired: true, category: "Technical" },
  { name: "Content Research Agent", status: "Scheduled", lastRun: "2026-07-19T22:00:00Z", nextRun: "2026-07-20T22:00:00Z", outputs: 18, openIssues: 0, approvalRequired: false, category: "Content" },
  { name: "Blog Content Agent", status: "Awaiting Approval", lastRun: "2026-07-20T03:00:00Z", nextRun: "2026-07-21T03:00:00Z", outputs: 6, openIssues: 0, approvalRequired: true, category: "Content" },
  { name: "Hyperlocal Area Page Agent", status: "Awaiting Approval", lastRun: "2026-07-20T02:30:00Z", nextRun: "2026-07-21T02:30:00Z", outputs: 12, openIssues: 0, approvalRequired: true, category: "Content" },
  { name: "Money Page Optimizer", status: "Active", lastRun: "2026-07-20T01:00:00Z", nextRun: "2026-07-21T01:00:00Z", outputs: 22, openIssues: 1, approvalRequired: false, category: "Content" },
  { name: "Internal Linking Agent", status: "Active", lastRun: "2026-07-20T00:30:00Z", nextRun: "2026-07-21T00:30:00Z", outputs: 148, openIssues: 0, approvalRequired: false, category: "Technical" },
  { name: "Duplicate / Cannibalization / Decay", status: "Needs Review", lastRun: "2026-07-19T23:00:00Z", nextRun: "2026-07-20T23:00:00Z", outputs: 9, openIssues: 3, approvalRequired: true, category: "Technical" },
  { name: "Topical Authority Agent", status: "Scheduled", lastRun: "2026-07-19T20:00:00Z", nextRun: "2026-07-20T20:00:00Z", outputs: 14, openIssues: 0, approvalRequired: false, category: "Authority" },
  { name: "Keyword Mapping Agent", status: "Active", lastRun: "2026-07-19T19:00:00Z", nextRun: "2026-07-20T19:00:00Z", outputs: 342, openIssues: 0, approvalRequired: false, category: "Authority" },
  { name: "AI Search Visibility Agent", status: "Active", lastRun: "2026-07-20T05:00:00Z", nextRun: "2026-07-20T17:00:00Z", outputs: 28, openIssues: 1, approvalRequired: false, category: "Intelligence" },
  { name: "Competitor Monitor", status: "Active", lastRun: "2026-07-20T06:15:00Z", nextRun: "2026-07-20T18:15:00Z", outputs: 41, openIssues: 2, approvalRequired: false, category: "Intelligence" },
  { name: "News & Brand Mention Monitor", status: "Paused", lastRun: "2026-07-18T12:00:00Z", nextRun: "—", outputs: 0, openIssues: 0, approvalRequired: false, category: "Intelligence" },
];

export const seoKpis: KpiStat[] = [
  { label: "Clicks (28d)", value: "48.2K", delta: 9.6, tone: "rose", spark: spark([6.1, 6.4, 6.6, 6.8, 7.0, 7.2, 7.4]) },
  { label: "Impressions", value: "1.94M", delta: 12.1, tone: "info", spark: spark([240, 252, 260, 272, 281, 290, 302]) },
  { label: "Avg Position", value: "8.4", delta: -0.7, tone: "success", spark: spark([9.8, 9.5, 9.2, 9.0, 8.8, 8.6, 8.4]) },
  { label: "CTR", value: "2.48%", delta: 0.3, tone: "rose", spark: spark([2.2, 2.3, 2.3, 2.4, 2.4, 2.45, 2.48]) },
  { label: "Indexed URLs", value: "1,208", delta: 1.4, tone: "info", spark: spark([1180, 1188, 1192, 1196, 1200, 1204, 1208]) },
  { label: "Pages w/ Issues", value: "34", delta: -12.0, tone: "warning", spark: spark([46, 44, 42, 40, 38, 36, 34]) },
  { label: "Ranking Drops", value: "7", delta: 2.0, tone: "danger", spark: spark([3, 4, 5, 4, 6, 6, 7]) },
  { label: "Content Opportunities", value: "23", delta: 4.0, tone: "plum", spark: spark([14, 16, 17, 19, 20, 22, 23]) },
  { label: "Competitor Changes", value: "11", delta: 3.0, tone: "warning", spark: spark([6, 7, 8, 8, 9, 10, 11]) },
  { label: "Backlink Opportunities", value: "19", delta: 5.0, tone: "success", spark: spark([10, 12, 13, 15, 16, 18, 19]) },
];

export const gscPerformance: TimeSeriesPoint[] = [
  { label: "Wk 1", Clicks: 6100, Impressions: 240000 },
  { label: "Wk 2", Clicks: 6600, Impressions: 260000 },
  { label: "Wk 3", Clicks: 7000, Impressions: 281000 },
  { label: "Wk 4", Clicks: 7400, Impressions: 302000 },
];

export const indexedVsNon: TimeSeriesPoint[] = [
  { label: "Indexed", value: 1208 },
  { label: "Discovered — not indexed", value: 46 },
  { label: "Crawled — not indexed", value: 30 },
];

export const contentPipeline: TimeSeriesPoint[] = [
  { label: "Researching", value: 18 },
  { label: "Drafting", value: 12 },
  { label: "In Review", value: 6 },
  { label: "Approved", value: 9 },
  { label: "Published", value: 41 },
];

export const seoTasks: SeoTask[] = [
  { id: "s-01", task: "Fix indexing on 5 hyperlocal pages", agent: "Indexing Agent", priority: "Urgent", url: "/dubai/marina/dry-cleaning", status: "Needs Review", suggestedAction: "Submit for re-indexing", approvalRequired: true, city: "Dubai" },
  { id: "s-02", task: "Publish 'Dry cleaning in Al Nahda' page", agent: "Hyperlocal Area Page Agent", priority: "High", url: "/sharjah/al-nahda/dry-cleaning", status: "Needs Review", suggestedAction: "Approve & publish", approvalRequired: true, city: "Sharjah" },
  { id: "s-03", task: "Resolve keyword cannibalization", agent: "Duplicate / Decay", priority: "High", url: "/services/wash-and-fold", status: "In Progress", suggestedAction: "Consolidate 2 URLs, add canonical", approvalRequired: true, scope: "global" },
  { id: "s-04", task: "Refresh decaying blog post", agent: "Money Page Optimizer", priority: "Medium", url: "/blog/laundry-tips-summer", status: "Todo", suggestedAction: "Update stats + internal links", approvalRequired: false, scope: "global" },
  { id: "s-05", task: "Add 12 internal links to money pages", agent: "Internal Linking Agent", priority: "Medium", url: "sitewide", status: "In Progress", suggestedAction: "Auto-insert contextual links", approvalRequired: false, scope: "global" },
  { id: "s-06", task: "Draft comparison article vs competitor", agent: "Blog Content Agent", priority: "Low", url: "/blog/best-laundry-dubai", status: "Needs Review", suggestedAction: "Approve outline", approvalRequired: true, city: "Dubai" },
];

export const seoBrief = {
  date: "2026-07-20",
  headline: "3 approvals waiting, 1 ranking drop worth attention",
  items: [
    { tone: "danger" as const, title: "Ranking drop", text: "'laundry service dubai marina' fell 4 positions (5 → 9) after a competitor refreshed their page." },
    { tone: "warning" as const, title: "Indexing", text: "5 hyperlocal pages are 'Discovered — not indexed'. Re-submission is queued and needs approval." },
    { tone: "rose" as const, title: "Opportunity", text: "23 content opportunities identified; the Al Nahda dry-cleaning page is ready to publish." },
    { tone: "success" as const, title: "Progress", text: "Pages with issues down 12% this week; CTR up to 2.48%." },
  ],
};

/* --------------------------------- Marketing --------------------------------- */

export const platformStats: PlatformStat[] = [
  { platform: "Instagram", connected: true, followers: 42800, reach: 318000, engagement: 4.8, clicks: 6200, leads: 184, delta: 8.4 },
  { platform: "Facebook", connected: true, followers: 28400, reach: 196000, engagement: 2.9, clicks: 3800, leads: 96, delta: 3.1 },
  { platform: "TikTok", connected: true, followers: 61200, reach: 512000, engagement: 6.7, clicks: 8400, leads: 142, delta: 22.6 },
  { platform: "LinkedIn", connected: true, followers: 8900, reach: 44000, engagement: 3.4, clicks: 1200, leads: 58, delta: 5.2 },
  { platform: "YouTube", connected: false, followers: 0, reach: 0, engagement: 0, clicks: 0, leads: 0, delta: 0 },
  { platform: "Google Business", connected: true, followers: 0, reach: 88000, engagement: 5.1, clicks: 4200, leads: 210, delta: 11.8 },
  { platform: "Email / Apollo", connected: false, followers: 0, reach: 0, engagement: 0, clicks: 0, leads: 0, delta: 0 },
  { platform: "WhatsApp Campaigns", connected: true, followers: 0, reach: 62000, engagement: 9.2, clicks: 5400, leads: 320, delta: 14.5 },
];

export const marketingKpis: KpiStat[] = [
  { label: "Total Reach", value: "1.22M", delta: 12.4, tone: "rose", spark: spark([0.9, 0.98, 1.02, 1.08, 1.14, 1.19, 1.22]) },
  { label: "Engagement Rate", value: "5.1%", delta: 0.7, tone: "success", spark: spark([4.2, 4.4, 4.6, 4.7, 4.9, 5.0, 5.1]) },
  { label: "Leads (30d)", value: "1,010", delta: 16.2, tone: "plum", spark: spark([720, 760, 810, 860, 910, 960, 1010]) },
  { label: "Campaigns Active", value: "9", delta: 2.0, tone: "info", spark: spark([6, 7, 7, 8, 8, 9, 9]) },
];

export const engagementTrend: TimeSeriesPoint[] = [
  { label: "Wk 1", Instagram: 4.2, TikTok: 5.9, Facebook: 2.6 },
  { label: "Wk 2", Instagram: 4.4, TikTok: 6.2, Facebook: 2.7 },
  { label: "Wk 3", Instagram: 4.6, TikTok: 6.5, Facebook: 2.8 },
  { label: "Wk 4", Instagram: 4.8, TikTok: 6.7, Facebook: 2.9 },
];

export const contentCalendar: { day: string; posts: { platform: string; title: string; time: string; status: string }[] }[] = [
  { day: "Mon", posts: [{ platform: "Instagram", title: "Fresh linen reel", time: "10:00", status: "Scheduled" }] },
  { day: "Tue", posts: [{ platform: "TikTok", title: "Behind the scenes: plant tour", time: "18:00", status: "Awaiting Approval" }] },
  { day: "Wed", posts: [] },
  { day: "Thu", posts: [{ platform: "Facebook", title: "Eid offer carousel", time: "12:00", status: "Scheduled" }, { platform: "LinkedIn", title: "B2B case study", time: "09:00", status: "Draft" }] },
  { day: "Fri", posts: [{ platform: "Instagram", title: "Weekend pickup reminder", time: "17:00", status: "Scheduled" }] },
  { day: "Sat", posts: [] },
  { day: "Sun", posts: [{ platform: "WhatsApp", title: "Loyalty broadcast", time: "11:00", status: "Awaiting Approval" }] },
];

export const marketingApprovals: MarketingApproval[] = [
  { id: "m-01", platform: "Instagram", caption: "Eid-ready wardrobe starts here ✨ Book a pickup on WhatsApp.", assetType: "Reel", status: "Awaiting Approval", createdBy: "Social Posting Agent", scheduledFor: "2026-07-22T10:00:00Z" },
  { id: "m-02", platform: "TikTok", caption: "A day inside our Al Quoz cleaning plant 🧺", assetType: "Video", status: "Awaiting Approval", createdBy: "Video / Reel Scripts Agent", scheduledFor: "2026-07-21T18:00:00Z" },
  { id: "m-03", platform: "Facebook", caption: "Eid offer: 20% off blankets & duvets this week only.", assetType: "Carousel", status: "Changes Requested", createdBy: "Social Posting Agent", scheduledFor: "2026-07-24T12:00:00Z" },
  { id: "m-04", platform: "WhatsApp", caption: "Loyalty reward: your next Wash & Fold is on us 💛", assetType: "Image", status: "Awaiting Approval", createdBy: "Campaign Agent", scheduledFor: "2026-07-27T11:00:00Z" },
];

export const marketingAgents: { name: string; status: string; note: string; approvalGate: boolean }[] = [
  { name: "Backlink Prospecting", status: "Active", note: "19 prospects found this week", approvalGate: false },
  { name: "Outreach Drafting", status: "Awaiting Approval", note: "8 emails drafted, none sent", approvalGate: true },
  { name: "PR Drafting", status: "Scheduled", note: "Next run tonight", approvalGate: true },
  { name: "Citation / NAP Monitoring", status: "Active", note: "All 24 listings consistent", approvalGate: false },
  { name: "Social Posting", status: "Awaiting Approval", note: "4 posts pending approval", approvalGate: true },
  { name: "Video / Reel Scripts", status: "Active", note: "6 scripts generated", approvalGate: true },
  { name: "Community Engagement", status: "Paused", note: "Paused pending policy review", approvalGate: true },
  { name: "UTM / Campaign Links", status: "Active", note: "14 links tracked", approvalGate: false },
  { name: "Influencer / UGC Outreach", status: "Scheduled", note: "3 creators shortlisted", approvalGate: true },
];

export const campaignLinks: { name: string; source: string; clicks: number; leads: number; utm: string }[] = [
  { name: "Eid Linen 2026", source: "Instagram", clicks: 2140, leads: 86, utm: "?utm_source=ig&utm_campaign=eid_linen" },
  { name: "B2B Hotels", source: "LinkedIn", clicks: 640, leads: 42, utm: "?utm_source=li&utm_campaign=b2b_hotels" },
  { name: "Weekend Pickup", source: "WhatsApp", clicks: 3200, leads: 210, utm: "?utm_source=wa&utm_campaign=weekend" },
];

/* ---------------------------------- Finance ---------------------------------- */

export const financeKpis: KpiStat[] = [
  { label: "Overall Revenue", value: "AED 612K", delta: 11.2, tone: "rose", spark: spark([48, 52, 50, 56, 58, 60, 62]) },
  { label: "Overall Cost", value: "AED 439K", delta: 6.8, tone: "warning", spark: spark([38, 40, 39, 41, 42, 43, 44]) },
  { label: "Overall Profit", value: "AED 173K", delta: 8.7, tone: "success", spark: spark([14, 15, 14, 16, 16, 17, 17]) },
  { label: "Gross Margin", value: "42.1%", delta: 1.2, tone: "rose", spark: spark([40, 40.5, 41, 41.2, 41.6, 42, 42.1]) },
  { label: "Net Margin", value: "28.3%", delta: 0.9, tone: "success", spark: spark([26, 26.5, 27, 27.4, 27.8, 28.1, 28.3]) },
  { label: "Avg Order Value", value: "AED 176", delta: 2.7, tone: "info", spark: spark([168, 170, 169, 172, 174, 175, 176]) },
  { label: "Cost per Order", value: "AED 126", delta: -1.9, tone: "success", spark: spark([132, 131, 130, 129, 128, 127, 126]) },
  { label: "Damage Cost", value: "AED 8.4K", delta: 14.0, tone: "danger", spark: spark([5.4, 6.0, 6.4, 6.9, 7.4, 8.0, 8.4]) },
  { label: "Tech Cost", value: "AED 21K", delta: 4.0, tone: "info", spark: spark([18, 18.5, 19, 19.5, 20, 20.5, 21]) },
  { label: "Marketing Cost", value: "AED 54K", delta: 9.0, tone: "warning", spark: spark([44, 46, 48, 49, 51, 53, 54]) },
  { label: "AI / LLM Cost", value: "AED 3.2K", delta: 26.0, tone: "plum", spark: spark([1.8, 2.1, 2.3, 2.6, 2.8, 3.0, 3.2]) },
  { label: "Facility Cost", value: "AED 162K", delta: 5.0, tone: "info", spark: spark([148, 151, 153, 156, 158, 160, 162]) },
];

export const revenueVsCost: TimeSeriesPoint[] = [
  { label: "Feb", Revenue: 442000, Cost: 332000 },
  { label: "Mar", Revenue: 478000, Cost: 350000 },
  { label: "Apr", Revenue: 512000, Cost: 372000 },
  { label: "May", Revenue: 548000, Cost: 398000 },
  { label: "Jun", Revenue: 580000, Cost: 418000 },
  { label: "Jul", Revenue: 612000, Cost: 439000 },
];

export const profitTrend: TimeSeriesPoint[] = [
  { label: "Feb", Profit: 110000 },
  { label: "Mar", Profit: 128000 },
  { label: "Apr", Profit: 140000 },
  { label: "May", Profit: 150000 },
  { label: "Jun", Profit: 162000 },
  { label: "Jul", Profit: 173000 },
];

export const costBreakdown: CostLine[] = [
  { category: "Facility & Cleaning", amount: 162000, pctOfCost: 36.9, delta: 5.0, note: "Plant labor, utilities, consumables", tone: "info" },
  { category: "Driver & Logistics", amount: 118000, pctOfCost: 26.9, delta: 4.2, note: "Pickup & delivery fleet", tone: "rose" },
  { category: "Marketing", amount: 54000, pctOfCost: 12.3, delta: 9.0, note: "Paid social, campaigns, creative", tone: "warning" },
  { category: "Staff & Ops", amount: 48000, pctOfCost: 10.9, delta: 3.0, note: "Support, ops team, QA", tone: "plum" },
  { category: "Tech & Infra", amount: 21000, pctOfCost: 4.8, delta: 4.0, note: "Hosting, tools, integrations", tone: "info" },
  { category: "Damage & Claims", amount: 8400, pctOfCost: 1.9, delta: 14.0, note: "Reprocessing & compensation", tone: "danger" },
  { category: "Payment Fees", amount: 24400, pctOfCost: 5.6, delta: 2.0, note: "Gateway & processing", tone: "neutral" },
  { category: "AI / LLM", amount: 3200, pctOfCost: 0.7, delta: 26.0, note: "Agent inference (estimate)", tone: "plum" },
];

export const revenueByMarketFin: TimeSeriesPoint[] = salesByMarket;

export const profitByCity: TimeSeriesPoint[] = [
  { label: "Dubai", value: 68000 },
  { label: "Abu Dhabi", value: 34000 },
  { label: "Doha", value: 28000 },
  { label: "Riyadh", value: 21000 },
  { label: "Sharjah", value: 12000 },
  { label: "Kuwait City", value: 6000 },
];

/* ---------------------------------- Reports ---------------------------------- */

export const reportCards: ReportCardData[] = [
  { name: "Daily SEO Brief", audience: "Growth team", frequency: "Daily · 07:00", lastGenerated: "2026-07-20T07:00:00Z", status: "Ready", summary: "Ranking drop on a Dubai Marina money page, 3 approvals waiting, CTR trending up." },
  { name: "Weekly Marketing Report", audience: "Marketing lead", frequency: "Weekly · Mon", lastGenerated: "2026-07-15T08:00:00Z", status: "Ready", summary: "TikTok engagement +22.6%, 1,010 leads this month, 4 posts pending approval." },
  { name: "Monthly Executive Report", audience: "Founders", frequency: "Monthly", lastGenerated: "2026-07-01T09:00:00Z", status: "Scheduled", summary: "Revenue AED 612K (+11.2%), net margin 28.3%, B2B revenue +21.5%." },
  { name: "Operations Report", audience: "Ops team", frequency: "Daily · 20:00", lastGenerated: "2026-07-19T20:00:00Z", status: "Ready", summary: "76% automation rate, 38 active tickets, 241 deliveries today." },
  { name: "Finance Report", audience: "Finance", frequency: "Weekly · Fri", lastGenerated: "2026-07-18T18:00:00Z", status: "Ready", summary: "Cost per order down to AED 126, damage cost up 14% — worth review." },
  { name: "WhatsApp Agent Report", audience: "Ops + Product", frequency: "Weekly", lastGenerated: "2026-07-19T09:00:00Z", status: "Generating", summary: "1,264 AI conversations, 76% handled without human takeover." },
  { name: "Sales Report", audience: "Sales lead", frequency: "Weekly · Sun", lastGenerated: "2026-07-14T08:00:00Z", status: "Ready", summary: "842 new customers, AOV AED 176, Dubai remains top city." },
  { name: "Partner Acquisition Report", audience: "Partnerships", frequency: "Weekly · Wed", lastGenerated: "2026-07-19T09:00:00Z", status: "Ready", summary: "184 partner leads, 12 onboarded, 6 in compliance review; GCC coverage strongest." },
  { name: "Finance & Compliance Report", audience: "Finance + Founders", frequency: "Weekly · Fri", lastGenerated: "2026-07-18T18:00:00Z", status: "Ready", summary: "Revenue AED 612K, 82% partner compliance pass rate, 7 audit flags, 4 documents expiring soon." },
  { name: "Dev & Automation Report", audience: "Platform + Ops", frequency: "Daily · 21:00", lastGenerated: "2026-07-20T09:00:00Z", status: "Generating", summary: "22 agents (1 live, 18 staged), 4 failed jobs, 99.94% uptime, AED 3.2K est. LLM cost." },
];

/* ---------------------------------- Settings --------------------------------- */

export const teamMembers: { name: string; email: string; role: string; markets: string; status: string }[] = [
  { name: "Nada El-Amin", email: "n•••@laundrykhalas.com", role: "Owner", markets: "All markets", status: "Active" },
  { name: "Faris Al-Rashid", email: "f•••@laundrykhalas.com", role: "Ops Manager", markets: "UAE, Qatar", status: "Active" },
  { name: "Huda Salem", email: "h•••@laundrykhalas.com", role: "Quality Lead", markets: "UAE", status: "Active" },
  { name: "Dana Aziz", email: "d•••@laundrykhalas.com", role: "Finance", markets: "All markets", status: "Active" },
  { name: "Layan Kareem", email: "l•••@laundrykhalas.com", role: "Support Agent", markets: "Saudi Arabia, Kuwait", status: "Invited" },
];

export const roles: { role: string; members: number; permissions: string }[] = [
  { role: "Owner", members: 1, permissions: "Full access · billing · settings" },
  { role: "Ops Manager", members: 2, permissions: "Orders · tickets · approvals · drivers" },
  { role: "Quality Lead", members: 1, permissions: "Tickets · quality · limited approvals" },
  { role: "Finance", members: 1, permissions: "Finance · reports · read-only ops" },
  { role: "Support Agent", members: 3, permissions: "Conversations · tickets (assigned)" },
];

export const connectedApps: ConnectedApp[] = [
  { name: "WhatsApp Cloud API", category: "Messaging", status: "Needs approval" },
  { name: "Stripe", category: "Payments", status: "Not connected" },
  { name: "Google Search Console", category: "SEO", status: "Coming soon" },
  { name: "Google Analytics 4", category: "Analytics", status: "Coming soon" },
  { name: "Semrush", category: "SEO", status: "Coming soon" },
  { name: "Ahrefs", category: "SEO", status: "Coming soon" },
  { name: "Instagram", category: "Social", status: "Coming soon" },
  { name: "Facebook", category: "Social", status: "Coming soon" },
  { name: "TikTok", category: "Social", status: "Coming soon" },
  { name: "LinkedIn", category: "Social", status: "Coming soon" },
  { name: "HeyGen", category: "Creative", status: "Coming soon" },
  { name: "Gamma", category: "Creative", status: "Coming soon" },
  { name: "Composio", category: "Automation", status: "Coming soon" },
  { name: "Apollo", category: "Outreach", status: "Coming soon" },
  { name: "Gmail", category: "Outreach", status: "Coming soon" },
  { name: "Meta WhatsApp", category: "Messaging", status: "Needs approval" },
  { name: "PostgreSQL", category: "Database", status: "Not connected" },
  { name: "Redis", category: "Cache / Queue", status: "Not connected" },
  { name: "Cloudflare R2", category: "Storage", status: "Coming soon" },
  { name: "Cloudflare Workers", category: "Edge / Gateway", status: "Coming soon" },
  { name: "Monitoring / Logging", category: "Observability", status: "Coming soon" },
  { name: "LLM Gateway", category: "AI", status: "Needs approval" },
];

export const marketConfig: { market: string; cities: string[]; currency: string; status: string }[] = [
  { market: "UAE", cities: ["Dubai", "Abu Dhabi", "Sharjah"], currency: "AED", status: "Live" },
  { market: "Qatar", cities: ["Doha"], currency: "QAR", status: "Live" },
  { market: "Saudi Arabia", cities: ["Riyadh"], currency: "SAR", status: "Live" },
  { market: "Kuwait", cities: ["Kuwait City"], currency: "KWD", status: "Pilot" },
  { market: "Bahrain", cities: ["Manama"], currency: "BHD", status: "Pilot" },
  { market: "Oman", cities: ["Muscat"], currency: "OMR", status: "Pilot" },
];
