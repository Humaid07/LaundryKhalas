/**
 * Roles for the facility dashboard.
 *
 * Facility partners sign in with a facility_* role. admin/operations are the
 * internal LaundryKhalas roles and are allowed everywhere here too (an internal
 * operator may need to view a partner's workspace for support).
 *
 * Hiding nav for a role is a UX convenience only — the backend independently
 * enforces role on every guarded /api/* call.
 */
import type { UserRole } from "./auth-token";

export interface RoleDef {
  id: UserRole;
  label: string;
  description: string;
}

export const ROLES: Record<UserRole, RoleDef> = {
  admin: {
    id: "admin",
    label: "Administrator",
    description: "Internal LaundryKhalas administrator.",
  },
  operations: {
    id: "operations",
    label: "Operations",
    description: "Internal LaundryKhalas operations team.",
  },
  facility_owner: {
    id: "facility_owner",
    label: "Facility Owner",
    description: "Full access to this facility's workspace and settings.",
  },
  facility_manager: {
    id: "facility_manager",
    label: "Facility Manager",
    description: "Day-to-day management of orders, finance and team.",
  },
  facility_staff: {
    id: "facility_staff",
    label: "Facility Staff",
    description: "Handle orders on the floor — receive, clean, QC, hand off.",
  },
  facility_driver: {
    id: "facility_driver",
    label: "Facility Driver / Runner",
    description: "Pickups and handoffs for this facility.",
  },
};

/** Every authenticated role may use the facility workspace. */
export function roleAllowsRoute(_role: UserRole, _pathname: string): boolean {
  return true;
}

/** Roles allowed to perform facility management writes (create/edit drivers,
 *  assign work, change statuses). Mirrors the backend's own enforcement — the
 *  UI hides manage actions for other roles as a convenience only. */
const MANAGE_ROLES: ReadonlySet<UserRole> = new Set<UserRole>([
  "facility_owner",
  "facility_manager",
  "admin",
]);

export function canManageFacility(role: UserRole | null | undefined): boolean {
  return !!role && MANAGE_ROLES.has(role);
}

/** Human label for a role (falls back to "Member" for an unknown/absent role). */
export function roleLabel(role: UserRole | null | undefined): string {
  return role && ROLES[role] ? ROLES[role].label : "Member";
}
