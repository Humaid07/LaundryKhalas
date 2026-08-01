"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Eye, EyeOff, Landmark, Loader2, Lock } from "lucide-react";
import { SectionCard } from "@/components/shared/SectionCard";
import { Button } from "@/components/ui/Button";
import { LoadingState, ErrorState } from "@/components/ui/states";
import { useAuth } from "@/lib/auth-context";
import { canManageFacility } from "@/lib/roles";
import { facilityApi, type BankDetailsInput, type BankDetailsMasked } from "@/lib/api-client";

const inputCls =
  "h-11 w-full rounded-lg border border-border bg-canvas px-3 text-sm text-ink placeholder:text-ink-faint focus:border-rose focus-visible:outline-none";
const labelCls = "mb-1 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint";

const EMPTY: BankDetailsInput = {
  account_holder_name: "", bank_name: "", iban: "", account_number: "",
  swift_bic: "", branch_name: "", bank_country: "AE", currency: "AED",
};

export function BankDetailsSection() {
  const { role } = useAuth();
  const canManage = canManageFacility(role);
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: ["facility", "bank-details"],
    queryFn: () => facilityApi.getBankDetails(),
  });

  const [editing, setEditing] = useState(false);

  if (q.isLoading) return <LoadingState label="Loading bank details…" />;
  if (q.isError) {
    return <ErrorState description={(q.error as Error)?.message} onRetry={() => q.refetch()} />;
  }

  const details = q.data ?? null;
  const hasDetails = Boolean(details?.has_iban || details?.account_holder_name);

  if (editing) {
    return (
      <BankDetailsForm
        current={details}
        onCancel={() => setEditing(false)}
        onSaved={() => { setEditing(false); qc.invalidateQueries({ queryKey: ["facility", "bank-details"] }); }}
      />
    );
  }

  return (
    <SectionCard
      title="Bank details"
      icon={Landmark}
      action={canManage ? (
        <Button variant="ghost" onClick={() => setEditing(true)}>
          {hasDetails ? "Edit" : "Add bank details"}
        </Button>
      ) : undefined}
    >
      <p className="mb-4 text-xs text-ink-muted">
        Payout banking for your facility. Sensitive numbers are encrypted and shown masked;
        only the account holder / manager can reveal the full IBAN, and every reveal is logged.
      </p>

      {!hasDetails ? (
        <p className="rounded-lg border border-dashed border-border bg-canvas px-4 py-6 text-center text-sm text-ink-muted">
          No bank details on file yet.{canManage ? " Add them so LaundryKhalas can pay out to your facility." : ""}
        </p>
      ) : (
        <BankDetailsView details={details!} canReveal={canManage} />
      )}
    </SectionCard>
  );
}

