// Hand-written mirror of app/schemas/*.py response models. Kept in sync
// manually - the backend surface is small and stable enough that codegen
// would be more overhead than value at this stage.

export type OrderStatus =
  | "draft"
  | "created"
  | "awaiting_pickup"
  | "picked_up"
  | "processing"
  | "ready_for_delivery"
  | "out_for_delivery"
  | "delivered"
  | "cancelled"
  | "escalated";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export type MessageDirection = "inbound" | "outbound";

export interface Market {
  id: string;
  code: string;
  name: string;
  country: string;
  currency: string;
  is_active: boolean;
}

export interface Conversation {
  id: string;
  market_id: string;
  customer_id: string;
  channel: string;
  external_thread_id: string | null;
  status: string;
  assigned_to_user_id: string | null;
  manual_takeover: boolean;
  latest_intent: string | null;
  latest_sentiment: string | null;
  latest_urgency: string | null;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  direction: MessageDirection;
  sender_type: string;
  text: string;
  status: string;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface Order {
  id: string;
  market_id: string;
  customer_id: string;
  facility_id: string | null;
  status: OrderStatus | string;
  service_type: string;
  // Canonical 8-service taxonomy fields (optional — added additively by the
  // backend; existing React-Query pages must still compile without them).
  service_id?: string | null;
  service_display_name?: string | null;
  items_json: Record<string, unknown>;
  address_id: string | null;
  pickup_window_start: string | null;
  pickup_window_end: string | null;
  delivery_window_start: string | null;
  delivery_window_end: string | null;
  estimated_total: number | null;
  payment_status: string;
  source_channel: string;
  created_at: string;
  updated_at: string;
}

export interface OrderEvent {
  id: string;
  order_id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  actor_type: string;
  actor_id: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface HumanApproval {
  id: string;
  market_id: string;
  conversation_id: string | null;
  order_id: string | null;
  requested_by_agent: string;
  action_type: string;
  reason: string | null;
  proposed_payload_json: { text?: string; [key: string]: unknown };
  status: ApprovalStatus | string;
  approved_by: string | null;
  rejected_by: string | null;
  decision_note: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface AIActionLog {
  id: string;
  market_id: string;
  conversation_id: string | null;
  order_id: string | null;
  agent_name: string;
  action_type: string;
  tool_name: string | null;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown>;
  model_name: string | null;
  provider: string | null;
  tokens_in: number;
  tokens_out: number;
  estimated_cost: number;
  latency_ms: number | null;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

export interface MockInboundResponse {
  conversation_id: string;
  message_id: string;
  customer_id: string;
}

export interface RunAgentResponse {
  decision: "ask_followup" | "create_order" | "escalate" | string;
  approval_id: string | null;
  order_id: string | null;
  draft_reply_text: string | null;
}
