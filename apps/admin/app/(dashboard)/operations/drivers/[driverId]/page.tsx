import Link from "next/link";
import { UserX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getDriver } from "@/components/dashboard/operations/driver-detail/data";
import { DriverDetailPage } from "@/components/dashboard/operations/driver-detail/DriverDetailPage";

/**
 * Dedicated full-page Driver detail — replaces the old right-side drawer. Shows a
 * driver plus all of their assigned pickup/delivery tasks and open issues, with
 * actions in the header menu. Driver-facing: customer area/city only, no PII.
 */
export default async function DriverDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ driverId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { driverId } = await params;
  const sp = await searchParams;
  const tab = typeof sp.tab === "string" ? sp.tab : undefined;
  const backHref = tab ? `/operations/drivers?tab=${tab}` : "/operations/drivers";

  const data = getDriver(decodeURIComponent(driverId));

  if (!data) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <UserX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Driver not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No driver matches this link.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Drivers</Button></Link>
      </div>
    );
  }

  return <DriverDetailPage data={data} backHref={backHref} />;
}
