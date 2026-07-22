"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChevronRight, ArrowLeft, RefreshCw, Truck, Building2, CalendarClock,
  MessageSquare, StickyNote, ArrowUpRight, PackageCheck, CheckCircle2, Ban, Undo2,
} from "lucide-react";
import { StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { orderStatusTone } from "@/lib/dashboard/status-maps";
import { formatRelativeTime } from "@/lib/dashboard/formatters";
import type { Order } from "@/lib/dashboard/types";
import { orderPriority, priorityTone, relatedConversation } from "./data";
import { ActionMenu, Chip, type MenuItem } from "./primitives";

/**
 * Top bar: breadcrumb, back, order identity + badges, and a clean grouped action
 * set (primary buttons + a "More actions" overflow that holds secondary and
 * destructive actions). Actions are visual in mock mode except real navigations
 * (back, open conversation).
 */
export function OrderHeader({ order, backHref }: { order: Order; backHref: string }) {
  const router = useRouter();
  const priority = orderPriority(order);
  const conv = relatedConversation(order);
  const cancellable = order.status !== "Delivered" && order.status !== "Cancelled";

  const openConversation = () => {
    const base = "/operations/customer-facing";
    router.push(conv ? `${base}?conversationId=${conv.id}&orderId=${order.id}` : base);
  };

  const menuItems: MenuItem[] = [
    { label: "Add internal note", icon: StickyNote },
    { label: "Open customer conversation", icon: MessageSquare, onClick: openConversation },
    { label: "Escalate to human", icon: ArrowUpRight },
    { label: "Mark ready for delivery", icon: PackageCheck, disabled: order.status === "Delivered" || order.status === "Cancelled" },
    { label: "Mark delivered", icon: CheckCircle2, disabled: order.status === "Delivered" || order.status === "Cancelled" },
    { label: "Cancel order", icon: Ban, tone: "danger", disabled: !cancellable },
    { label: "Request refund review", icon: Undo2, approval: true },
  ];

  return (
    <div className="space-y-4">
      {/* breadcrumb */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-ink-muted">
        <Link href="/operations" className="transition-colors hover:text-ink">Operations</Link>
        <ChevronRight className="h-3 w-3 text-ink-faint" />
        <Link href={backHref} className="transition-colors hover:text-ink">Customer Orders</Link>
        <ChevronRight className="h-3 w-3 text-ink-faint" />
        <span className="font-medium text-ink">Order {order.id}</span>
      </nav>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        {/* identity */}
        <div className="flex items-start gap-3">
          <Link
            href={backHref}
            aria-label="Back to Customer Orders"
            className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2 text-ink-muted transition-colors hover:border-border-strong hover:text-ink"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">{order.id}</h1>
              <StatusBadge tone={orderStatusTone[order.status]}>{order.status}</StatusBadge>
              <Chip tone="info">{order.service}</Chip>
              {priority !== "Standard" && <Chip tone={priorityTone[priority]}>{priority} priority</Chip>}
            </div>
            <p className="mt-1.5 text-sm text-ink-muted">
              {order.customer} · {order.city}, {order.market} · via {order.channel}
              <span className="text-ink-faint"> · created {formatRelativeTime(order.createdAt)}</span>
            </p>
          </div>
        </div>

        {/* actions */}
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" size="sm"><RefreshCw className="h-3.5 w-3.5" /> Change status</Button>
          <Button variant="secondary" size="sm"><Truck className="h-3.5 w-3.5" /> Assign driver</Button>
          <Button variant="secondary" size="sm"><Building2 className="h-3.5 w-3.5" /> Assign facility</Button>
          <Button variant="secondary" size="sm"><CalendarClock className="h-3.5 w-3.5" /> Reschedule</Button>
          <ActionMenu items={menuItems} />
        </div>
      </div>
    </div>
  );
}
