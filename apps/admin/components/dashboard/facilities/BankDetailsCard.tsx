"use client";

import { useCallback, useEffect, useState } from "react";
import { Landmark, Loader2, Eye, EyeOff, Lock } from "lucide-react";
import { DetailSectionCard, Field, FieldGrid } from "@/components/dashboard/minimal/DetailSectionCard";
import { Button } from "@/components/dashboard/ui/Button";
import {
  getFacilityBankDetails, updateFacilityBankDetails, revealFacilityBankDetails,
  FacilitiesApiError,
  type BankDetailsMasked, type BankDetailsInput,
} from "@/lib/dashboard/facilities-api";

const inputCls = "h-9 w-full rounded-md border border-border bg-canvas px-2 text-xs text-ink focus:border-rose focus-visible:outline-none";
const labelCls = "mb-1 block text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint";

export function BankDetailsCard({ facilityId }: { facilityId: string }) {
  const [details, setDetails] = useState<BankDetailsMasked | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [revealed, setRevealed] = useState<{ iban?: string | null; account_number?: string | null } | null>(null);
  const [adminOnly, setAdminOnly] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setDetails(await getFacilityBankDetails(facilityId)); }
    catch { setDetails(null); }
    finally { setLoading(false); }
  }, [facilityId]);

  useEffect(() => { load(); }, [load]);

  async function reveal() {
    setBusy(true); setErr(null);
    try {
      const r = await revealFacilityBankDetails(facilityId);
      setRevealed({ iban: r.iban, account_number: r.account_number });
    } catch (e) {
      if (e instanceof FacilitiesApiError && e.status === 403) setAdminOnly(true);
      else setErr(e instanceof Error ? e.message : "Could not reveal details.");
    } finally { setBusy(false); }
  }

  const has = Boolean(details?.has_iban || details?.account_holder_name);

  return (
    <DetailSectionCard title="Bank details" icon={Landmark}
      action={!editing ? (
        <Button variant="secondary" size="sm" onClick={() => { setEditing(true); setRevealed(null); }}>
          {has ? "Edit" : "Add"}
        </Button>
      ) : undefined}>
      <p className="mb-3 text-xxs text-ink-faint">
        Payout banking. IBAN &amp; account number are encrypted; editing and revealing full values are administrator-only and audited.
      </p>

      {loading ? (
        <p className="text-xs text-ink-muted">Loading…</p>
      ) : editing ? (
        <BankForm facilityId={facilityId} current={details} onCancel={() => setEditing(false)}
          onSaved={() => { setEditing(false); load(); }}
          onForbidden={() => { setEditing(false); setAdminOnly(true); }} />
      ) : !has ? (
        <p className="text-xs text-ink-muted">No bank details on file.</p>
      ) : (
        <>
          <FieldGrid cols={2}>
            <Field label="Account holder" value={details!.account_holder_name} />
            <Field label="Bank" value={details!.bank_name} />
            <Field label="IBAN" value={revealed?.iban ?? details!.iban_masked} mono />
            <Field label="Account number" value={revealed?.account_number ?? details!.account_number_masked} mono />
            <Field label="SWIFT / BIC" value={details!.swift_bic} mono />
            <Field label="Branch" value={details!.branch_name} />
            <Field label="Country" value={details!.bank_country} />
            <Field label="Currency" value={details!.currency} />
          </FieldGrid>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {adminOnly ? (
              <span className="inline-flex items-center gap-1.5 text-xxs text-ink-faint">
                <Lock className="h-3 w-3" /> Revealing full banking is administrator-only.
              </span>
            ) : details!.has_iban && (
              revealed ? (
                <Button variant="ghost" size="sm" onClick={() => setRevealed(null)}><EyeOff className="h-3.5 w-3.5" /> Hide</Button>
              ) : (
                <Button variant="ghost" size="sm" onClick={reveal} disabled={busy}>
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Eye className="h-3.5 w-3.5" />} Reveal full details
                </Button>
              )
            )}
            {details!.updated_at && (
              <span className="text-xxs text-ink-faint">Updated {new Date(details!.updated_at).toLocaleDateString()}</span>
            )}
          </div>
          {err && <p className="mt-2 text-xs text-danger">{err}</p>}
        </>
      )}
    </DetailSectionCard>
  );
}

