import Link from "next/link";
import { UserX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { PartnerLeadDetailPage } from "@/components/dashboard/partner-acquisition/lead-detail/PartnerLeadDetailPage";
import {
  getPartner, getComplianceForPartner, getMeetingsForPartner,
} from "@/components/dashboard/partner-acquisition/lead-detail/data";

/**
 * Dedicated full-page Partner lead detail — the heavy record + ALL actions.
 * Server component: reads the lead id + originating status tab from the route so
 * "back" returns to the exact pipeline view the operator came from.
 */
export default async function PartnerLeadDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ leadId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { leadId: raw } = await params;
  const sp = await searchParams;
  const leadId = decodeURIComponent(raw);
  const tab = typeof sp.tab === "string" ? sp.tab : undefined;
  const backHref = tab ? `/partner-acquisition/pipeline?tab=${tab}` : "/partner-acquisition/pipeline";

  const partner = getPartner(leadId);

  if (!partner) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <UserX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Partner lead not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No partner lead matches “{leadId}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Pipeline</Button></Link>
      </div>
    );
  }

  return (
    <PartnerLeadDetailPage
      partner={partner}
      compliance={getComplianceForPartner(partner.name)}
      meetings={getMeetingsForPartner(partner.name)}
      backHref={backHref}
    />
  );
}
