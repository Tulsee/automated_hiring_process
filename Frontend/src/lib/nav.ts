/** Navigation model, shared by the shell and the pages that navigate. */

import type { IconName } from "../components/Icon";

export type ViewId =
  | "dashboard"
  | "jobs"
  | "candidates"
  | "review"
  | "interviews"
  | "portal";

export interface NavEntry {
  id: ViewId;
  label: string;
  icon: IconName;
}

export const RECRUITER_NAV: NavEntry[] = [
  { id: "dashboard", label: "Dashboard", icon: "trending" },
  { id: "jobs", label: "Jobs", icon: "briefcase" },
  { id: "candidates", label: "Candidates", icon: "users" },
  { id: "review", label: "Review queue", icon: "clipboard" },
  { id: "interviews", label: "Interviews", icon: "calendar" },
];

export const APPLICANT_NAV: NavEntry[] = [
  { id: "portal", label: "Open roles", icon: "briefcase" },
];
