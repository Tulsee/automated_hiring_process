/**
 * Developer-facing detail about one candidate's processing.
 *
 * Two things a recruiter does not need but anyone debugging the pipeline does:
 *
 *   - the live screening status, which distinguishes "still processing" from
 *     "screened but scoreless" — a difference the candidate detail cannot
 *     express, because it only carries the stored score;
 *   - whether the candidate was actually indexed in the vector store, and with
 *     what payload.
 *
 * Both load only when the section is opened, so a recruiter never pays for a
 * request they did not ask for.
 */

import { useState } from "react";
import { api } from "../api/client";
import { useApi } from "../hooks/useApi";
import { screeningIsComplete } from "../types";
import { Icon } from "./Icon";
import { Loading, StatusPill } from "./primitives";

export function CandidateDiagnostics({
  candidateId,
}: {
  candidateId: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <h3>Diagnostics</h3>
      <button
        type="button"
        className="accordion-button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span>
          Processing detail
          <span className="table-subtext">
            Screening status and vector-store record
          </span>
        </span>
        <Icon name={open ? "chevron-up" : "chevron-down"} size={14} />
      </button>

      {open ? (
        <div style={{ paddingBottom: 12 }}>
          <ScreeningStatus candidateId={candidateId} />
          <VectorRecord candidateId={candidateId} />
        </div>
      ) : null}
    </>
  );
}

/** The screening endpoint's own view, which reports progress. */
function ScreeningStatus({ candidateId }: { candidateId: string }) {
  const screening = useApi(
    () => api.getCandidateScreening(candidateId),
    [candidateId],
  );

  if (screening.loading) return <Loading what="screening status" />;

  if (screening.error) {
    return (
      <p className="table-note" role="alert">
        Screening status unavailable: {screening.error.message}
      </p>
    );
  }

  const result = screening.data;

  if (!result) return null;

  if (!screeningIsComplete(result)) {
    return (
      <div style={{ padding: "10px 0" }}>
        <div className="pipeline-stage-top">
          <span>Screening</span>
          <strong>
            <StatusPill value={result.status} />
          </strong>
        </div>
        <p className="table-note">{result.message}</p>
      </div>
    );
  }

  return (
    <div style={{ padding: "10px 0" }}>
      <div className="pipeline-stage-top">
        <span>Screening</span>
        <strong>{result.screening_score.toFixed(2)} / 100</strong>
      </div>
      <p className="table-note">
        Matched {result.matched_skills.length} required{" "}
        {result.matched_skills.length === 1 ? "skill" : "skills"},{" "}
        {result.missing_skills.length} missing. Reported directly by the
        screening endpoint.
      </p>
    </div>
  );
}

/** Whether the candidate made it into the vector store. */
function VectorRecord({ candidateId }: { candidateId: string }) {
  const vector = useApi(
    () => api.getCandidateVector(candidateId),
    [candidateId],
  );

  if (vector.loading) return <Loading what="the vector record" />;

  if (vector.error) {
    // A 404 here is information, not a failure: it means this candidate was
    // never embedded, which is why semantic similarity would be missing.
    const missing = "status" in vector.error && vector.error.status === 404;

    return (
      <div style={{ padding: "10px 0" }}>
        <div className="pipeline-stage-top">
          <span>Vector store</span>
          <strong>
            <StatusPill value={missing ? "pending" : "failed"} />
          </strong>
        </div>
        <p className="table-note">
          {missing
            ? "No embedding stored for this candidate, so semantic similarity could not be computed."
            : vector.error.message}
        </p>
      </div>
    );
  }

  const record = vector.data;

  if (!record) return null;

  return (
    <div style={{ padding: "10px 0" }}>
      <div className="pipeline-stage-top">
        <span>Vector store</span>
        <strong>{record.vector_dimensions} dimensions</strong>
      </div>
      <dl style={{ margin: "8px 0 0" }}>
        {Object.entries(record.payload).map(([key, value]) => (
          <div
            key={key}
            style={{ display: "flex", gap: 8, padding: "3px 0" }}
          >
            <dt
              className="table-subtext"
              style={{ minWidth: 92, marginTop: 0 }}
            >
              {key}
            </dt>
            <dd
              className="table-subtext"
              style={{
                margin: 0,
                marginTop: 0,
                overflowWrap: "anywhere",
                color: "var(--text-muted)",
              }}
            >
              {Array.isArray(value)
                ? `${value.length} item${value.length === 1 ? "" : "s"}: ${value
                    .slice(0, 8)
                    .join(", ")}${value.length > 8 ? "…" : ""}`
                : String(value)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
