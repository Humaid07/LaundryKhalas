"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle, ArrowLeft, ClipboardList, Clock, MapPin, MessageSquare, X,
} from "lucide-react";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { EmptyState, LoadingState } from "@/components/dashboard/ui/states";
import {
  agentApi, type InboxConversationDTO, type InboxMessageDTO, type OrderDTO,
} from "@/lib/dashboard/whatsapp-agent-api";
import { statusMeta } from "@/lib/dashboard/order-status";

const POLL_MS = 15000;

function fmtTime(v?: string | null): string {
  if (!v) return "";
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleString("en-GB", { timeZone: "Asia/Dubai", dateStyle: "short", timeStyle: "short" });
}
function fmtDate(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleDateString("en-GB", { timeZone: "Asia/Dubai", dateStyle: "medium" });
}

/**
 * Renders the exact WhatsApp conversation for an order when the Operations page
 * is opened via /operations/customer-facing?conversationId=…&orderId=… (from an
 * order card's "Open Chat in Operations" button). Reads the linked conversation
 * by its stored id (never by phone/name matching), shows an order-context header,
 * and lets staff start/end human takeover. Renders nothing when no param is set,
 * so the normal Operations page is unaffected.
 */
export function OperationsDeepLink() {
  const params = useSearchParams();
  const router = useRouter();
  const conversationId = params.get("conversationId");
  const orderId = params.get("orderId");

  const [convo, setConvo] = useState<InboxConversationDTO | null>(null);
  const [messages, setMessages] = useState<InboxMessageDTO[]>([]);
  const [order, setOrder] = useState<OrderDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (spinner = false) => {
    if (!conversationId) return;
    if (spinner) setLoading(true);
    try {
      const [c, m] = await Promise.all([
        agentApi.getConversation(conversationId),
        agentApi.getMessages(conversationId),
      ]);
      setConvo(c);
      setMessages(m);
      if (orderId) {
        try { setOrder(await agentApi.getOrder(orderId)); } catch { /* order optional */ }
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load the conversation");
    } finally {
      setLoading(false);
    }
  }, [conversationId, orderId]);

  useEffect(() => {
    if (!conversationId) return;
    load(true);
    const id = setInterval(() => load(false), POLL_MS);
    return () => clearInterval(id);
  }, [conversationId, load]);

  if (!conversationId) return null;

  const close = () => router.push("/operations/customer-facing");
  const inTakeover = convo?.status === "human_takeover";

  async function toggleTakeover() {
    if (!conversationId) return;
    setBusy(true);
    try {
      if (inTakeover) await agentApi.returnToBot(conversationId);
      else await agentApi.startHumanTakeover(conversationId, "Operations");
      await load(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Takeover action failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel padded={false} className="border-rose/30">
      <PanelHeader
        title={<span className="flex items-center gap-2"><MessageSquare className="h-4 w-4 text-rose" /> Conversation for order {orderId ?? ""}</span>}
        subtitle="Opened from the Orders section · showing the exact linked chat"
        className="p-4"
        action={
          <div className="flex items-center gap-2">
            {orderId && (
              <Link href="/orders" className="inline-flex items-center gap-1 rounded-lg bg-surface-2 px-2.5 py-1 text-xs font-semibold text-ink-muted hover:text-ink">
                <ArrowLeft className="h-3.5 w-3.5" /> Orders
              </Link>
            )}
            <button onClick={close} aria-label="Close conversation view" className="rounded-lg p-1 text-ink-faint hover:bg-surface-2 hover:text-ink">
              <X className="h-4 w-4" />
            </button>
          </div>
        }
      />

      {loading ? (
        <div className="p-4"><LoadingState label="Loading conversation…" /></div>
      ) : error ? (
        <div className="p-4">
          <EmptyState icon={AlertTriangle} title="Conversation unavailable" description={error}
            action={<Button size="sm" variant="secondary" onClick={() => load(true)}>Try again</Button>} />
        </div>
      ) : (
        <div className="grid gap-0 lg:grid-cols-[1fr_18rem]">
          {/* Thread */}
          <div className="flex max-h-[28rem] flex-col gap-2 overflow-y-auto border-t border-border p-4">
            {messages.length === 0 ? (
              <p className="text-xs text-ink-muted">No messages in this conversation yet.</p>
            ) : (
              messages.map((m) => {
                const mine = m.sender_type !== "customer";
                return (
                  <div key={m.id} className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                    mine ? "self-end bg-rose/10 text-ink" : "self-start bg-surface-2 text-ink"
                  } ${m.is_internal ? "border border-dashed border-border italic text-ink-muted" : ""}`}>
                    <p className="whitespace-pre-wrap">{m.message_text}</p>
                    <span className="mt-1 block text-xxs text-ink-faint">{m.sender_type} · {fmtTime(m.created_at)}</span>
                  </div>
                );
              })
            )}
          </div>

          {/* Order-context panel */}
          <aside className="border-t border-border bg-surface-2/50 p-4 lg:border-l lg:border-t-0">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold text-ink">Order context</span>
              {inTakeover && <StatusBadge tone="warning">Human takeover</StatusBadge>}
            </div>
            {order ? (
              <div className="space-y-1.5 text-xs text-ink-muted">
                <p className="font-mono font-semibold text-ink">{order.order_id}</p>
                <p className="flex items-center gap-1.5"><ClipboardList className="h-3 w-3" />{order.service_display_name ?? order.service_type ?? "—"}</p>
                <p className="flex items-center gap-1.5"><Clock className="h-3 w-3" />{fmtDate(order.pickup_date)}{order.pickup_time ? ` · ${order.pickup_time}` : ""}</p>
                <p className="flex items-center gap-1.5"><MapPin className="h-3 w-3" />{order.pickup_address ?? order.pickup_area ?? "—"}</p>
                {order.pickup_instructions && <p>📝 {order.pickup_instructions}</p>}
                <div className="pt-1"><StatusBadge tone={statusMeta(order.status).tone}>{order.status_label || statusMeta(order.status).label}</StatusBadge></div>
              </div>
            ) : (
              <p className="text-xs text-ink-muted">No order linked, or the order could not be loaded.</p>
            )}
            <div className="mt-4 space-y-2">
              <Button size="sm" variant={inTakeover ? "secondary" : "primary"} onClick={toggleTakeover} disabled={busy} className="w-full">
                {busy ? "…" : inTakeover ? "Return to bot" : "Take over"}
              </Button>
            </div>
          </aside>
        </div>
      )}
    </Panel>
  );
}
