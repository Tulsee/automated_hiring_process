/**
 * Whether the API is answering.
 *
 * Without this, an empty dashboard is ambiguous: a recruiter cannot tell
 * "no candidates yet" from "the backend is not running", which is the single
 * most common thing to be wrong in local development.
 */

import { api } from "../api/client";
import { useApi } from "../hooks/useApi";

export function ApiStatus() {
  const health = useApi(() => api.health(), []);

  if (health.loading) {
    return <span className="privacy-note">Checking API…</span>;
  }

  if (health.error) {
    return (
      <span className="status status--in-review" role="status">
        API unreachable
      </span>
    );
  }

  return (
    <span className="privacy-note" role="status">
      API {health.data?.status ?? "ok"}
    </span>
  );
}
