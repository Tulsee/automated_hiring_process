/**
 * The superadmin's approval queue for administration profile changes.
 *
 * An administration user's profile edit does not take effect until it is
 * approved here. Each row shows exactly what would change (old → new) so the
 * superadmin is approving something specific, not a black box.
 */

import { api } from "../api/client";
import { useApi, useAction } from "../hooks/useApi";
import { Icon } from "../components/Icon";
import {
  EmptyState,
  ErrorState,
  Loading,
  Panel,
} from "../components/primitives";
import { PageHeader } from "../components/AppShell";
import { humanise } from "../lib/format";
import type { ChangeRequest } from "../types";

function renderValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  const text = String(value);
  // A base64 photo is unreadable; say what it is instead of dumping it.
  if (text.startsWith("data:image")) return "(new photo)";
  return text.length > 80 ? `${text.slice(0, 80)}…` : text;
}

export function ApprovalsPage() {
  const requests = useApi(() => api.listChangeRequests(), []);

  return (
    <>
      <PageHeader
        eyebrow="SUPERADMIN"
        title="Approval"
        highlight="queue"
        subtitle="Administration profile changes wait here for your decision."
      />

      {requests.error ? (
        <ErrorState error={requests.error} onRetry={requests.reload} />
      ) : requests.loading ? (
        <Panel>
          <Loading what="pending changes" />
        </Panel>
      ) : (requests.data ?? []).length === 0 ? (
        <Panel>
          <EmptyState title="Nothing to approve">
            When an administrator edits their profile, the change appears here
            for you to approve or reject.
          </EmptyState>
        </Panel>
      ) : (
        <div className="approval-list">
          {requests.data!.map((request) => (
            <RequestCard
              key={request.id}
              request={request}
              onDecided={requests.reload}
            />
          ))}
        </div>
      )}
    </>
  );
}

function RequestCard({
  request,
  onDecided,
}: {
  request: ChangeRequest;
  onDecided: () => void;
}) {
  const approve = useAction(api.approveChangeRequest);
  const reject = useAction(api.rejectChangeRequest);
  const pending = approve.pending || reject.pending;

  return (
    <Panel
      title={request.user_name ?? request.user_email ?? "An administrator"}
      subtitle={request.user_email ?? ""}
    >
      <table className="approval-table">
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">Current</th>
            <th scope="col">Requested</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(request.changes).map(([field, change]) => (
            <tr key={field}>
              <td>{humanise(field)}</td>
              <td className="muted">{renderValue(change.from)}</td>
              <td>
                <strong>{renderValue(change.to)}</strong>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {approve.error || reject.error ? (
        <p className="table-note" role="alert">
          {(approve.error ?? reject.error)!.message}
        </p>
      ) : null}

      <div className="modal-actions">
        <button
          type="button"
          className="button button--secondary"
          disabled={pending}
          onClick={async () => {
            const done = await reject.run(request.id);
            if (done) onDecided();
          }}
        >
          {reject.pending ? "Rejecting…" : "Reject"}
        </button>
        <button
          type="button"
          className="button button--primary"
          disabled={pending}
          onClick={async () => {
            const done = await approve.run(request.id);
            if (done) onDecided();
          }}
        >
          <Icon name="check" size={13} />{" "}
          {approve.pending ? "Approving…" : "Approve"}
        </button>
      </div>
    </Panel>
  );
}