function BankForm({
  facilityId, current, onCancel, onSaved, onForbidden,
}: {
  facilityId: string;
  current: BankDetailsMasked | null;
  onCancel: () => void;
  onSaved: () => void;
  onForbidden: () => void;
}) {
  const [form, setForm] = useState<BankDetailsInput>({
    account_holder_name: current?.account_holder_name ?? "",
    bank_name: current?.bank_name ?? "",
    swift_bic: current?.swift_bic ?? "",
    branch_name: current?.branch_name ?? "",
    bank_country: current?.bank_country ?? "AE",
    currency: current?.currency ?? "AED",
    iban: "", account_number: "",
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof BankDetailsInput, v: string) => setForm((s) => ({ ...s, [k]: v }));
  const hasIban = Boolean(current?.has_iban);

  async function save() {
    if (!form.account_holder_name?.trim()) { setErr("Account holder name is required."); return; }
    if (!hasIban && !form.iban?.trim()) { setErr("IBAN is required."); return; }
    setBusy(true); setErr(null);
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
    try {
      await updateFacilityBankDetails(facilityId, payload);
      onSaved();
    } catch (e) {
      if (e instanceof FacilitiesApiError && e.status === 403) { onForbidden(); return; }
      setErr(e instanceof Error ? e.message : "Could not save.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><label className={labelCls}>Account holder *</label><input className={inputCls} value={form.account_holder_name ?? ""} onChange={(e) => set("account_holder_name", e.target.value)} /></div>
        <div><label className={labelCls}>Bank</label><input className={inputCls} value={form.bank_name ?? ""} onChange={(e) => set("bank_name", e.target.value)} /></div>
        <div><label className={labelCls}>Branch</label><input className={inputCls} value={form.branch_name ?? ""} onChange={(e) => set("branch_name", e.target.value)} /></div>
        <div className="sm:col-span-2">
          <label className={labelCls}>IBAN {!hasIban && "*"} {hasIban && <span className="font-normal normal-case tracking-normal text-ink-faint">(blank = keep {current?.iban_masked})</span>}</label>
          <input className={`${inputCls} font-mono`} value={form.iban ?? ""} onChange={(e) => set("iban", e.target.value)} placeholder="AE07 0331 2345 6789 0123 456" autoComplete="off" />
        </div>
        <div className="sm:col-span-2">
          <label className={labelCls}>Account number {current?.has_account_number && <span className="font-normal normal-case tracking-normal text-ink-faint">(blank = keep {current?.account_number_masked})</span>}</label>
          <input className={`${inputCls} font-mono`} value={form.account_number ?? ""} onChange={(e) => set("account_number", e.target.value)} autoComplete="off" />
        </div>
        <div><label className={labelCls}>SWIFT / BIC</label><input className={`${inputCls} font-mono`} value={form.swift_bic ?? ""} onChange={(e) => set("swift_bic", e.target.value)} /></div>
        <div className="grid grid-cols-2 gap-2">
          <div><label className={labelCls}>Country</label><input className={inputCls} value={form.bank_country ?? ""} maxLength={3} onChange={(e) => set("bank_country", e.target.value.toUpperCase())} /></div>
          <div><label className={labelCls}>Currency</label><input className={inputCls} value={form.currency ?? ""} maxLength={3} onChange={(e) => set("currency", e.target.value.toUpperCase())} /></div>
        </div>
      </div>
      {err && <p className="text-xs text-danger">{err}</p>}
      <div className="flex items-center gap-2">
        <Button variant="primary" size="sm" onClick={save} disabled={busy}>{busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Save</Button>
        <Button variant="secondary" size="sm" onClick={onCancel} disabled={busy}>Cancel</Button>
      </div>
    </div>
  );
}
