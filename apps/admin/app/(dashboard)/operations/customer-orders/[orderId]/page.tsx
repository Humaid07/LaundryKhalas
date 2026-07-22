import Link from "next/link";
import { PackageX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getOrder } from "@/components/dashboard/operations/order-detail/data";
import { CustomerOrderDetailPage } from "@/components/dashboard/operations/order-detail/CustomerOrderDetailPage";

/**
 * Dedicated full-page Customer Order detail — replaces the old right-side drawer.
 * Server component: reads the order id + active status tab from the route so no
 * client-side search-param hook (and no Suspense boundary) is needed. The `?tab=`
 * value is carried back into the list link so "back" returns to the exact view
 * the operator came from (global filters persist via the dashboard FiltersProvider).
 * See docs/architecture/customer-order-detail-page.md.
 */
export default async function CustomerOrderDetailRoute({
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
  const backHref = tab ? `/operations/customer-orders?tab=${tab}` : "/operations/customer-orders";

  const order = getOrder(orderId);

  if (!order) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <PackageX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Order not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No order matches “{orderId}”. It may have been removed or the link is out of date.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Customer Orders</Button></Link>
      </div>
    );
  }

  return <CustomerOrderDetailPage order={order} backHref={backHref} />;
}
