import { useCallback, useEffect, useState } from "react";
import type { ViewId } from "../lib/nav";

/**
 * Navigation held in the URL, so the browser's Back button works.
 *
 * Navigation used to be `useState`, which meant nothing was ever pushed to
 * history: Back had no entry to return to and left the app entirely. Every
 * navigable thing now lives in the query string, so Back, Forward, a mouse's
 * back button, a reload and a pasted link all behave the way a browser's
 * users expect.
 *
 * Why the query string rather than paths: the app is served from
 * `/dashboard/` by `StaticFiles`, which serves `index.html` for a directory
 * but not for an arbitrary sub-path. `"/dashboard/candidates"` would 404 on
 * reload, while `"/dashboard/?view=candidates"` cannot. It also needs no
 * router dependency for six flat views.
 */

export type Audience = "recruiter" | "applicant";

export interface UrlState {
  view: ViewId;
  /** The candidate whose detail dialog is open, if any. */
  candidate: string | null;
  /** The job the candidate list is filtered to. */
  job: string;
  audience: Audience;
}

const VIEWS: ViewId[] = [
  "dashboard",
  "jobs",
  "candidates",
  "review",
  "interviews",
  "access",
  "approvals",
  "profile",
  "myapps",
  "portal",
];

export const DEFAULT_STATE: UrlState = {
  view: "dashboard",
  candidate: null,
  job: "",
  audience: "recruiter",
};

/** Read the state the URL describes, ignoring anything unrecognised. */
export function readUrlState(search: string = window.location.search): UrlState {
  const params = new URLSearchParams(search);

  const view = params.get("view") as ViewId | null;

  const audience = params.get("audience");

  return {
    view: view && VIEWS.includes(view) ? view : DEFAULT_STATE.view,
    candidate: params.get("candidate") || null,
    job: params.get("job") ?? "",
    audience: audience === "applicant" ? "applicant" : "recruiter",
  };
}

/**
 * The query string for a state.
 *
 * Defaults are left out so a URL carries only what differs, and `token` is
 * preserved because an applicant's invite link must survive navigation.
 */
export function writeUrlState(
  state: UrlState,
  search: string = window.location.search,
): string {
  const params = new URLSearchParams();

  const token = new URLSearchParams(search).get("token");

  if (token) params.set("token", token);

  if (state.view !== DEFAULT_STATE.view) params.set("view", state.view);
  if (state.candidate) params.set("candidate", state.candidate);
  if (state.job) params.set("job", state.job);
  if (state.audience !== DEFAULT_STATE.audience) {
    params.set("audience", state.audience);
  }

  const serialised = params.toString();

  return serialised ? `?${serialised}` : window.location.pathname;
}

export interface Navigation extends UrlState {
  /**
   * Move to a new state, adding a history entry.
   *
   * Opening a dialog counts: it means Back closes the dialog rather than
   * leaving the page, which is what a Back press is for.
   */
  go: (changes: Partial<UrlState>) => void;
  /** Change the URL without adding an entry, for corrections. */
  replace: (changes: Partial<UrlState>) => void;
}

export function useUrlState(): Navigation {
  const [state, setState] = useState<UrlState>(() => readUrlState());

  // Back, Forward and the mouse's side buttons all arrive here.
  useEffect(() => {
    function onPopState() {
      setState(readUrlState());
    }

    window.addEventListener("popstate", onPopState);

    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const apply = useCallback(
    (changes: Partial<UrlState>, mode: "push" | "replace") => {
      const next = { ...readUrlState(), ...changes };

      const url = writeUrlState(next);

      // An identical push would add an entry that Back cannot escape.
      const unchanged =
        url === `${window.location.search || window.location.pathname}`;

      if (mode === "push" && !unchanged) {
        window.history.pushState(next, "", url);
      } else {
        window.history.replaceState(next, "", url);
      }

      setState(next);
    },
    [],
  );

  const go = useCallback(
    (changes: Partial<UrlState>) => apply(changes, "push"),
    [apply],
  );

  const replace = useCallback(
    (changes: Partial<UrlState>) => apply(changes, "replace"),
    [apply],
  );

  return { ...state, go, replace };
}
