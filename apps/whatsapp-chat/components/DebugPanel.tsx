import type { TestChatResponse } from "@/lib/types";

const DOMAIN_LABEL: Record<string, string> = {
  in_domain: "In domain",
  out_of_domain: "Out of domain — refused",
  uncertain: "Uncertain — clarifying",
};

export function DebugPanel({ last }: { last: TestChatResponse | null }) {
  return (
    <aside className="hidden w-72 shrink-0 border-l border-wa-border bg-white p-4 text-xs lg:block">
      <h3 className="mb-3 text-sm font-semibold text-wa-text">Developer / Debug Panel</h3>
      {!last ? (
        <p className="text-wa-muted">Send a message to see domain-guard and provider details.</p>
      ) : (
        <dl className="space-y-3">
          <div>
            <dt className="text-wa-muted">Domain guard result</dt>
            <dd className="font-medium text-wa-text">
              {DOMAIN_LABEL[last.domain] ?? last.domain}
            </dd>
          </div>
          <div>
            <dt className="text-wa-muted">Mode</dt>
            <dd className="font-medium text-wa-text">{last.mode}</dd>
          </div>
          <div>
            <dt className="text-wa-muted">Provider</dt>
            <dd className="font-medium text-wa-text">{last.provider}</dd>
          </div>
          <div>
            <dt className="text-wa-muted">Conversation ID</dt>
            <dd className="break-all font-mono text-[11px] text-wa-text">
              {last.conversation_id}
            </dd>
          </div>
          <div>
            <dt className="text-wa-muted">Attached actions</dt>
            <dd className="font-medium text-wa-text">
              {last.actions.length > 0
                ? last.actions.map((a) => a.id).join(", ")
                : "none"}
            </dd>
          </div>
        </dl>
      )}
    </aside>
  );
}
