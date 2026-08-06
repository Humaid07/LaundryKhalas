"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Paperclip, AlertTriangle } from "lucide-react";
import {
  facilityApi,
  type FacilityViewItem,
  type IssueTypeOption,
} from "@/lib/api-client";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/primitives";

/**
 * RaiseIssueForm — the redesigned Raise-an-Issue flow: pick a canonical issue
 * type (backend registry), optionally target a specific item, explain, and attach
 * photos. Photos upload to the `issue_photo` stage (source FACILITY_ISSUE, linked
 * to the item) first, then the issue is created with their ids.
 */
export function RaiseIssueForm({
  orderId,
  items,
  onCancel,
  onDone,
}: {
  orderId: string;
  items: FacilityViewItem[];
  onCancel: () => void;
  onDone: () => void;
}) {
  const qc = useQueryClient();
  const [issueType, setIssueType] = useState("");
  const [itemId, setItemId] = useState("");
  const [message, setMessage] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { data: types = [], isLoading: typesLoading } = useQuery({
    queryKey: ["facility", "issue-types"],
    queryFn: () => facilityApi.issueTypes(),
    staleTime: 5 * 60 * 1000,
  });

  const selected: IssueTypeOption | undefined = useMemo(
    () => types.find((t) => t.key === issueType),
    [types, issueType],
  );

  const submit = useMutation({
    mutationFn: async () => {
      let photoIds: string[] = [];
      if (files.length > 0) {
        const uploaded = await facilityApi.uploadOrderPhotos(orderId, "issue_photo", files, {
          orderItemId: itemId || undefined,
          source: "FACILITY_ISSUE",
        });
        photoIds = (uploaded.photos ?? []).map((p) => p.id);
      }
      return facilityApi.raiseOrderIssue(orderId, {
        issue_type: issueType,
        message: message.trim(),
        order_item_id: itemId || null,
        photo_ids: photoIds,
      });
    },
    onSuccess: () => {
      setError(null);
      qc.invalidateQueries({ queryKey: ["facility", "order", orderId] });
      qc.invalidateQueries({ queryKey: ["facility", "issues"] });
      onDone();
    },
    onError: (e: unknown) => setError(e instanceof Error ? e.message : "Could not raise the issue."),
  });

  const canSubmit = !!issueType && !!message.trim() && !submit.isPending;

  return (
    <div className="space-y-2.5">
      <div>
        <label className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">Issue type</label>
        <select
          value={issueType}
          onChange={(e) => setIssueType(e.target.value)}
          disabled={typesLoading}
          className="mt-1 h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
        >
          <option value="" disabled>
            {typesLoading ? "Loading…" : "Select an issue type…"}
          </option>
          {types.map((t) => (
            <option key={t.key} value={t.key}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {selected && (selected.requires_photo || selected.requires_customer_response || selected.requires_price_revision || selected.blocking) && (
        <div className="flex flex-wrap gap-1.5">
          {selected.requires_photo && <StatusBadge tone="info" dot={false}>Photo needed</StatusBadge>}
          {selected.requires_customer_response && <StatusBadge tone="warning" dot={false}>Needs customer</StatusBadge>}
          {selected.requires_price_revision && <StatusBadge tone="warning" dot={false}>Price revision</StatusBadge>}
          {selected.blocking && <StatusBadge tone="danger" dot={false}>Pauses order</StatusBadge>}
        </div>
      )}

      {items.length > 0 && (
        <div>
          <label className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">Affected item (optional)</label>
          <select
            value={itemId}
            onChange={(e) => setItemId(e.target.value)}
            className="mt-1 h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink focus:border-rose focus-visible:outline-none"
          >
            <option value="">Whole order</option>
            {items.map((it) => (
              <option key={it.id} value={it.id}>
                {it.name}
              </option>
            ))}
          </select>
        </div>
      )}

      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={3}
        placeholder="Explain the issue for the operations team…"
        className="w-full rounded-lg border border-border bg-canvas px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none"
      />

      <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border px-3 py-2.5 text-sm text-ink-muted hover:border-border-strong">
        <Paperclip className="h-4 w-4" />
        {files.length > 0 ? `${files.length} photo${files.length === 1 ? "" : "s"} attached` : "Attach photos (optional)"}
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          className="hidden"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        />
      </label>

      {selected?.requires_photo && files.length === 0 && (
        <p className="flex items-center gap-1 text-xxs text-warning">
          <AlertTriangle className="h-3 w-3" /> This issue type usually needs a photo.
        </p>
      )}
      {error && <p className="text-xxs font-medium text-danger">{error}</p>}

      <div className="flex gap-2">
        <Button variant="primary" size="md" className="flex-1" disabled={!canSubmit} onClick={() => submit.mutate()}>
          {submit.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Submit issue
        </Button>
        <Button variant="ghost" size="md" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
