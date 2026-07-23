import Link from "next/link";
import { PackageX } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import { getAgentBySlug } from "@/lib/dashboard/dev-automation-data";
import { AgentDetailPage } from "@/components/dashboard/dev-automation/agent-detail/AgentDetailPage";

/**
 * Dedicated full-page agent detail — a primary Dev & Automation record.
 * Server component: reads the agent slug + originating status tab from the route
 * so "back" returns to the exact agent-health view the operator came from.
 */
export default async function AgentDetailRoute({
  params,
  searchParams,
}: {
  params: Promise<{ agentId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { agentId: raw } = await params;
  const sp = await searchParams;
  const agentId = decodeURIComponent(raw);
  const tab = typeof sp.tab === "string" ? sp.tab : undefined;
  const backHref = tab ? `/dev-automation/agent-health?tab=${tab}` : "/dev-automation/agent-health";

  const agent = getAgentBySlug(agentId);

  if (!agent) {
    return (
      <div className="lk-enter flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface-2 text-ink-faint">
          <PackageX className="h-7 w-7" />
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold text-ink">Agent not found</h1>
          <p className="mt-1 text-sm text-ink-muted">No agent matches “{agentId}”.</p>
        </div>
        <Link href={backHref}><Button variant="primary" size="sm">Back to Agent health</Button></Link>
      </div>
    );
  }

  return <AgentDetailPage agent={agent} backHref={backHref} />;
}
