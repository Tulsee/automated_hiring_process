/** Navigation model, shared by the shell and the pages that navigate. */

import type { IconName } from "../components/Icon";

export type ViewId =
  | "dashboard"
  | "jobs"
  | "candidates"
  | "review"
  | "interviews"
  | "access"
  | "approvals"
  | "profile"
  | "myapps"
  | "portal";

export interface NavEntry {
  id: ViewId;
  label: string;
  icon: IconName;
  /**
   * Permissions that make this entry reachable. An entry with none is open to
   * any administration user; an entry listing several shows if the user holds
   * *any* of them. The superadmin sees everything regardless.
   */
  anyOf?: string[];
  /** Only the superadmin sees this entry (e.g. the approvals queue). */
  superadminOnly?: boolean;
}

export const RECRUITER_NAV: NavEntry[] = [
  { id: "dashboard", label: "Dashboard", icon: "trending" },
  { id: "jobs", label: "Jobs", icon: "briefcase", anyOf: ["jobs:read", "jobs:write"] },
  { id: "candidates", label: "Candidates", icon: "users", anyOf: ["candidates:read"] },
  { id: "review", label: "Review queue", icon: "clipboard", anyOf: ["interviews:read"] },
  { id: "interviews", label: "Interviews", icon: "calendar", anyOf: ["interviews:read"] },
  {
    id: "access",
    label: "Access control",
    icon: "settings",
    anyOf: ["roles:manage", "users:manage"],
  },
  {
    id: "approvals",
    label: "Approvals",
    icon: "clipboard",
    superadminOnly: true,
  },
  { id: "profile", label: "My profile", icon: "users" },
];

export const APPLICANT_NAV: NavEntry[] = [
  { id: "myapps", label: "My applications", icon: "clipboard" },
  { id: "portal", label: "Open roles", icon: "briefcase" },
  { id: "profile", label: "My profile", icon: "users" },
];

/** The entries an administration user may actually use. */
export function visibleNav(
  entries: NavEntry[],
  can: (permission: string) => boolean,
  isSuperadmin = false,
): NavEntry[] {
  return entries.filter((entry) => {
    if (entry.superadminOnly && !isSuperadmin) return false;
    return !entry.anyOf || entry.anyOf.some((permission) => can(permission));
  });
}
