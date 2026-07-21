import { User, Users, Shield, Globe, Plug, Bot, Bell, Palette, ShieldCheck } from "lucide-react";
import { Panel, PanelHeader, StatusBadge } from "@/components/dashboard/ui/primitives";
import { Button } from "@/components/dashboard/ui/Button";
import { Switch } from "@/components/dashboard/ui/Switch";
import { ThemeToggle } from "@/components/dashboard/shell/ThemeToggle";
import { ConnectedAppRow } from "@/components/dashboard/widgets";
import { teamMembers, roles, connectedApps, marketConfig } from "@/lib/dashboard/mock-data";

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

function ProfileTeam() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <SettingsSection icon={User} title="Profile" description="Your account details">
        <div className="flex items-center gap-4">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-rose/12 font-display text-lg font-bold text-rose">NE</span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-ink">Nada El-Amin</p>
            <p className="text-xs text-ink-muted">n•••@laundrykhalas.com · Owner</p>
          </div>
          <Button variant="secondary" size="sm">Edit</Button>
        </div>
      </SettingsSection>
      <SettingsSection icon={Users} title="Team members" description={`${teamMembers.length} people`}>
        <ul className="divide-y divide-border">
          {teamMembers.map((m) => (
            <li key={m.email} className="flex items-center justify-between gap-3 py-2.5">
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose/12 text-xxs font-bold text-rose">{m.name.split(" ").map((n) => n[0]).join("").slice(0, 2)}</span>
                <div>
                  <p className="text-sm font-medium text-ink">{m.name}</p>
                  <p className="text-xxs text-ink-faint">{m.email} · {m.markets}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden text-xs text-ink-muted sm:block">{m.role}</span>
                <StatusBadge tone={m.status === "Active" ? "success" : "warning"} dot={false}>{m.status}</StatusBadge>
              </div>
            </li>
          ))}
        </ul>
        <Button variant="secondary" size="sm" className="mt-3">Invite member</Button>
      </SettingsSection>
    </div>
  );
}

function RolesPermissions() {
  return (
    <SettingsSection icon={Shield} title="Roles & permissions" description="Access levels">
      <ul className="space-y-2">
        {roles.map((r) => (
          <li key={r.role} className="rounded-xl border border-border bg-surface-2 p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-ink">{r.role}</p>
              <span className="text-xxs text-ink-faint">{r.members} member{r.members > 1 ? "s" : ""}</span>
            </div>
            <p className="mt-0.5 text-xs text-ink-muted">{r.permissions}</p>
          </li>
        ))}
      </ul>
    </SettingsSection>
  );
}

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
    case "profile-team": return <ProfileTeam />;
    case "roles-permissions": return <RolesPermissions />;
    case "markets": return <Markets />;
    case "notifications": return <Notifications />;
    case "agent-guardrails": return <AgentGuardrails />;
    case "connected-apps": return <ConnectedApps />;
    case "theme": return <Theme />;
    default: return <ProfileTeam />;
  }
}
