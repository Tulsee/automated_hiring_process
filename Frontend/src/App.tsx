import { useState } from "react";
import { AppShell } from "./components/AppShell";
import type { ViewId } from "./lib/nav";
import { useUrlState } from "./hooks/useUrlState";
import { DashboardPage } from "./pages/DashboardPage";
import { JobsPage } from "./pages/JobsPage";
import { CandidatesPage } from "./pages/CandidatesPage";
import { ReviewPage } from "./pages/ReviewPage";
import { InterviewsPage } from "./pages/InterviewsPage";
import { CandidatePortalPage } from "./pages/CandidatePortalPage";
import { InterviewPage } from "./pages/InterviewPage";

export default function App() {
  // An invite link carries ?token=…, which belongs to one candidate and one
  // interview. It bypasses the workspace entirely: nobody arriving on it
  // should see a recruiter's navigation.
  const inviteToken = new URLSearchParams(window.location.search).get("token");

  // Navigation lives in the URL, so Back, Forward, a mouse's side buttons and
  // a reload all work. See `useUrlState`.
  const { view, candidate, job, audience, go } = useUrlState();

  // Search is deliberately *not* in the URL: a history entry per keystroke
  // would make Back useless. It resets when the page changes.
  const [search, setSearch] = useState("");

  const [createJobOpen, setCreateJobOpen] = useState(false);

  function navigate(next: ViewId) {
    // Leaving a page closes whatever it had open.
    go({ view: next, candidate: null });
    setSearch("");
  }

  if (inviteToken) {
    return <InterviewPage token={inviteToken} />;
  }

  return (
    <AppShell
      view={view}
      onNavigate={navigate}
      audience={audience}
      onAudienceChange={(next) => go({ audience: next })}
      search={search}
      onSearchChange={setSearch}
    >
      {view === "dashboard" ? (
        <DashboardPage
          onNavigate={navigate}
          onOpenCandidate={(candidateId) =>
            go({ view: "candidates", candidate: candidateId })
          }
          onCreateJob={() => {
            go({ view: "jobs" });
            setCreateJobOpen(true);
          }}
        />
      ) : null}

      {view === "jobs" ? (
        <JobsPage
          search={search}
          createOpen={createJobOpen}
          onCreateOpenChange={setCreateJobOpen}
          onViewCandidates={(jobId) => {
            go({ view: "candidates", job: jobId, candidate: null });
            setSearch("");
          }}
        />
      ) : null}

      {view === "candidates" ? (
        <CandidatesPage
          search={search}
          jobFilter={job}
          onJobFilterChange={(jobId) => go({ job: jobId })}
          openCandidateId={candidate}
          // Opening a candidate adds a history entry, so Back closes the
          // dialog rather than leaving the page.
          onOpenCandidate={(candidateId) => go({ candidate: candidateId })}
        />
      ) : null}

      {view === "review" ? <ReviewPage search={search} /> : null}

      {view === "interviews" ? <InterviewsPage search={search} /> : null}

      {view === "portal" ? <CandidatePortalPage search={search} /> : null}
    </AppShell>
  );
}
