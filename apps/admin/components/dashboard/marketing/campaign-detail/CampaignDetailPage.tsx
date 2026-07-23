"use client";

import {
  Megaphone, GitBranch, Gauge, Radio, Rocket, Pause, Play,
  PencilLine, Copy, StopCircle, StickyNote, Target,
} from "lucide-react";
import {
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, type MenuItem,
} from "@/components/dashboard/minimal";
import {
  campaignStatusTone, campaignCpl, CAMPAIGN_LIFECYCLE, type Campaign,
} from "@/lib/dashboard/marketing-data";
import { formatCurrency, formatNumber } from "@/lib/dashboard/formatters";

function ProgressCard({ campaign }: { campaign: Campaign }) {
  const currentIdx = CAMPAIGN_LIFECYCLE.indexOf(campaign.status);
  return (
    <DetailSectionCard title="Campaign lifecycle" icon={GitBranch}>
      <ol className="space-y-3">
        {CAMPAIGN_LIFECYCLE.map((s, i) => {
          const done = currentIdx >= 0 && i <= currentIdx;
          const current = s === campaign.status;
          return (
            <li key={s} className="flex gap-3">
              <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${done ? "bg-rose" : "bg-ink-faint/40"}`} />
              <div className="min-w-0">
                <p className="text-sm text-ink">{s}</p>
                {current && <p className="text-xxs text-ink-faint">Current stage</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </DetailSectionCard>
  );
}

const ACTIONS = (c: Campaign): MenuItem[] => [
  { label: "Launch campaign", icon: Rocket, approval: true, disabled: c.status === "Active" || c.status === "Ended" },
  { label: "Pause campaign", icon: Pause, disabled: c.status !== "Active" },
  { label: "Resume campaign", icon: Play, disabled: c.status !== "Paused" },
  { label: "Edit budget & targeting", icon: PencilLine },
  { label: "Duplicate campaign", icon: Copy },
  { label: "Add note", icon: StickyNote },
  { label: "End campaign", icon: StopCircle, tone: "danger", approval: true, disabled: c.status === "Ended" },
];

export function CampaignDetailPage({ campaign, backHref }: { campaign: Campaign; backHref: string }) {
  return (
    <DetailPageShell
      backHref={backHref}
      backLabel="Campaigns"
      eyebrow="Marketing campaign"
      title={campaign.name}
      status={<StatusBadge tone={campaignStatusTone[campaign.status]} dot={false}>{campaign.status}</StatusBadge>}
      actions={<ActionMenu items={ACTIONS(campaign)} />}
    >
      <DetailColumns
        main={
          <>
            <DetailSectionCard title="Campaign" icon={Megaphone}>
              <FieldGrid>
                <Field label="Campaign ID" value={campaign.id} mono />
                <Field label="Name" value={campaign.name} />
                <Field label="Channels" value={campaign.channel} />
                <Field label="Status" value={<Chip tone={campaignStatusTone[campaign.status]}>{campaign.status}</Chip>} />
              </FieldGrid>
            </DetailSectionCard>

            <DetailSectionCard title="Performance" icon={Gauge}>
              <FieldGrid cols={3}>
                <Field label="Spend" value={formatCurrency(campaign.spend)} />
                <Field label="Reach" value={formatNumber(campaign.reach, true)} />
                <Field label="Leads" value={String(campaign.leads)} />
                <Field label="ROAS" value={campaign.roas} />
                <Field label="Cost / lead" value={campaignCpl(campaign)} />
              </FieldGrid>
            </DetailSectionCard>

            <ProgressCard campaign={campaign} />
          </>
        }
        sidebar={
          <>
            <DetailSectionCard title="Delivery" icon={Radio}>
              <FieldGrid cols={2}>
                <Field label="Channels" value={campaign.channel} />
                <Field label="Status" value={<Chip tone={campaignStatusTone[campaign.status]}>{campaign.status}</Chip>} />
              </FieldGrid>
            </DetailSectionCard>
            <DetailSectionCard title="Targeting" icon={Target}>
              <p className="text-xs leading-relaxed text-ink-muted">
                Audience, budget and schedule are managed from the ActionMenu. Go-live and end actions are approval-gated — nothing spends without a human sign-off.
              </p>
            </DetailSectionCard>
          </>
        }
      />
    </DetailPageShell>
  );
}
