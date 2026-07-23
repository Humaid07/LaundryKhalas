import Link from "next/link";
import { PackageX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getFacilityOrder } from "@/components/dashboard/operations/facility-detail/data";
import { FacilityOrderDetailPage } from "@/components/dashboard/operations/facility-detail/FacilityOrderDetailPage";

/**
 * Dedicated full-page Facility order detail — replaces the old right-side drawer.
 * Server component: reads the order id + originating status tab from the route so
 * "back" returns to the exact facility view the operator came from.
 */
export default async function FacilityOrderDetailRoute({
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
  const backHref = tab ? `/operations/facility-facing?tab=${tab}` : "/operations/facility-facing";

  const order = getFacilityOrder(orderId);

  if (!order) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <PackageX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Facility order not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No facility order matches “{orderId}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Facility Facing</Button></Link>
      </div>
    );
  }

  return <FacilityOrderDetailPage order={order} backHref={backHref} />;
}
