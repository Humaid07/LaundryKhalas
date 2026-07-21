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
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  description: string;
  /** Optional live count badge shown in the sidebar. */
  badge?: number;
};

/** Primary sidebar sections — the ten command-center domains. */
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
  },
  {
    label: "Sales",
    href: "/sales",
    icon: TrendingUp,
    description: "Revenue, growth and customer performance",
  },
  {
    label: "Partner Acquisition",
    href: "/partner-acquisition",
    icon: Handshake,
    description: "Partner pipeline, market intelligence & onboarding",
    badge: 5,
  },
  {
    label: "SEO Agents",
    href: "/seo-agents",
    icon: Search,
    description: "Autonomous SEO agents, tasks and daily brief",
    badge: 3,
  },
  {
    label: "Marketing",
    href: "/marketing",
    icon: Megaphone,
    description: "Social analytics, creative studio and approvals",
    badge: 4,
  },
  {
    label: "Finance & Compliance",
    href: "/finance-compliance",
    icon: ShieldCheck,
    description: "Revenue, cost, profit plus compliance & risk oversight",
  },
  {
    label: "Dev & Automation",
    href: "/dev-automation",
    icon: TerminalSquare,
    description: "Agent health, automations, API & system status",
    badge: 3,
  },
  {
    label: "Reports",
    href: "/reports",
    icon: FileBarChart,
    description: "Scheduled briefs and executive reports",
  },
  {
    label: "Settings",
    href: "/settings",
    icon: Settings,
    description: "Team, markets, connected apps and preferences",
  },
];
