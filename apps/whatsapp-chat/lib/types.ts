// Hand-written mirror of the standalone agent's schemas.py response models.

export type DomainStatus = "in_domain" | "out_of_domain" | "uncertain";
export type Mode = "mock" | "live";

export interface MessageAction {
  id: string;
  label: string;
  type: "quick_reply";
}

export interface Message {
  id: string;
  conversation_id: string;
  direction: "inbound" | "outbound";
  sender_type: string;
  text: string;
  domain_status: DomainStatus | null;
  created_at: string;
  /** Only present on the message just returned by a live send - not
   * persisted server-side, so a reloaded conversation's older bubbles
   * won't show their buttons again. See architecture doc for why. */
  actions?: MessageAction[];
}

export interface TestChatResponse {
  conversation_id: string;
  user_message: string;
  agent_reply: string;
  domain: DomainStatus;
  mode: Mode;
  provider: string;
  actions: MessageAction[];
  /** Set when this turn created/touched a mock order behind the scenes. */
  order_id?: string | null;
  order_status?: string | null;
}

export interface SettingsStatus {
  app_env: string;
  agent_mode: string;
  llm_provider: string;
  llm_live_ready: boolean;
  whatsapp_mode: string;
  whatsapp_live_ready: boolean;
  database_kind: string;
  agent_min_typing_delay_ms: number;
  agent_max_typing_delay_ms: number;
}
