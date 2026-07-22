import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Workflow,
  TrendingUp,
  Handshake,
  Search,
  Megaphone,
  ShieldCheck,
  TerminalSquare,
  FileBarChart,
  Settings,
  ClipboardList,
} from "lucide-react";
import { subsectionsOf } from "./sections";

/** A child sub-tab shown nested under a top-level section in the sidebar. */
export type NavChild = {
  label: string;
  href: string;
  /** Subsection-specific count badge. */
  badge?: number;
};

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  description: string;
  /** Optional aggregated count badge shown on the parent section. */
  badge?: number;
  /** Nested sub-tabs rendered under the parent (each an existing route). */
  children?: NavChild[];
  /** Expand this section by default even when the route is elsewhere. */
  defaultOpen?: boolean;
  /** Reserved for future role-gating; unused today but part of the item shape. */
  allowedRoles?: string[];
};

/**
 * Build the nested children for a section straight from `sections.ts` (the
 * single source of truth for subsections), so the sidebar tree never drifts
 * from the actual routes. Each child href is `${base}/${slug}` — every one of
 * these routes already exists under app/(dashboard)/.
 */
function childrenOf(sectionKey: string, base: string): NavChild[] {
  return subsectionsOf(sectionKey).map((s) => ({
    label: s.label,
    href: `${base}/${s.slug}`,
    badge: s.badge,
  }));
}

/**
 * Primary sidebar sections — the ten command-center domains. Every domain
 * (except the single-page Overview) carries its subsections as `children`, so
 * operators reach a working page directly from the sidebar instead of opening a
 * landing page and choosing from cards.
 */
export const NAV_ITEMS: NavItem[] = [
  {
    label: "Overview",
    href: "/overview",
    icon: LayoutDashboard,
    description: "Live operations snapshot across every market",
  },
  {
    label: "Operations",
    href: "/operations",
    icon: Workflow,
    description: "WhatsApp agent, orders, tickets & driver assignment",
    badge: 6,
    children: childrenOf("operations", "/operations"),
  },
  {
    label: "Orders",
    href: "/orders",
    icon: ClipboardList,
    description: "Live WhatsApp orders — cards, details & operational status",
  },
  {
    label: "Sales",
    href: "/sales",
    icon: TrendingUp,
    description: "Revenue, growth and customer performance",
    children: childrenOf("sales", "/sales"),
  },
  {
    label: "Partner Acquisition",
    href: "/partner-acquisition",
    icon: Handshake,
    description: "Partner pipeline, market intelligence & onboarding",
    badge: 5,
    children: childrenOf("partner-acquisition", "/partner-acquisition"),
  },
  {
    label: "SEO Agents",
    href: "/seo-agents",
    icon: Search,
    description: "Autonomous SEO agents, tasks and daily brief",
    badge: 3,
    children: childrenOf("seo-agents", "/seo-agents"),
  },
  {
    label: "Marketing",
    href: "/marketing",
    icon: Megaphone,
    description: "Social analytics, creative studio and approvals",
    badge: 4,
    children: childrenOf("marketing", "/marketing"),
  },
  {
    label: "Finance & Compliance",
    href: "/finance-compliance",
    icon: ShieldCheck,
    description: "Revenue, cost, profit plus compliance & risk oversight",
    children: childrenOf("finance-compliance", "/finance-compliance"),
  },
  {
    label: "Dev & Automation",
    href: "/dev-automation",
    icon: TerminalSquare,
    description: "Agent health, automations, API & system status",
    badge: 3,
    children: childrenOf("dev-automation", "/dev-automation"),
  },
  {
    label: "Reports",
    href: "/reports",
    icon: FileBarChart,
    description: "Scheduled briefs and executive reports",
    children: childrenOf("reports", "/reports"),
  },
  {
    label: "Settings",
    href: "/settings",
    icon: Settings,
    description: "Team, markets, connected apps and preferences",
    children: childrenOf("settings", "/settings"),
  },
];
