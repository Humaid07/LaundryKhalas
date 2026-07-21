/**
 * Client for the standalone WhatsApp Agent backend (apps/whatsapp-agent, :8100).
 * This is an existing *local mock* service (LLM + WhatsApp both in mock mode) —
 * no live third-party calls. Used by the Operations → WhatsApp Agent tab.
 */

const BASE_URL = process.env.NEXT_PUBLIC_WHATSAPP_AGENT_API_URL ?? "http://localhost:8100";

export type DomainStatus = "in_domain" | "out_of_domain" | "uncertain";

export interface AgentAction {
  id: string;
  label: string;
  type: string;
}

export interface AgentReply {
  conversation_id: string;
  user_message: string;
  agent_reply: string;
  domain: DomainStatus;
  mode: "mock" | "live";
  provider: string;
  actions: AgentAction[];
}

export interface AgentSettingsStatus {
  app_env: string;
  agent_mode: string;
  llm_provider: string;
  llm_live_ready: boolean;
  whatsapp_mode: string;
  whatsapp_live_ready: boolean;
  database_kind: string;
}

export class AgentApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new AgentApiError(0, "Could not reach the WhatsApp agent backend (:8100). Is it running?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new AgentApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const agentApi = {
  baseUrl: BASE_URL,

  health: () => request<{ status: string }>("/health"),

  settingsStatus: () => request<AgentSettingsStatus>("/api/settings/status"),

  sendMessage: (payload: {
    conversation_id?: string;
    sender_name?: string;
    phone_number?: string;
    message: string;
    action_id?: string;
  }) =>
    request<AgentReply>("/api/test-chat/message", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
