import Link from "next/link";
import { Bot } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getSeoAgentBySlug } from "@/lib/dashboard/seo-data";
import { AgentDetailPage } from "@/components/dashboard/seo/agent-detail/AgentDetailPage";

/**
 * Dedicated full-page SEO agent detail. Server component: resolves the agent by
 * its url-safe slug and renders the detail page (the only place agent actions
 * live). "Back" returns to the agent fleet.
 */
export default async function SeoAgentDetailRoute({
  params,
}: {
  params: Promise<{ agentId: string }>;
}) {
  const { agentId: raw } = await params;
  const slug = decodeURIComponent(raw);
  const backHref = "/seo-agents/agent-fleet";
  const agent = getSeoAgentBySlug(slug);

  if (!agent) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <Bot className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Agent not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No SEO agent matches “{slug}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Agent fleet</Button></Link>
      </div>
    );
  }

  return <AgentDetailPage agent={agent} backHref={backHref} />;
}
