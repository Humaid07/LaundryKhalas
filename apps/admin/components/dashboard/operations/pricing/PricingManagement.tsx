"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Tag, Plus, Rocket, Undo2, X, Info, Pencil } from "lucide-react";
import { Button } from "@/components/dashboard/ui/Button";
import {
  MinimalKpiStrip, WorkflowTabs, DataPreviewTable, EmptyState, StatusBadge,
  type WorkflowTab,
} from "@/components/dashboard/minimal";
import * as api from "@/lib/dashboard/pricing-api";
import type { PricingItem, PricingVersion, Promotion, HistoryEntry, SyncStatus } from "@/lib/dashboard/pricing-api";

const money = (v: number | null | undefined, cur = "AED") =>
  v === null || v === undefined ? "—" : `${cur} ${Number.isInteger(v) ? v : v.toFixed(2)}`;
const dt = (s?: string | null) => (s ? new Date(s).toLocaleString("en-AE", { dateStyle: "medium", timeStyle: "short" }) : "—");

type TabId = "current" | "drafts" | "promotions" | "history" | "sync";
const TABS: { id: TabId; label: string }[] = [
  { id: "current", label: "Current Prices" },
  { id: "drafts", label: "Drafts" },
  { id: "promotions", label: "Promotions" },
  { id: "history", label: "History" },
  { id: "sync", label: "Sync" },
];