function BankDetailsView({ details, canReveal }: { details: BankDetailsMasked; canReveal: boolean }) {
  const [revealed, setRevealed] = useState<{ iban?: string | null; account_number?: string | null } | null>(null);
  const reveal = useMutation({
    mutationFn: () => facilityApi.revealBankDetails(),
    onSuccess: (r) => setRevealed({ iban: r.iban, account_number: r.account_number }),
  });

  return (
    <div className="space-y-4">
      <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
        <Field label="Account holder" value={details.account_holder_name} />
        <Field label="Bank" value={details.bank_name} />
        <Field
          label="IBAN"
          value={revealed?.iban ?? details.iban_masked}
          mono
        />
        <Field
          label="Account number"
          value={revealed?.account_number ?? details.account_number_masked}
          mono
        />
        <Field label="SWIFT / BIC" value={details.swift_bic} mono />
        <Field label="Branch" value={details.branch_name} />
        <Field label="Bank country" value={details.bank_country} />
        <Field label="Currency" value={details.currency} />
      </dl>

      <div className="flex flex-wrap items-center gap-3">
        {canReveal && details.has_iban && (
          revealed ? (
            <Button variant="ghost" onClick={() => setRevealed(null)}>
              <EyeOff className="h-4 w-4" /> Hide full details
            </Button>
          ) : (
            <Button variant="ghost" onClick={() => reveal.mutate()} disabled={reveal.isPending}>
              {reveal.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
              Reveal full details
            </Button>
          )
        )}
        {!canReveal && (
          <span className="inline-flex items-center gap-1.5 text-xxs text-ink-faint">
            <Lock className="h-3 w-3" /> Only the account owner or manager can reveal full banking.
          </span>
        )}
        {details.updated_at && (
          <span className="text-xxs text-ink-faint">
            Last updated {new Date(details.updated_at).toLocaleDateString()}
          </span>
        )}
      </div>
      {reveal.isError && (
        <p className="text-xs font-medium text-danger">{(reveal.error as Error).message}</p>
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value?: string | null; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xxs font-medium uppercase tracking-eyebrow text-ink-faint">{label}</dt>
      <dd className={`mt-1 break-words text-sm font-medium text-ink ${mono ? "font-mono tracking-wide" : ""}`}>
        {value || "—"}
      </dd>
    </div>
  );
}

function BankDetailsForm({
  current, onCancel, onSaved,
}: {
  current: BankDetailsMasked | null;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState<BankDetailsInput>(() => ({
    ...EMPTY,
    account_holder_name: current?.account_holder_name ?? "",
    bank_name: current?.bank_name ?? "",
    swift_bic: current?.swift_bic ?? "",
    branch_name: current?.branch_name ?? "",
    bank_country: current?.bank_country ?? "AE",
    currency: current?.currency ?? "AED",
    // IBAN / account number are never prefilled (masked-only); leave blank to
    // keep the stored value, or type a new one to replace it.
    iban: "",
    account_number: "",
  }));
  const [saved, setSaved] = useState(false);
  const [clientErr, setClientErr] = useState<string | null>(null);
  const set = (k: keyof BankDetailsInput, v: string) => setForm((s) => ({ ...s, [k]: v }));
  const hasIban = Boolean(current?.has_iban);

  const mutation = useMutation({
    mutationFn: (payload: BankDetailsInput) => facilityApi.updateBankDetails(payload),
    onSuccess: () => { setSaved(true); setTimeout(onSaved, 600); },
  });

  useEffect(() => { setClientErr(null); }, [form]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.account_holder_name?.trim()) { setClientErr("Account holder name is required."); return; }
    if (!hasIban && !form.iban?.trim()) { setClientErr("IBAN is required."); return; }
    // Only send changed sensitive fields; blank IBAN/account = keep existing.
    const payload: BankDetailsInput = {
      account_holder_name: form.account_holder_name?.trim() || null,
      bank_name: form.bank_name?.trim() || null,
      swift_bic: form.swift_bic?.trim() || null,
      branch_name: form.branch_name?.trim() || null,
      bank_country: form.bank_country || "AE",
      currency: form.currency || "AED",
    };
    if (form.iban?.trim()) payload.iban = form.iban.trim();
    if (form.account_number?.trim()) payload.account_number = form.account_number.trim();
    mutation.mutate(payload);
  }

  const err = clientErr ?? (mutation.isError ? (mutation.error as Error).message : null);

  return (
    <SectionCard title="Bank details" icon={Landmark}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className={labelCls}>Account holder name <span className="text-rose">*</span></label>
            <input className={inputCls} value={form.account_holder_name ?? ""} onChange={(e) => set("account_holder_name", e.target.value)} required />
          </div>
          <div><label className={labelCls}>Bank name</label><input className={inputCls} value={form.bank_name ?? ""} onChange={(e) => set("bank_name", e.target.value)} /></div>
          <div><label className={labelCls}>Branch</label><input className={inputCls} value={form.branch_name ?? ""} onChange={(e) => set("branch_name", e.target.value)} /></div>
          <div className="sm:col-span-2">
            <label className={labelCls}>
              IBAN {!hasIban && <span className="text-rose">*</span>}
              {hasIban && <span className="ml-1 font-normal normal-case tracking-normal text-ink-faint">(leave blank to keep {current?.iban_masked})</span>}
            </label>
            <input className={`${inputCls} font-mono`} value={form.iban ?? ""} onChange={(e) => set("iban", e.target.value)} placeholder="AE07 0331 2345 6789 0123 456" autoComplete="off" />
          </div>
          <div className="sm:col-span-2">
            <label className={labelCls}>
              Account number
              {current?.has_account_number && <span className="ml-1 font-normal normal-case tracking-normal text-ink-faint">(leave blank to keep {current?.account_number_masked})</span>}
            </label>
            <input className={`${inputCls} font-mono`} value={form.account_number ?? ""} onChange={(e) => set("account_number", e.target.value)} placeholder="Optional" autoComplete="off" />
          </div>
          <div><label className={labelCls}>SWIFT / BIC</label><input className={`${inputCls} font-mono`} value={form.swift_bic ?? ""} onChange={(e) => set("swift_bic", e.target.value)} /></div>
          <div className="grid grid-cols-2 gap-2">
            <div><label className={labelCls}>Country</label><input className={inputCls} value={form.bank_country ?? ""} onChange={(e) => set("bank_country", e.target.value.toUpperCase())} maxLength={3} /></div>
            <div><label className={labelCls}>Currency</label><input className={inputCls} value={form.currency ?? ""} onChange={(e) => set("currency", e.target.value.toUpperCase())} maxLength={3} /></div>
          </div>
        </div>

        {err && <p className="text-xs font-medium text-danger">{err}</p>}

        <div className="flex items-center gap-2">
          <Button type="submit" variant="primary" size="lg" disabled={mutation.isPending}>
            {mutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            {saved && <Check className="h-4 w-4" />}
            Save bank details
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel} disabled={mutation.isPending}>Cancel</Button>
        </div>
        <p className="flex items-center gap-1.5 text-xxs text-ink-faint">
          <Lock className="h-3 w-3" /> IBAN and account number are encrypted at rest and never shown in full unless you reveal them.
        </p>
      </form>
    </SectionCard>
  );
}
