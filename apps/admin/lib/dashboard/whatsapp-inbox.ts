/**
 * WhatsApp Agent inbox — data model + seeded conversations.
 *
 * This is the operator-facing inbox surface for the WhatsApp Operations Agent.
 * It is MOCK/LOCAL for now: the conversations below are seeded so the inbox can
 * be demoed and reviewed without a live WhatsApp connection. The shapes here
 * intentionally mirror the documented backend contract
 *   GET  /api/conversations
 *   GET  /api/conversations/{id}
 *   POST /api/conversations/{id}/human-takeover | return-to-bot | human-message | resolve
 * so real webhook-delivered messages can later populate the same structures
 * with no UI change. Customer messages are NEVER authored from the dashboard —
 * they arrive from a real device / WhatsApp Cloud API webhook (or a seed).
 *
 * Privacy: phones are stored full but ALWAYS masked at render (maskPhone).
 * No full addresses, no card/bank details — area + city only.
 */

import type { Tone } from "./types";

export type InboxStatus = "bot" | "human_needed" | "human_takeover" | "resolved";
export type InboxPriority = "urgent" | "high" | "medium" | "low";
export type InboxSender = "customer" | "agent" | "human" | "system";

export interface InboxAction {
  id: string;
  label: string;
}

export interface InboxMessage {
  id: string;
  sender: InboxSender;
  text: string;
  createdAt: string;
  /** System/internal notes render as a separate note card, not a chat bubble. */
  isInternal?: boolean;
  /** Small label under outgoing bubbles: "AI Draft", "Sent by Agent", "Sent by Human". */
  authorLabel?: string;
  /** Quick-reply / menu buttons attached to this specific agent message. */
  actions?: InboxAction[];
}

export interface InboxFlag {
  reason: string; // e.g. "Refund request"
  priority: InboxPriority;
  team: string; // e.g. "Customer Facing / Finance"
  suggestedReply?: string;
  suggestedAction?: string;
}

/** Compact, privacy-safe order summary shown inside a conversation. */
export interface InboxOrder {
  id: string;
  service: string;
  status: string;
  area: string;
  city: string;
  payment: string;
  pickupSlot: string;
  lastUpdate: string; // ISO
}

export interface InboxConversation {
  id: string;
  customerName: string;
  phone: string; // full — masked at render
  city: string;
  area: string;
  service: string | null;
  status: InboxStatus;
  priority: InboxPriority | null;
  handoffReason: string | null;
  assignedTeam: string | null;
  unread: number;
  lastMessage: string;
  lastMessageAt: string;
  order: InboxOrder | null;
  flag: InboxFlag | null;
  notes: string[];
  messages: InboxMessage[];
  /**
   * Provenance markers mirrored from the Supabase row (is_test_data / is_demo).
   * Seeded/demo conversations render "Test Data" / "Demo Conversation" badges so
   * operators always know a thread is not a real customer. Optional here so a
   * future live-webhook conversation can leave them unset/false.
   */
  isTestData?: boolean;
  isDemo?: boolean;
}

/* ------------------------------- status meta ------------------------------- */

export const statusMeta: Record<InboxStatus, { label: string; tone: Tone }> = {
  bot: { label: "Bot Handling", tone: "info" },
  human_needed: { label: "Human Needed", tone: "warning" },
  human_takeover: { label: "Human Takeover", tone: "rose" },
  resolved: { label: "Resolved", tone: "neutral" },
};

export const priorityTone: Record<InboxPriority, Tone> = {
  urgent: "danger",
  high: "warning",
  medium: "info",
  low: "neutral",
};

/* ------------------------------ filter chips ------------------------------- */

export type InboxFilter = "all" | "human_needed" | "urgent" | "active_orders" | "resolved";

export const inboxFilters: { id: InboxFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "human_needed", label: "Human Needed" },
  { id: "urgent", label: "Urgent" },
  { id: "active_orders", label: "Active Orders" },
  { id: "resolved", label: "Resolved" },
];

export function matchesFilter(c: InboxConversation, filter: InboxFilter): boolean {
  switch (filter) {
    case "human_needed":
      return c.status === "human_needed" || c.status === "human_takeover";
    case "urgent":
      return c.priority === "urgent";
    case "active_orders":
      return !!c.order && c.status !== "resolved";
    case "resolved":
      return c.status === "resolved";
    default:
      return true;
  }
}

