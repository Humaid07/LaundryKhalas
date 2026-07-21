export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const ADMIN_API_KEY =
  process.env.NEXT_PUBLIC_ADMIN_API_KEY ?? "changeme_local_admin_key";

export const MARKET_CODES = ["AE", "QA"] as const;

export const SAMPLE_MESSAGES: string[] = [
  "I need laundry pickup tomorrow",
  "How much for dry cleaning suit?",
  "Can you pick up from Dubai Marina tonight?",
  "I want to cancel my order",
  "This service is terrible",
];

// Messages the WhatsApp Agent has no tool for yet (no refund/cancellation/
// complaint-handling tools exist by design - see agents/whatsapp_operations/tools.py).
// The console flags these so testers don't mistake "agent asked a generic
// follow-up" for "agent handled the cancellation/complaint."
export const OUT_OF_SCOPE_HINTS: { match: RegExp; hint: string }[] = [
  {
    match: /cancel/i,
    hint: "The agent has no cancellation tool - it will only ask a generic follow-up question or escalate. Cancellation handling is out of scope for this MVP.",
  },
  {
    match: /terrible|complain|refund|compensat/i,
    hint: "The agent has no complaint/refund/compensation tool - it will only ask a generic follow-up question or escalate. Complaint handling is out of scope for this MVP.",
  },
];
