import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { JsonViewer } from "@/components/ui/json-viewer";
import { formatDateTime, titleCase } from "@/lib/formatters";
import type { OrderEvent } from "@/lib/types";

export function OrderTimeline({ events }: { events: OrderEvent[] }) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-sm font-semibold text-ink">Order events</h2>
      </CardHeader>
      <CardBody>
        {events.length === 0 ? (
          <EmptyState title="No events recorded" />
        ) : (
          <ol className="space-y-4">
            {events.map((event, idx) => (
              <li key={event.id} className="relative flex gap-3">
                <div className="flex flex-col items-center">
                  <span className="h-2 w-2 rounded-full bg-brand" />
                  {idx < events.length - 1 && <span className="mt-1 w-px flex-1 bg-border" />}
                </div>
                <div className="flex-1 pb-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-medium text-ink">{titleCase(event.event_type)}</p>
                    <p className="text-xs text-ink-faint">{formatDateTime(event.created_at)}</p>
                  </div>
                  <p className="text-xs text-ink-muted">
                    {event.from_status && event.to_status && event.from_status !== event.to_status
                      ? `${titleCase(event.from_status)} → ${titleCase(event.to_status)} `
                      : ""}
                    by {event.actor_type}
                    {event.actor_id ? ` (${event.actor_id})` : ""}
                  </p>
                  <JsonViewer data={event.metadata_json} label="Details" />
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardBody>
    </Card>
  );
}
