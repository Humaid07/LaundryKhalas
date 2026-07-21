import Link from "next/link";
import { DataTable, type Column } from "@/components/ui/data-table";
import { JsonViewer } from "@/components/ui/json-viewer";
import { formatDateTime, shortId } from "@/lib/formatters";
import type { AIActionLog } from "@/lib/types";

export function AIActionLogTable({ logs }: { logs: AIActionLog[] }) {
  const columns: Column<AIActionLog>[] = [
    { header: "Time", cell: (l) => formatDateTime(l.created_at) },
    { header: "Agent", cell: (l) => l.agent_name },
    { header: "Action", cell: (l) => l.action_type },
    { header: "Tool", cell: (l) => l.tool_name ?? "-" },
    {
      header: "Conversation",
      cell: (l) =>
        l.conversation_id ? (
          <Link href={`/admin/conversations/${l.conversation_id}`} className="text-brand hover:text-brand-hover">
            {shortId(l.conversation_id)}
          </Link>
        ) : (
          "-"
        ),
    },
    {
      header: "Order",
      cell: (l) =>
        l.order_id ? (
          <Link href={`/admin/orders/${l.order_id}`} className="text-brand hover:text-brand-hover">
            {shortId(l.order_id)}
          </Link>
        ) : (
          "-"
        ),
    },
    {
      header: "Result",
      cell: (l) => (
        <span className={l.success ? "font-medium text-success" : "font-medium text-danger"}>
          {l.success ? "Success" : "Failed"}
        </span>
      ),
    },
    { header: "Latency", cell: (l) => (l.latency_ms !== null ? `${l.latency_ms}ms` : "-") },
    {
      header: "Provider / model",
      cell: (l) => (l.provider ? `${l.provider} / ${l.model_name ?? "-"}` : "-"),
    },
    { header: "Cost", cell: (l) => `$${l.estimated_cost.toFixed(4)}` },
    {
      header: "Data",
      cell: (l) => (
        <div className="flex flex-col gap-1">
          <JsonViewer data={l.input_json} label="Input" />
          <JsonViewer data={l.output_json} label="Output" />
          {l.error_message && <span className="text-xs text-danger">{l.error_message}</span>}
        </div>
      ),
    },
  ];

  return <DataTable columns={columns} rows={logs} rowKey={(l) => l.id} />;
}
