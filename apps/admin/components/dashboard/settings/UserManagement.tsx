"use client";

import { useCallback, useEffect, useState } from "react";
import { Shield, Users, User, UserPlus, Info, Loader2 } from "lucide-react";
import { Panel } from "@/components/dashboard/ui/primitives";
import { StatusBadge } from "@/components/dashboard/minimal";
import { Button } from "@/components/dashboard/ui/Button";
import { useAuth } from "@/lib/dashboard/auth-context";
import { ROLE_LIST, ROLES, roleLabel } from "@/lib/dashboard/roles";
import type { UserRole } from "@/lib/dashboard/auth-token";
import {
  listUsers, createUser, updateUser, UsersUnavailableError,
  type ManagedUser,
} from "@/lib/dashboard/users-api";

/* Shared panel header (mirrors Settings.tsx SettingsSection). */
function PanelHead({ icon: Icon, title, description }: { icon: typeof User; title: string; description: string }) {
  return (
    <div className="mb-4 flex items-start gap-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose/10 text-rose"><Icon className="h-4 w-4" /></span>
      <div>
        <h3 className="font-display text-sm font-semibold text-ink">{title}</h3>
        <p className="text-xs text-ink-muted">{description}</p>
      </div>
    </div>
  );
}

function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-info/20 bg-info/[0.06] px-3.5 py-3">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
      <p className="text-xs leading-relaxed text-ink-muted">{children}</p>
    </div>
  );
}

const initials = (s: string) => s.split(/[\s@.]+/).filter(Boolean).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

/* --------------------------- shared user-loading hook ----------------------- */

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; users: ManagedUser[] }
  | { kind: "unavailable"; message: string }
  | { kind: "error"; message: string };

function useUsers(): [LoadState, () => void] {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const reload = useCallback(() => {
    setState({ kind: "loading" });
    listUsers()
      .then(({ users }) => setState({ kind: "ready", users }))
      .catch((e) => {
        if (e instanceof UsersUnavailableError) setState({ kind: "unavailable", message: e.message });
        else setState({ kind: "error", message: e?.message ?? "Failed to load users." });
      });
  }, []);
  useEffect(() => { reload(); }, [reload]);
  return [state, reload];
}

/* ------------------------------- Roles view --------------------------------- */

export function RolesPermissionsPanel() {
  const { role: myRole } = useAuth();
  const [state] = useUsers();
  const counts: Partial<Record<UserRole, number>> =
    state.kind === "ready"
      ? state.users.reduce((acc, u) => ({ ...acc, [u.role]: (acc[u.role] ?? 0) + 1 }), {} as Record<UserRole, number>)
      : {};

  return (
    <Panel>
      <PanelHead icon={Shield} title="Roles & permissions" description="The two access levels enforced across the dashboard and the backend." />
      <ul className="space-y-3">
        {ROLE_LIST.map((r) => (
          <li key={r.id} className="rounded-xl border border-border/70 bg-surface-2 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-ink">{r.label}</p>
                {myRole === r.id && <StatusBadge tone="rose" dot={false}>You</StatusBadge>}
              </div>
              {state.kind === "ready" && (
                <span className="text-xxs text-ink-faint">{counts[r.id] ?? 0} member{(counts[r.id] ?? 0) === 1 ? "" : "s"}</span>
              )}
            </div>
            <p className="mt-1 text-xs text-ink-muted">{r.description}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {r.access.map((a) => (
                <span key={a} className="rounded-full border border-border bg-surface px-2 py-0.5 text-xxs font-medium text-ink-muted">{a}</span>
              ))}
            </div>
          </li>
        ))}
      </ul>
      {state.kind === "unavailable" && (
        <div className="mt-4"><Notice>Member counts and user management are available when the backend runs with authentication enabled (<code className="font-mono text-xxs">REQUIRE_AUTH=true</code>) and <code className="font-mono text-xxs">DATABASE_MODE=supabase</code>. Roles themselves are fixed and always enforced.</Notice></div>
      )}
    </Panel>
  );
}

/* --------------------------- Profile + Users view --------------------------- */

function InviteForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("operations");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      await createUser({ email, full_name: fullName || null, password, role });
      setEmail(""); setFullName(""); setPassword(""); setRole("operations"); setOpen(false);
      onCreated();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Could not create user.");
    } finally { setBusy(false); }
  };

  if (!open) return <Button variant="secondary" size="sm" className="mt-3" onClick={() => setOpen(true)}><UserPlus className="mr-1.5 h-3.5 w-3.5" />Add user</Button>;

  const input = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-rose/40";
  return (
    <form onSubmit={submit} className="mt-4 space-y-2.5 rounded-xl border border-border/70 bg-surface-2 p-4">
      <div className="grid gap-2.5 sm:grid-cols-2">
        <input className={input} type="email" required placeholder="email@laundrykhalas.com" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className={input} placeholder="Full name (optional)" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        <input className={input} type="password" required minLength={8} placeholder="Temp password (min 8)" value={password} onChange={(e) => setPassword(e.target.value)} />
        <select className={input} value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
          {ROLE_LIST.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
        </select>
      </div>
      {err && <p className="text-xs text-danger">{err}</p>}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" disabled={busy}>{busy ? "Adding…" : "Create user"}</Button>
        <Button type="button" variant="secondary" size="sm" onClick={() => { setOpen(false); setErr(null); }}>Cancel</Button>
      </div>
    </form>
  );
}

function UserRow({ u, isMe, onChanged }: { u: ManagedUser; isMe: boolean; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async (patch: Parameters<typeof updateUser>[1]) => {
    setBusy(true); setErr(null);
    try { await updateUser(u.id, patch); onChanged(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Update failed."); }
    finally { setBusy(false); }
  };
  const select = "rounded-lg border border-border bg-surface px-2 py-1 text-xs text-ink outline-none focus-visible:ring-2 focus-visible:ring-rose/40 disabled:opacity-50";
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-rose/12 text-xxs font-bold text-rose">{initials(u.full_name || u.email)}</span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-ink">{u.full_name || u.email}{isMe && <span className="ml-1.5 text-xxs text-rose">(you)</span>}</p>
          <p className="truncate text-xxs text-ink-faint">{u.email}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {busy && <Loader2 className="h-3.5 w-3.5 animate-spin text-ink-faint" />}
        <select
          className={select}
          value={u.role}
          disabled={busy || isMe}
          title={isMe ? "You can't change your own role" : undefined}
          onChange={(e) => run({ role: e.target.value as UserRole })}
        >
          {ROLE_LIST.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
        </select>
        <button
          type="button"
          disabled={busy || (isMe && u.is_active)}
          onClick={() => run({ is_active: !u.is_active })}
          title={isMe && u.is_active ? "You can't deactivate your own account" : undefined}
          className="rounded-lg border border-border px-2.5 py-1 text-xxs font-semibold text-ink-muted transition-colors hover:border-border-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-45"
        >
          {u.is_active ? "Deactivate" : "Activate"}
        </button>
        <StatusBadge tone={u.is_active ? "success" : "neutral"} dot={false}>{u.is_active ? "Active" : "Inactive"}</StatusBadge>
      </div>
      {err && <p className="w-full text-right text-xxs text-danger">{err}</p>}
    </li>
  );
}

export function ProfileTeamPanel() {
  const { user, role } = useAuth();
  const [state, reload] = useUsers();

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel>
        <PanelHead icon={User} title="Profile" description="Your account" />
        <div className="flex items-center gap-4">
          <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-rose/12 font-display text-lg font-bold text-rose">{initials(user?.full_name || user?.email || "?")}</span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-ink">{user?.full_name || user?.email || "—"}</p>
            <p className="truncate text-xs text-ink-muted">{user?.email ?? "—"} · {roleLabel(role)}</p>
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHead icon={Users} title="Users" description="Dashboard accounts & their roles" />
        {state.kind === "loading" && (
          <div className="flex items-center gap-2 py-6 text-sm text-ink-muted"><Loader2 className="h-4 w-4 animate-spin text-rose" />Loading users…</div>
        )}
        {state.kind === "unavailable" && (
          <Notice>User management is available when the backend runs with authentication enabled (<code className="font-mono text-xxs">REQUIRE_AUTH=true</code>) and <code className="font-mono text-xxs">DATABASE_MODE=supabase</code>. In local dev you're signed in as a synthetic admin, so there are no stored accounts to manage yet.</Notice>
        )}
        {state.kind === "error" && <p className="py-4 text-sm text-danger">{state.message}</p>}
        {state.kind === "ready" && (
          <>
            <ul className="divide-y divide-border">
              {state.users.map((u) => (
                <UserRow key={u.id} u={u} isMe={!!user?.id && String(user.id) === String(u.id)} onChanged={reload} />
              ))}
            </ul>
            <InviteForm onCreated={reload} />
          </>
        )}
      </Panel>
    </div>
  );
}
