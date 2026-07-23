/**
 * Single source of truth for dashboard RBAC roles.
 *
 * There are exactly two roles, matching the backend (services/auth.py ROLES and
 * the users.role CHECK constraint): `admin` and `operations`. Route access,
 * the Settings → Roles & Permissions view, and the sidebar/guard all derive from
 * here, so the frontend can never drift from what the backend enforces.
 *
 * Hiding nav for a role is a UX convenience only — the backend independently
 * enforces role on every guarded /api/* call (api/deps.require_roles).
 */
import type { UserRole } from "./auth-token";

export interface RoleDef {
  id: UserRole;
  label: string;
  description: string;
  /** Route prefixes this role may reach. "all" = every route (admin). */
  allowedPrefixes: string[] | "all";
  /** Human-readable list of what the role can access (for the Roles UI). */
  access: string[];
}

export const ROLES: Record<UserRole, RoleDef> = {
  admin: {
    id: "admin",
    label: "Administrator",
    description: "Full access to every section, settings, and user management.",
    allowedPrefixes: "all",
    access: [
      "All dashboard sections",
      "Settings & configuration",
      "User & role management",
      "All approvals",
    ],
  },
  operations: {
    id: "operations",
    label: "Operations",
    description: "Day-to-day order & operations work only — no settings or admin areas.",
    allowedPrefixes: ["/orders", "/operations"],
    access: [
      "Orders",
      "Operations · Customer Facing",
      "Operations · Facility Facing",
      "Operations · Drivers",
      "Operations · Customer Orders",
    ],
  },
};

export const ROLE_LIST: RoleDef[] = Object.values(ROLES);

/** Whether a role may reach a route. Admin → everything; others → their prefixes. */
export function roleAllowsRoute(role: UserRole, pathname: string): boolean {
  const def = ROLES[role];
  if (!def) return false;
  if (def.allowedPrefixes === "all") return true;
  return def.allowedPrefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Human label for a role (falls back to "Member" for an unknown/absent role). */
export function roleLabel(role: UserRole | null | undefined): string {
  return role && ROLES[role] ? ROLES[role].label : "Member";
}