export function matchesSearch(c: InboxConversation, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    c.customerName.toLowerCase().includes(q) ||
    c.lastMessage.toLowerCase().includes(q) ||
    (c.order?.id.toLowerCase().includes(q) ?? false) ||
    (c.service?.toLowerCase().includes(q) ?? false) ||
    c.city.toLowerCase().includes(q)
  );
}

/* --------------------------- seeded conversations -------------------------- */
/* Timestamps cluster around the deterministic MOCK_NOW (2026-07-20T10:00Z)     */
/* used across the dashboard so relative times render consistently.            */

export const seedConversations: InboxConversation[] = [
  // 1 — Normal booking flow (bot happily handling)
  {
    id: "wa-1001",
    customerName: "Aisha Rahman",
    phone: "+971 50 220 4471",
    city: "Dubai",
    area: "Dubai Marina",
    service: "Wash & Fold",
    status: "bot",
    priority: null,
    handoffReason: null,
    assignedTeam: null,
    unread: 0,
    lastMessage: "Sure. Which service do you need today?",
    lastMessageAt: "2026-07-20T09:52:00Z",
    order: null,
    flag: null,
    notes: [],
    messages: [
      { id: "m1", sender: "customer", text: "Hi, I need laundry pickup today", createdAt: "2026-07-20T09:50:00Z" },
      {
        id: "m2",
        sender: "agent",
        text: "Sure. Which service do you need today?",
        createdAt: "2026-07-20T09:52:00Z",
        authorLabel: "Sent by Agent",
        actions: [
          { id: "a-wf", label: "Wash & Fold" },
          { id: "a-dc", label: "Dry Cleaning" },
          { id: "a-ir", label: "Ironing" },
        ],
      },
    ],
  },

  // 2 — Refund, urgent (flag raised)
  {
    id: "wa-1002",
    customerName: "Amaan Patel",
    phone: "+971 52 664 7712",
    city: "Dubai",
    area: "Business Bay",
    service: "Dry Cleaning",
    status: "human_needed",
    priority: "urgent",
    handoffReason: "Refund request",
    assignedTeam: "Customer Facing / Finance",
    unread: 2,
    lastMessage: "I want my refund now!",
    lastMessageAt: "2026-07-20T09:58:00Z",
    order: {
      id: "LK-AE-1024",
      service: "Dry Cleaning",
      status: "Delivered",
      area: "Business Bay",
      city: "Dubai",
      payment: "Paid",
      pickupSlot: "18 Jul · 14:00–16:00",
      lastUpdate: "2026-07-19T16:20:00Z",
    },
    flag: {
      reason: "Refund request",
      priority: "urgent",
      team: "Customer Facing / Finance",
      suggestedReply:
        "Please hold on while we find a quick solution. Our team will get back to you shortly.",
    },
    notes: ["Refund request flagged · human intervention required."],
    messages: [
      { id: "m1", sender: "customer", text: "This is the second time my order had a problem.", createdAt: "2026-07-20T09:55:00Z" },
      { id: "m2", sender: "customer", text: "I want my refund now!", createdAt: "2026-07-20T09:56:00Z" },
      {
        id: "m3",
        sender: "agent",
        text: "Please hold on while we find a quick solution. Our team will get back to you shortly.",
        createdAt: "2026-07-20T09:58:00Z",
        authorLabel: "Sent by Agent",
      },
      {
        id: "m4",
        sender: "system",
        text: "Refund request flagged · human intervention required",
        createdAt: "2026-07-20T09:58:00Z",
        isInternal: true,
      },
    ],
  },

  // 3 — Damaged item (flag raised, high)
  {
    id: "wa-1003",
    customerName: "Hassan Ali",
    phone: "+971 55 771 9930",
    city: "Sharjah",
    area: "Al Nahda",
    service: "Wash & Fold",
    status: "human_needed",
    priority: "high",
    handoffReason: "Damaged item complaint",
    assignedTeam: "Customer Facing / Facility Facing",
    unread: 1,
    lastMessage: "My shirt came back damaged",
    lastMessageAt: "2026-07-20T09:40:00Z",
    order: {
      id: "LK-AE-1026",
      service: "Wash & Fold",
      status: "Delivered",
      area: "Al Nahda",
      city: "Sharjah",
      payment: "Paid",
      pickupSlot: "18 Jul · 10:00–12:00",
      lastUpdate: "2026-07-19T18:05:00Z",
    },
    flag: {
      reason: "Damaged item complaint",
      priority: "high",
      team: "Customer Facing / Facility Facing",
      suggestedAction: "Ask for the order ID and a photo of the damaged item.",
    },
    notes: ["Possible facility quality issue — capture evidence before any commitment."],
    messages: [
      { id: "m1", sender: "customer", text: "My shirt came back damaged", createdAt: "2026-07-20T09:38:00Z" },
      {
        id: "m2",
        sender: "agent",
        text: "I'm sorry about that. Please share your order ID and a photo if possible.",
        createdAt: "2026-07-20T09:40:00Z",
        authorLabel: "Sent by Agent",
      },
      {
        id: "m3",
        sender: "system",
        text: "Damaged item complaint flagged · human intervention required",
        createdAt: "2026-07-20T09:40:00Z",
        isInternal: true,
      },
    ],
  },

  // 4 — Track order (bot handling, no flag)
  {
    id: "wa-1004",
    customerName: "Omar Haddad",
    phone: "+971 50 123 4567",
    city: "Abu Dhabi",
    area: "Al Reem Island",
    service: "Ironing / Pressing",
    status: "bot",
    priority: null,
    handoffReason: null,
    assignedTeam: null,
    unread: 0,
    lastMessage: "Your order LK-AE-1024 is currently pickup scheduled.",
    lastMessageAt: "2026-07-20T09:15:00Z",
    order: {
      id: "LK-AE-1027",
      service: "Ironing / Pressing",
      status: "Pickup Scheduled",
      area: "Al Reem Island",
      city: "Abu Dhabi",
      payment: "Pending",
      pickupSlot: "20 Jul · 16:00–18:00",
      lastUpdate: "2026-07-20T08:50:00Z",
    },
    flag: null,
    notes: [],
    messages: [
      { id: "m1", sender: "customer", text: "Track LK-AE-1027", createdAt: "2026-07-20T09:14:00Z" },
      {
        id: "m2",
        sender: "agent",
        text: "Your order LK-AE-1027 is currently Pickup Scheduled for today 16:00–18:00. I'll send an update when the driver is on the way.",
        createdAt: "2026-07-20T09:15:00Z",
        authorLabel: "Sent by Agent",
        actions: [{ id: "a-slot", label: "Change pickup time" }],
      },
    ],
  },

  // 5 — B2B enquiry (flag raised, medium)
  {
    id: "wa-1005",
    customerName: "Jumeirah Bay Hotel",
    phone: "+971 4 511 2200",
    city: "Dubai",
    area: "Jumeirah",
    service: "Business Laundry",
    status: "human_needed",
    priority: "medium",
    handoffReason: "Business enquiry",
    assignedTeam: "Sales / Partner Acquisition",
    unread: 1,
    lastMessage: "We are a hotel and need laundry service",
    lastMessageAt: "2026-07-20T08:30:00Z",
    order: null,
    flag: {
      reason: "Business enquiry",
      priority: "medium",
      team: "Sales / Partner Acquisition",
      suggestedAction: "Collect business name, location, and estimated weekly laundry volume.",
    },
    notes: ["B2B lead — route to Partner Acquisition for a tailored quote."],
    messages: [
      { id: "m1", sender: "customer", text: "We are a hotel and need laundry service", createdAt: "2026-07-20T08:28:00Z" },
      {
        id: "m2",
        sender: "agent",
        text: "Sure. Please share your hotel name, location, and estimated weekly laundry volume. Our team will contact you.",
        createdAt: "2026-07-20T08:30:00Z",
        authorLabel: "Sent by Agent",
      },
      {
        id: "m3",
        sender: "system",
        text: "Business enquiry flagged · routed to Sales / Partner Acquisition",
        createdAt: "2026-07-20T08:30:00Z",
        isInternal: true,
      },
    ],
  },

  // 6 — Payment issue (flag raised, high)
  {
    id: "wa-1006",
    customerName: "Sara Juma",
    phone: "+968 92 551 3307",
    city: "Muscat",
    area: "Al Khuwair",
    service: "Wash & Fold",
    status: "human_needed",
    priority: "high",
    handoffReason: "Payment issue",
    assignedTeam: "Customer Facing / Finance",
    unread: 1,
    lastMessage: "I was charged twice",
    lastMessageAt: "2026-07-20T08:05:00Z",
    order: {
      id: "LK-AE-1025",
      service: "Wash & Fold",
      status: "In Cleaning",
      area: "Al Khuwair",
      city: "Muscat",
      payment: "Pending",
      pickupSlot: "19 Jul · 12:00–14:00",
      lastUpdate: "2026-07-20T07:40:00Z",
    },
    flag: {
      reason: "Payment issue",
      priority: "high",
      team: "Customer Facing / Finance",
      suggestedAction: "Ask for the order ID and a payment screenshot if available.",
    },
    notes: ["Do not confirm a double charge until Finance verifies the transaction."],
    messages: [
      { id: "m1", sender: "customer", text: "I was charged twice", createdAt: "2026-07-20T08:03:00Z" },
      {
        id: "m2",
        sender: "agent",
        text: "Sorry about that. Please share your order ID and payment screenshot if available.",
        createdAt: "2026-07-20T08:05:00Z",
        authorLabel: "Sent by Agent",
      },
      {
        id: "m3",
        sender: "system",
        text: "Payment issue flagged · human intervention required",
        createdAt: "2026-07-20T08:05:00Z",
        isInternal: true,
      },
    ],
  },

  // 7 — Pickup change (bot handling)
  {
    id: "wa-1007",
    customerName: "Khalid Nasser",
    phone: "+965 99 220 8841",
    city: "Kuwait City",
    area: "Salmiya",
    service: "Dry Cleaning",
    status: "bot",
    priority: null,
    handoffReason: null,
    assignedTeam: null,
    unread: 0,
    lastMessage: "Done — your pickup is moved to 8:00 PM tonight.",
    lastMessageAt: "2026-07-20T07:20:00Z",
    order: {
      id: "LK-AE-1028",
      service: "Dry Cleaning",
      status: "Pickup Scheduled",
      area: "Salmiya",
      city: "Kuwait City",
      payment: "Paid",
      pickupSlot: "20 Jul · 20:00–21:00",
      lastUpdate: "2026-07-20T07:20:00Z",
    },
    flag: null,
    notes: [],
    messages: [
      { id: "m1", sender: "customer", text: "Can you change pickup to 8 PM?", createdAt: "2026-07-20T07:18:00Z" },
      {
        id: "m2",
        sender: "agent",
        text: "Done — your pickup is moved to 8:00 PM tonight. See you then!",
        createdAt: "2026-07-20T07:20:00Z",
        authorLabel: "Sent by Agent",
      },
    ],
  },

  // 8 — Resolved (human handled earlier)
  {
    id: "wa-1008",
    customerName: "Mariam Zayed",
    phone: "+973 33 909 1120",
    city: "Manama",
    area: "Seef",
    service: "Blankets / Duvets",
    status: "resolved",
    priority: null,
    handoffReason: "Late delivery",
    assignedTeam: "Customer Facing",
    unread: 0,
    lastMessage: "Thank you, that works. Appreciate the quick help!",
    lastMessageAt: "2026-07-19T17:40:00Z",
    order: {
      id: "LK-AE-1021",
      service: "Blankets / Duvets",
      status: "Delivered",
      area: "Seef",
      city: "Manama",
      payment: "Paid",
      pickupSlot: "17 Jul · 09:00–11:00",
      lastUpdate: "2026-07-19T17:30:00Z",
    },
    flag: null,
    notes: ["Resolved by Ops — redelivery arranged, customer satisfied."],
    messages: [
      { id: "m1", sender: "customer", text: "My duvet delivery is late, where is it?", createdAt: "2026-07-19T16:55:00Z" },
      {
        id: "m2",
        sender: "human",
        text: "Apologies for the delay — I've arranged delivery for 6 PM today and added a small credit to your account.",
        createdAt: "2026-07-19T17:10:00Z",
        authorLabel: "Sent by Human",
      },
      { id: "m3", sender: "customer", text: "Thank you, that works. Appreciate the quick help!", createdAt: "2026-07-19T17:40:00Z" },
    ],
  },
];
