import Link from "next/link";
import { Megaphone } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getCampaign } from "@/lib/dashboard/marketing-data";
import { CampaignDetailPage } from "@/components/dashboard/marketing/campaign-detail/CampaignDetailPage";

/**
 * Dedicated full-page Campaign detail — the click-through target for a campaign
 * card. Server component: reads the campaign id + originating status tab so
 * "back" returns to the exact Campaigns view the operator came from.
 */
export default async function CampaignDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ campaignId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { campaignId: raw } = await params;
  const sp = await searchParams;
  const campaignId = decodeURIComponent(raw);
  const tab = typeof sp.tab === "string" ? sp.tab : undefined;
  const backHref = tab ? `/marketing/campaigns?tab=${tab}` : "/marketing/campaigns";

  const campaign = getCampaign(campaignId);

  if (!campaign) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <Megaphone className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Campaign not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No campaign matches “{campaignId}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Campaigns</Button></Link>
      </div>
    );
  }

  return <CampaignDetailPage campaign={campaign} backHref={backHref} />;
}
