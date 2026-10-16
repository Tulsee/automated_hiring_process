/**
 * Pipeline rules shared by every view that offers an action.
 *
 * These mirror the backend's own rules (`app/services/interview_service.py`).
 * They live in one place because having two views disagree about whether a
 * candidate can be interviewed is how a dead-end button appears: the detail
 * panel once offered "Create interview invite" to rejected candidates, which
 * the API answered with 400.
 */

/**
 * Decisions that make a candidate interviewable.
 *
 * Both spellings are accepted: the screening graph used to write
 * `invite_to_interview`, so candidates already in the database carry either.
 */
export const ELIGIBLE_DECISIONS = new Set([
  "invited_to_interview",
  "invite_to_interview",
]);

export function isEligibleForInterview(
  decision: string | null | undefined,
): boolean {
  return decision !== null && decision !== undefined
    ? ELIGIBLE_DECISIONS.has(decision)
    : false;
}