function Notice({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warning" }) {
  const c = tone === "warning" ? "border-warning/25 bg-warning/[0.06]" : "border-info/20 bg-info/[0.06]";
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border ${c} px-3.5 py-3`}>
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
      <div className="text-xs leading-relaxed text-ink-muted">{children}</div>
    </div>
  );
}

function Modal({ title, onClose, children, footer }: { title: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-full max-w-lg overflow-hidden rounded-2xl border border-border bg-surface shadow-pop">
        <header className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="font-display text-[0.95rem] font-semibold text-ink">{title}</h2>
          <button onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted hover:bg-surface-2 hover:text-ink"><X className="h-4 w-4" /></button>
        </header>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-border bg-surface-2/40 px-5 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

const input = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-rose/40";

export function PricingManagement() {
  const [tab, setTab] = useState<TabId>("current");
  const [perms, setPerms] = useState<string[]>([]);
  const [items, setItems] = useState<PricingItem[]>([]);
  const [version, setVersion] = useState<number | null>(null);
  const [versions, setVersions] = useState<PricingVersion[]>([]);
  const [promos, setPromos] = useState<Promotion[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [cat, setCat] = useState("");
  const [editItem, setEditItem] = useState<PricingItem | null>(null);
  const [publishV, setPublishV] = useState<PricingVersion | null>(null);
  const [newPromo, setNewPromo] = useState(false);

  const can = (p: string) => perms.includes(p);
  const draft = versions.find((v) => v.status === "draft");

  const reload = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const [pm, cur, vs, pr, hi, sy] = await Promise.all([
        api.getMyPricingPermissions(), api.getCurrentItems(), api.getVersions(),
        api.getPromotions(), api.getHistory(), api.getSyncStatus(),
      ]);
      setPerms(pm.permissions); setItems(cur.items); setVersion(cur.catalogue_version);
      setVersions(vs.versions); setPromos(pr.promotions); setHistory(hi.history); setSync(sy);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load pricing.");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const categories = useMemo(
    () => Array.from(new Map(items.map((i) => [i.category_code, i.category_name])).entries())
      .filter(([c]) => c) as [string, string][],
    [items]);
  const filtered = items.filter((i) =>
    (!cat || i.category_code === cat) &&
    (!search || `${i.canonical_name} ${i.item_code}`.toLowerCase().includes(search.toLowerCase())));

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key); setErr(null);
    try { await fn(); await reload(); } catch (e) { setErr(e instanceof Error ? e.message : "Action failed."); }
    finally { setBusy(null); }
  };

  const ensureDraftThenEdit = async (it: PricingItem) => {
    if (!draft) {
      await run("draft", async () => { await api.createDraft("Price update"); });
    }
    setEditItem(it);
  };

  const kpis = [
    { label: "Published version", value: version ? `v${version}` : "—" },
    { label: "Open drafts", value: String(versions.filter((v) => v.status === "draft" || v.status === "pending_review").length), tone: draft ? "warning" as const : undefined },
    { label: "Active promotions", value: String(promos.filter((p) => p.active).length) },
    { label: "Catalogue items", value: String(items.length) },
  ];

  const websiteSync = sync?.sync.find((s) => s.target === "website");

  if (loading) return <div className="flex items-center gap-2 py-10 text-sm text-ink-muted"><Loader2 className="h-4 w-4 animate-spin text-rose" />Loading pricing…</div>;

  return (
    <div className="space-y-6">
      {/* Published-catalogue header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/70 bg-surface px-5 py-4 shadow-card">
        <div>
          <p className="text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Published catalogue</p>
          <p className="mt-1 font-display text-lg font-semibold text-ink">Version {version ?? "—"}</p>
          <p className="mt-0.5 text-xs text-ink-muted">
            Published {dt(sync?.published_at)} · Website sync:{" "}
            <StatusBadge tone={websiteSync?.status === "success" ? "success" : websiteSync?.status === "failed" ? "danger" : "warning"} dot={false}>
              {websiteSync?.status ?? "—"}
            </StatusBadge>{" "}
            · WhatsApp cache: <StatusBadge tone="success" dot={false}>Live</StatusBadge>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {can("pricing.create") && !draft && (
            <Button variant="secondary" size="sm" disabled={busy === "draft"} onClick={() => run("draft", async () => { await api.createDraft("Price update"); setTab("drafts"); })}>
              <Plus className="mr-1.5 h-3.5 w-3.5" />Create draft
            </Button>
          )}
          {draft && <StatusBadge tone="warning" dot={false}>Draft v{draft.version_number} in progress</StatusBadge>}
        </div>
      </div>

      {err && <Notice tone="warning">{err}</Notice>}

      <WorkflowTabs tabs={TABS.map<WorkflowTab>((t) => ({ id: t.id, label: t.label }))} value={tab} onChange={(id) => setTab(id as TabId)} />

      <MinimalKpiStrip kpis={kpis} />

      {tab === "current" && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <input className={`${input} max-w-xs`} placeholder="Search item or code…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <select className={`${input} max-w-xs`} value={cat} onChange={(e) => setCat(e.target.value)}>
              <option value="">All categories</option>
              {categories.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
            </select>
          </div>
          <DataPreviewTable
            columns={[
              { key: "cat", header: "Category", cell: (i: PricingItem) => i.category_name, primary: true },
              { key: "item", header: "Item", cell: (i) => <span className="font-medium text-ink">{i.canonical_name}</span> },
              { key: "code", header: "Code", cell: (i) => <span className="font-mono text-xxs text-ink-muted">{i.item_code}</span> },
              { key: "price", header: "Price", align: "right", cell: (i) => (
                <span className="tnum">{i.is_starting_price ? "From " : ""}{money(i.effective_price ?? i.current_price, i.currency)}<span className="text-xxs text-ink-faint"> /{i.pricing_unit.toLowerCase()}</span></span>
              ) },
              { key: "flags", header: "", cell: (i) => (
                <span className="flex flex-wrap gap-1">
                  {i.price_source === "promotion" && <StatusBadge tone="rose" dot={false}>Promo</StatusBadge>}
                  {i.requires_inspection && <StatusBadge tone="warning" dot={false}>Inspect</StatusBadge>}
                  {!i.active && <StatusBadge tone="neutral" dot={false}>Inactive</StatusBadge>}
                </span>
              ) },
            ]}
            rows={filtered}
            rowKey={(i) => i.item_code}
            onRowClick={can("pricing.edit") ? (i) => ensureDraftThenEdit(i) : undefined}
            empty={<EmptyState icon={Tag} title="No items" description="No catalogue items match the filters." />}
          />
          <p className="text-xxs text-ink-faint">
            {can("pricing.edit")
              ? <>Click an item to edit it. Editing stages a <span className="font-semibold text-ink">draft</span> — live prices don't change until you publish.</>
              : "You have read-only access to pricing."}
          </p>
        </>
      )}

      {tab === "drafts" && (
        <div className="space-y-3">
          {versions.filter((v) => v.status === "draft" || v.status === "pending_review").length === 0 ? (
            <EmptyState icon={Pencil} title="No drafts" description="Create a draft from Current Prices to stage changes." />
          ) : versions.filter((v) => v.status === "draft" || v.status === "pending_review").map((v) => (
            <div key={v.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/70 bg-surface p-5 shadow-card">
              <div>
                <p className="font-display text-sm font-semibold text-ink">Draft v{v.version_number} <StatusBadge tone={v.status === "pending_review" ? "info" : "warning"} dot={false}>{v.status}</StatusBadge></p>
                <p className="mt-0.5 text-xs text-ink-muted">{v.change_summary ?? "—"} · by {v.created_by ?? "—"} · {dt(v.created_at)}</p>
              </div>
              {can("pricing.publish") && (
                <Button variant="primary" size="sm" onClick={() => setPublishV(v)}><Rocket className="mr-1.5 h-3.5 w-3.5" />Preview & publish</Button>
              )}
            </div>
          ))}
          {/* Published version history + rollback */}
          <p className="pt-2 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Catalogue history</p>
          {versions.filter((v) => v.status !== "draft").map((v) => (
            <div key={v.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/60 bg-surface-2 px-4 py-3">
              <p className="text-sm text-ink">v{v.version_number} <StatusBadge tone={v.is_current ? "success" : "neutral"} dot={false}>{v.is_current ? "current" : v.status}</StatusBadge>{v.source === "rollback" && <span className="ml-1 text-xxs text-ink-faint">↩ rollback of v{v.rollback_of_version}</span>}</p>
              <div className="flex items-center gap-2 text-xxs text-ink-faint">
                <span>{dt(v.published_at)}</span>
                {can("pricing.rollback") && !v.is_current && (
                  <button className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 font-semibold text-ink-muted hover:border-rose/40 hover:text-rose"
                    disabled={busy === `rb${v.version_number}`}
                    onClick={() => { if (confirm(`Roll back to v${v.version_number}? This creates a new published version.`)) run(`rb${v.version_number}`, () => api.rollbackTo(v.version_number, "manual rollback")); }}>
                    <Undo2 className="h-3 w-3" />Roll back
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "promotions" && (
        <div className="space-y-3">
          {can("pricing.edit") && <Button variant="secondary" size="sm" onClick={() => setNewPromo(true)}><Plus className="mr-1.5 h-3.5 w-3.5" />New promotion</Button>}
          {promos.length === 0 ? (
            <EmptyState icon={Tag} title="No promotions" description="Promotions overlay the published price for a set window and revert automatically." />
          ) : (
            <div className="space-y-2">
              {promos.map((p) => (
                <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/70 bg-surface px-4 py-3 shadow-card">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">{p.name} <span className="font-mono text-xxs text-ink-faint">{p.item_code}</span></p>
                    <p className="mt-0.5 text-xxs text-ink-muted">{money(p.promo_price)} · {dt(p.starts_at)} → {dt(p.ends_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge tone={p.active ? "success" : "neutral"} dot={false}>{p.active ? "Active" : "Ended"}</StatusBadge>
                    {can("pricing.edit") && p.active && (
                      <button className="rounded-lg border border-border px-2.5 py-1 text-xxs font-semibold text-ink-muted hover:border-danger/40 hover:text-danger disabled:opacity-45"
                        disabled={busy === `end${p.id}`} onClick={() => run(`end${p.id}`, () => api.endPromotion(p.id))}>End</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "history" && (
        <DataPreviewTable
          columns={[
            { key: "when", header: "When", cell: (h: HistoryEntry) => <span className="text-xxs text-ink-muted">{dt(h.created_at)}</span>, primary: true },
            { key: "action", header: "Action", cell: (h) => <StatusBadge tone="neutral" dot={false}>{h.action}</StatusBadge> },
            { key: "entity", header: "Entity", cell: (h) => <span className="text-xs">{h.entity_type} {h.entity_ref ? `· ${h.entity_ref}` : ""}</span> },
            { key: "change", header: "Change", cell: (h) => h.field ? <span className="text-xxs text-ink-muted">{h.field}: {h.old_value ?? "—"} → {h.new_value ?? "—"}</span> : <span className="text-xxs text-ink-faint">{h.new_value ?? "—"}</span> },
            { key: "actor", header: "By", cell: (h) => <span className="text-xxs text-ink-faint">{h.actor ?? "—"}</span> },
          ]}
          rows={history} rowKey={(_, i) => String(i)}
          empty={<EmptyState icon={Info} title="No history yet" description="Pricing changes will appear here." />}
        />
      )}

      {tab === "sync" && (
        <DataPreviewTable
          columns={[
            { key: "target", header: "Target", cell: (s: SyncStatus["sync"][number]) => s.target, primary: true },
            { key: "v", header: "Version", cell: (s) => `v${s.version_number ?? "—"}` },
            { key: "status", header: "Status", cell: (s) => <StatusBadge tone={s.status === "success" ? "success" : s.status === "failed" ? "danger" : "warning"} dot={false}>{s.status}</StatusBadge> },
            { key: "detail", header: "Detail", cell: (s) => <span className="text-xxs text-ink-muted">{s.detail}</span> },
            { key: "when", header: "When", cell: (s) => <span className="text-xxs text-ink-faint">{dt(s.attempted_at)}</span> },
          ]}
          rows={sync?.sync ?? []} rowKey={(_, i) => String(i)}
          empty={<EmptyState icon={Info} title="No sync events" description="Publish a version to record website/WhatsApp sync." />}
        />
      )}

      {editItem && draft && (
        <EditItemModal item={editItem} versionId={draft.id} onClose={() => setEditItem(null)} onSaved={async () => { setEditItem(null); await reload(); setTab("drafts"); }} />
      )}
      {publishV && (
        <PublishModal version={publishV} onClose={() => setPublishV(null)} onPublished={async () => { setPublishV(null); await reload(); setTab("current"); }} />
      )}
      {newPromo && (
        <PromoModal items={items} onClose={() => setNewPromo(false)} onSaved={async () => { setNewPromo(false); await reload(); }} />
      )}
    </div>
  );
}

/* --------------------------- edit / publish / promo modals ----------------- */

function EditItemModal({ item, versionId, onClose, onSaved }: { item: PricingItem; versionId: string; onClose: () => void; onSaved: () => void }) {
  const [current, setCurrent] = useState(item.current_price ?? 0);
  const [regular, setRegular] = useState(item.regular_price ?? 0);
  const [active, setActive] = useState(item.active);
  const [disclaimer, setDisclaimer] = useState(item.disclaimer ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setBusy(true); setErr(null);
    try {
      await api.patchItem(versionId, item.item_code, {
        current_price: Number(current), regular_price: Number(regular), active, disclaimer,
      });
      onSaved();
    } catch (e) { setErr(e instanceof Error ? e.message : "Save failed."); } finally { setBusy(false); }
  };
  return (
    <Modal title={`Edit ${item.canonical_name}`} onClose={onClose}
      footer={<><Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button><Button variant="primary" size="sm" disabled={busy} onClick={save}>{busy ? "Saving…" : "Save to draft"}</Button></>}>
      <div className="space-y-3">
        <p className="text-xxs text-ink-faint">Staged in draft — live prices don't change until you publish.</p>
        <label className="block text-xs"><span className="text-ink-muted">Current price (AED, excl. VAT)</span><input className={input} type="number" step="0.01" value={current} onChange={(e) => setCurrent(e.target.valueAsNumber)} /></label>
        <label className="block text-xs"><span className="text-ink-muted">Regular price (crossed-out)</span><input className={input} type="number" step="0.01" value={regular} onChange={(e) => setRegular(e.target.valueAsNumber)} /></label>
        <label className="block text-xs"><span className="text-ink-muted">Customer disclaimer</span><input className={input} value={disclaimer} onChange={(e) => setDisclaimer(e.target.value)} /></label>
        <label className="flex items-center gap-2 text-xs text-ink"><input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />Active (shown to customers)</label>
        {err && <p className="text-xs text-danger">{err}</p>}
      </div>
    </Modal>
  );
}

function PublishModal({ version, onClose, onPublished }: { version: PricingVersion; onClose: () => void; onPublished: () => void }) {
  const [diff, setDiff] = useState<api.DiffEntry[]>([]);
  const [items, setItems] = useState<PricingItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.getVersion(version.id).then((v) => { setDiff(v.diff); setItems(v.items); }).catch(() => {}); }, [version.id]);
  const sample = items.find((i) => !i.is_starting_price && i.current_price) ?? items[0];
  const startingSample = items.find((i) => i.is_starting_price);
  const publish = async () => {
    setBusy(true); setErr(null);
    try { await api.publishVersion(version.id); onPublished(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Publish failed."); } finally { setBusy(false); }
  };
  return (
    <Modal title={`Publish draft v${version.version_number}`} onClose={onClose}
      footer={<><Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button><Button variant="primary" size="sm" disabled={busy} onClick={publish}>{busy ? "Publishing…" : `Publish v${version.version_number}`}</Button></>}>
      <div className="space-y-4">
        <p className="text-xs text-ink-muted">Publishing makes this the live catalogue for the WhatsApp agent and the public pricing API — immediately, with no restart. Historical orders keep their prices.</p>
        <div>
          <p className="mb-1 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Changes ({diff.length})</p>
          {diff.length === 0 ? <p className="text-xs text-ink-faint">No changes vs the current published version.</p> : (
            <ul className="max-h-40 space-y-1 overflow-y-auto text-xs">
              {diff.map((d) => (
                <li key={d.item_code} className="rounded-lg border border-border/60 bg-surface-2 px-3 py-1.5">
                  <span className="font-medium text-ink">{d.name ?? d.item_code}</span> — {d.change}
                  {d.fields && Object.entries(d.fields).map(([f, v]) => <span key={f} className="ml-1 text-ink-muted">{f}: {String(v.old)}→{String(v.new)}</span>)}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-border/60 bg-surface-2 p-3">
            <p className="mb-1 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">WhatsApp preview</p>
            {startingSample ? (
              <p className="text-xs text-ink">{startingSample.canonical_name}<br />From {money(startingSample.current_price)} per {startingSample.pricing_unit.toLowerCase()}<br /><span className="text-ink-faint">Final price depends on condition, material and brand.</span></p>
            ) : sample ? <p className="text-xs text-ink">{sample.canonical_name} — {money(sample.current_price)} per {sample.pricing_unit.toLowerCase()}</p> : <p className="text-xs text-ink-faint">—</p>}
          </div>
          <div className="rounded-xl border border-border/60 bg-surface-2 p-3">
            <p className="mb-1 text-xxs font-semibold uppercase tracking-eyebrow text-ink-faint">Website preview</p>
            {sample ? (
              <p className="text-xs text-ink">{sample.canonical_name}<br /><span className="font-semibold">{money(sample.current_price)}</span>{sample.regular_price ? <span className="ml-1 text-ink-faint line-through">{money(sample.regular_price)}</span> : null} / {sample.pricing_unit.toLowerCase()}<br /><span className="text-ink-faint">Prices exclude 5% VAT.</span></p>
            ) : <p className="text-xs text-ink-faint">—</p>}
          </div>
        </div>
        {err && <p className="text-xs text-danger">{err}</p>}
      </div>
    </Modal>
  );
}

function PromoModal({ items, onClose, onSaved }: { items: PricingItem[]; onClose: () => void; onSaved: () => void }) {
  const [itemCode, setItemCode] = useState(items[0]?.item_code ?? "");
  const [name, setName] = useState("");
  const [price, setPrice] = useState(0);
  const [starts, setStarts] = useState("");
  const [ends, setEnds] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setBusy(true); setErr(null);
    try {
      await api.createPromotion({ item_code: itemCode, name, promo_price: Number(price),
        starts_at: starts || undefined, ends_at: ends || undefined });
      onSaved();
    } catch (e) { setErr(e instanceof Error ? e.message : "Failed."); } finally { setBusy(false); }
  };
  return (
    <Modal title="New promotion" onClose={onClose}
      footer={<><Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button><Button variant="primary" size="sm" disabled={busy || !name || !itemCode} onClick={save}>{busy ? "Saving…" : "Create promotion"}</Button></>}>
      <div className="space-y-3">
        <label className="block text-xs"><span className="text-ink-muted">Item</span>
          <select className={input} value={itemCode} onChange={(e) => setItemCode(e.target.value)}>
            {items.map((i) => <option key={i.item_code} value={i.item_code}>{i.canonical_name} ({i.item_code})</option>)}
          </select></label>
        <label className="block text-xs"><span className="text-ink-muted">Promotion name</span><input className={input} value={name} onChange={(e) => setName(e.target.value)} placeholder="Eid Flash Sale" /></label>
        <label className="block text-xs"><span className="text-ink-muted">Promo price (AED)</span><input className={input} type="number" step="0.01" value={price} onChange={(e) => setPrice(e.target.valueAsNumber)} /></label>
        <div className="grid grid-cols-2 gap-2">
          <label className="block text-xs"><span className="text-ink-muted">Starts</span><input className={input} type="datetime-local" value={starts} onChange={(e) => setStarts(e.target.value)} /></label>
          <label className="block text-xs"><span className="text-ink-muted">Ends</span><input className={input} type="datetime-local" value={ends} onChange={(e) => setEnds(e.target.value)} /></label>
        </div>
        <p className="text-xxs text-ink-faint">The promo overlays the published price for its window and reverts automatically when it ends.</p>
        {err && <p className="text-xs text-danger">{err}</p>}
      </div>
    </Modal>
  );
}
