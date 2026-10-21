/**
 * Which entry the browser is at, and how to link between them.
 *
 * The app is served under a base path (`/dashboard/` in production, `/` in
 * tests). Three public entries share that base as real URLs, so a reload lands
 * back on the same screen:
 *
 *   <base>          the public job board (anyone)
 *   <base>admin     the hiring-team sign-in
 *   <base>apply     the candidate sign-in / sign-up
 */

export type Entry = "root" | "admin" | "apply";

const BASE = import.meta.env.BASE_URL || "/";

/** The entry the current URL names. */
export function currentEntry(): Entry {
  const path = window.location.pathname.replace(/\/+$/, "");
  if (path.endsWith("/admin")) return "admin";
  if (path.endsWith("/apply")) return "apply";
  return "root";
}

/** The absolute href for an entry, under the app's base path. */
export function entryHref(entry: Entry): string {
  if (entry === "root") return BASE;
  return `${BASE}${entry}`;
}

/** Navigate to an entry with a full load, so the backend serves its page. */
export function goToEntry(entry: Entry): void {
  window.location.assign(entryHref(entry));
}
