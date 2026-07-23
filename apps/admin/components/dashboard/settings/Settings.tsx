import { User, Globe, Plug, Bot, Bell, Palette, ShieldCheck } from "lucide-react";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Switch } from "@/components/dashboard/ui/Switch";
import { ThemeToggle } from "@/components/dashboard/shell/ThemeToggle";
import { ConnectedAppRow } from "@/components/dashboard/widgets";
import { connectedApps, marketConfig } from "@/lib/dashboard/mock-data";
import { ProfileTeamPanel, RolesPermissionsPanel } from "./UserManagement";

function SettingsSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof User;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <Panel>
      <div className="mb-4 flex items-start gap-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose/10 text-rose"><Icon className="h-4 w-4" /></span>
        <div>
          <h3 className="font-display text-sm font-semibold text-ink">{title}</h3>
          <p className="text-xs text-ink-muted">{description}</p>
        </div>
      </div>
      {children}
    </Panel>
  );
}

function ReviewModeBanner() {
  return (
    <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-info/25 bg-info/8 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <ShieldCheck className="h-5 w-5 text-info" />
        <div>
          <p className="text-sm font-semibold text-ink">Review mode is on</p>
          <p className="text-xs text-ink-muted">Agent-drafted replies and actions are held for approval before anything reaches a customer, payment or channel.</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <StatusBadge tone="info" dot={false}>WhatsApp · Review</StatusBadge>
        <StatusBadge tone="info" dot={false}>Payments · Review</StatusBadge>
        <StatusBadge tone="info" dot={false}>AI · Review</StatusBadge>
      </div>
    </div>
  );
}

/* -------------------------------- Subsections ------------------------------- */
/* Profile/Users and Roles & Permissions are real, RBAC-backed views — see
 * ./UserManagement.tsx (backed by /api/users). Everything else is mock config. */

function Markets() {
  return (
    <SettingsSection icon={Globe} title="Markets" description="Regions & currencies">
      <ul className="grid gap-2 sm:grid-cols-2">
        {marketConfig.map((m) => (
          <li key={m.market} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 p-3">
            <div>
              <p className="text-sm font-medium text-ink">{m.market} · {m.currency}</p>
              <p className="text-xxs text-ink-faint">{m.cities.join(", ")}</p>
            </div>
            <StatusBadge tone={m.status.startsWith("Live") ? "success" : "info"}>{m.status}</StatusBadge>
          </li>
        ))}
      </ul>
    </SettingsSection>
  );
}

function Notifications() {
  return (
    <SettingsSection icon={Bell} title="Notification preferences" description="What you get pinged about">
      <ul className="divide-y divide-border">
        {[
          { label: "New approval requests", on: true },
          { label: "Ranking drops (SEO)", on: true },
          { label: "Urgent tickets & SLA breaches", on: true },
          { label: "Daily brief digest", on: false },
          { label: "Weekly executive summary", on: true },
        ].map((n) => (
          <li key={n.label} className="flex items-center justify-between gap-4 py-3">
            <span className="min-w-0 flex-1 text-sm font-medium text-ink">{n.label}</span>
            <Switch defaultOn={n.on} label={n.label} className="shrink-0" />
          </li>
        ))}
      </ul>
    </SettingsSection>
  );
}

function AgentGuardrails() {
  return (
    <div className="space-y-4">
      <ReviewModeBanner />
      <SettingsSection icon={Bot} title="Agent guardrails" description="Approval gates for autonomous agents">
        <ul className="divide-y divide-border">
          {[
            { label: "Require approval for every customer reply", on: true },
            { label: "Require approval for refunds & discounts", on: true },
            { label: "Require approval before publishing SEO pages", on: true },
            { label: "Require approval before posting to social", on: true },
            { label: "Allow agents to auto-assign facilities", on: false },
          ].map((n) => (
            <li key={n.label} className="flex items-center justify-between gap-4 py-3">
              <span className="min-w-0 flex-1 text-sm font-medium text-ink">{n.label}</span>
              <Switch defaultOn={n.on} label={n.label} className="shrink-0" />
            </li>
          ))}
        </ul>
      </SettingsSection>
    </div>
  );
}

function ConnectedApps() {
  return (
    <div className="space-y-4">
      <ReviewModeBanner />
      <Panel>
        <PanelHeader title="Connected apps" subtitle="Connected apps and integrations" action={<span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose/10 text-rose"><Plug className="h-4 w-4" /></span>} />
        <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {connectedApps.map((a) => <ConnectedAppRow key={a.name} app={a} />)}
        </div>
      </Panel>
    </div>
  );
}

function Theme() {
  return (
    <SettingsSection icon={Palette} title="Theme & appearance" description="Light and dark mode">
      <div className="flex items-center justify-between rounded-xl border border-border bg-surface-2 p-3">
        <div>
          <p className="text-sm font-medium text-ink">Dark mode</p>
          <p className="text-xs text-ink-muted">Toggle the command center theme</p>
        </div>
        <ThemeToggle />
      </div>
    </SettingsSection>
  );
}

/* --------------------------------- Router ----------------------------------- */

/** Renders one Settings subsection by slug (see lib/dashboard/sections.ts). */
export function SettingsSubsection({ slug }: { slug: string }) {
  switch (slug) {
    case "profile-team": return <ProfileTeamPanel />;
    case "roles-permissions": return <RolesPermissionsPanel />;
    case "markets": return <Markets />;
    case "notifications": return <Notifications />;
    case "agent-guardrails": return <AgentGuardrails />;
    case "connected-apps": return <ConnectedApps />;
    case "theme": return <Theme />;
    default: return <ProfileTeamPanel />;
  }
}
