import Link from "next/link";
import { SearchX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getTicket } from "@/components/dashboard/operations/support-detail/data";
import { TicketDetailPage } from "@/components/dashboard/operations/support-detail/TicketDetailPage";

/**
 * Dedicated full-page support ticket detail — replaces the old right-side drawer
 * for tickets, complaints and escalations. Server component: "back" returns to
 * the originating Customer Facing tab.
 */
export default async function TicketDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ ticketId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { ticketId } = await params;
  const sp = await searchParams;
  const tab = typeof sp.tab === "string" ? sp.tab : undefined;
  const backHref = tab ? `/operations/customer-facing?tab=${tab}` : "/operations/customer-facing";

  const ticket = getTicket(decodeURIComponent(ticketId));

  if (!ticket) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <SearchX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Ticket not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No ticket matches this link.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Customer Facing</Button></Link>
      </div>
    );
  }

  return <TicketDetailPage ticket={ticket} backHref={backHref} />;
}
