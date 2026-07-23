import Link from "next/link";
import { PackageX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getRefundAdjustment } from "@/lib/dashboard/finance-compliance-data";
import { RefundDetailPage } from "@/components/dashboard/finance-compliance/refund-detail/RefundDetailPage";

/**
 * Dedicated full-page Refund / adjustment detail — the only place the approval
 * actions (approve / decline, both approval-gated) live. Server component:
 * resolves the reference id and the originating status tab for a precise "back".
 */
export default async function RefundDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ refundId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { refundId: raw } = await params;
  const sp = await searchParams;
  const refundId = decodeURIComponent(raw);
  const tab = typeof sp.tab === "string" ? sp.tab : undefined;
  const backHref = tab
    ? `/finance-compliance/refunds-adjustments?tab=${tab}`
    : "/finance-compliance/refunds-adjustments";

  const refund = getRefundAdjustment(refundId);

  if (!refund) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <PackageX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Request not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No refund or adjustment matches “{refundId}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Refunds &amp; Adjustments</Button></Link>
      </div>
    );
  }

  return <RefundDetailPage refund={refund} backHref={backHref} />;
}
