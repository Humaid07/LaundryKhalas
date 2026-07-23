import Link from "next/link";
import { PackageX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getPaymentRecord } from "@/lib/dashboard/finance-compliance-data";
import { PaymentDetailPage } from "@/components/dashboard/finance-compliance/payment-detail/PaymentDetailPage";

/**
 * Dedicated full-page Customer payment detail — the only place per-record payment
 * actions live (progressive disclosure). Server component: resolves the order id
 * and the originating status tab so "back" returns to the exact payments view.
 */
export default async function PaymentDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ orderId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { orderId: raw } = await params;
  const sp = await searchParams;
  const orderId = decodeURIComponent(raw);
  const tab = typeof sp.tab === "string" ? sp.tab : undefined;
  const backHref = tab
    ? `/finance-compliance/customer-payments?tab=${tab}`
    : "/finance-compliance/customer-payments";

  const payment = getPaymentRecord(orderId);

  if (!payment) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <PackageX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Payment not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No payment record matches “{orderId}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Customer Payments</Button></Link>
      </div>
    );
  }

  return <PaymentDetailPage payment={payment} backHref={backHref} />;
}
