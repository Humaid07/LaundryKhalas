"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Plus } from "lucide-react";
import { facilityApi } from "@/lib/api-client";
import { formatRelativeTime } from "@/lib/formatters";
import { issueStatusTone, issueStatusLabel } from "@/lib/status";
import { MobilePageHeader } from "@/components/shared/MobilePageHeader";
import { WorkflowTabs } from "@/components/ui/Tabs";
import { CompactRecordCard, RecordList } from "@/components/minimal/CompactRecordCard";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/states";

const FILTERS = [
  { id: "", label: "All" },
  { id: "open", label: "Open" },
  { id: "in_progress", label: "In Progress" },
  { id: "resolved", label: "Resolved" },
];

export default function IssuesPage() {
  const [status, setStatus] = useState("");
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["facility", "issues", status],
    queryFn: () => facilityApi.issues(status ? { status } : {}),
  });

  const issues = data ?? [];

  return (
    <div className="lk-enter space-y-5">
      <MobilePageHeader
        title="Issues"
        description="Delays, damage and other concerns raised with operations."
        action={
          <Link href="/issues/new">
            <Button variant="primary" size="md">
              <Plus className="h-4 w-4" /> Report Issue
            </Button>
          </Link>
        }
      />

      <div className="sticky top-14 z-20 -mx-4 border-b border-border/60 bg-canvas/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
        <WorkflowTabs tabs={FILTERS} value={status} onChange={setStatus} />
      </div>

      {isLoading ? (
        <LoadingState label="Loading issues…" />
      ) : isError ? (
        <ErrorState description="Could not load issues." onRetry={() => refetch()} />
      ) : issues.length === 0 ? (
        <EmptyState icon={AlertCircle} title="No issues here" description="Nothing to report right now." />
      ) : (
        <RecordList>
          {issues.map((iss) => (
            <CompactRecordCard
              key={iss.id}
              id={iss.related_order_id ?? undefined}
              title={iss.title ?? iss.issue_type ?? "Issue"}
              status={{ label: issueStatusLabel(iss.status), tone: issueStatusTone(iss.status) }}
              fields={[
                { label: "Type", value: iss.issue_type ?? "—" },
                { label: "Priority", value: iss.priority ?? "—" },
                { label: "Raised", value: formatRelativeTime(iss.created_at) },
              ]}
              href={`/issues/${iss.id}`}
            />
          ))}
        </RecordList>
      )}
    </div>
  );
}
