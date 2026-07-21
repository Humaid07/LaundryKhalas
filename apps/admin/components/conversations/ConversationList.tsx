import Link from "next/link";
import { DataTable, type Column } from "@/components/ui/data-table";
import { StatusBadge, BooleanBadge } from "@/components/ui/status-badge";
import { truncate, formatRelativeTime, shortId } from "@/lib/formatters";
import type { Conversation } from "@/lib/types";

export interface ConversationRow extends Conversation {
  marketCode: string;
  latestMessagePreview: string | null;
  hasPendingApproval: boolean;
}

export function ConversationList({ rows }: { rows: ConversationRow[] }) {
  const columns: Column<ConversationRow>[] = [
    {
      header: "Conversation",
      cell: (row) => (
        <Link href={`/admin/conversations/${row.id}`} className="font-medium text-brand hover:text-brand-hover">
          {shortId(row.id)}
        </Link>
      ),
    },
    {
      header: "Latest message",
      cell: (row) => (
        <span className="text-ink-muted">
          {row.latestMessagePreview ? truncate(row.latestMessagePreview, 60) : "No messages yet"}
        </span>
      ),
      className: "max-w-xs",
    },
    { header: "Market", cell: (row) => row.marketCode },
    { header: "Channel", cell: (row) => <span className="capitalize">{row.channel}</span> },
    { header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
    {
      header: "Flags",
      cell: (row) => (
        <div className="flex gap-1.5">
          {row.manual_takeover && <BooleanBadge value trueLabel="Manual takeover" />}
          {row.hasPendingApproval && <BooleanBadge value trueLabel="Pending approval" trueTone="info" />}
        </div>
      ),
    },
    { header: "Updated", cell: (row) => formatRelativeTime(row.updated_at) },
  ];

  return <DataTable columns={columns} rows={rows} rowKey={(row) => row.id} />;
}
