"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  ClipboardCheck,
  ShoppingBag,
  ScrollText,
  Send,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS: { href: string; label: string; icon: LucideIcon; exact?: boolean }[] = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/admin/conversations", label: "Conversations", icon: MessageSquare },
  { href: "/admin/approvals", label: "Approvals", icon: ClipboardCheck },
  { href: "/admin/orders", label: "Orders", icon: ShoppingBag },
  { href: "/admin/ai-logs", label: "AI Action Logs", icon: ScrollText },
  { href: "/admin/mock-whatsapp", label: "WhatsApp Console", icon: Send },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed bottom-0 left-0 top-0 z-40 hidden w-60 flex-col border-r border-border bg-surface md:flex">
      <div className="flex items-center gap-2.5 border-b border-border px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose text-sm font-bold text-rose-contrast">
          LK
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight text-ink">LaundryKhalas</p>
          <p className="text-[10px] font-medium text-ink-muted">WhatsApp Agent Ops</p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
          const isActive = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition-colors duration-150",
                isActive
                  ? "bg-surface-sunken font-semibold text-ink"
                  : "text-ink-faint hover:bg-surface-2 hover:text-ink"
              )}
            >
              <Icon size={16} strokeWidth={isActive ? 2.25 : 1.75} />
              <span className="flex-1 truncate">{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border px-4 py-4">
        <p className="text-[10px] leading-relaxed text-ink-muted">
          Internal operations console for the WhatsApp Agent.
        </p>
      </div>
    </aside>
  );
}
