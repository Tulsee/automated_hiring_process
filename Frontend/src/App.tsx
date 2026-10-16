import { useState } from "react";
import { AppShell } from "./components/AppShell";
import type { ViewId } from "./lib/nav";
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

  const [view, setView] = useState<ViewId>("dashboard");
  const [audience, setAudience] = useState<"recruiter" | "applicant">(
    "recruiter",
  );

  // Search lives in the shell so the topbar field drives whichever page is
  // open, which is what a single global search is for.
  const [search, setSearch] = useState("");

  // Cross-page intents: opening a candidate from the dashboard, or filtering
  // candidates by the job you just clicked.
  const [openCandidateId, setOpenCandidateId] = useState<string | null>(null);
  const [jobFilter, setJobFilter] = useState("");
  const [createJobOpen, setCreateJobOpen] = useState(false);

  function navigate(next: ViewId) {
    setView(next);
    setSearch("");
  }

  function openCandidate(candidateId: string) {
    setOpenCandidateId(candidateId);
    setView("candidates");
  }

  if (inviteToken) {
    return <InterviewPage token={inviteToken} />;
  }

  return (
    <AppShell
      view={view}
      onNavigate={navigate}
      audience={audience}
      onAudienceChange={setAudience}
      search={search}
      onSearchChange={setSearch}
    >
      {view === "dashboard" ? (
        <DashboardPage
          onNavigate={navigate}
          onOpenCandidate={openCandidate}
          onCreateJob={() => {
            setView("jobs");
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
            setJobFilter(jobId);
            navigate("candidates");
          }}
        />
      ) : null}

      {view === "candidates" ? (
        <CandidatesPage
          search={search}
          jobFilter={jobFilter}
          onJobFilterChange={setJobFilter}
          openCandidateId={openCandidateId}
          onOpenCandidate={setOpenCandidateId}
        />
      ) : null}

      {view === "review" ? <ReviewPage search={search} /> : null}

      {view === "interviews" ? <InterviewsPage search={search} /> : null}

      {view === "portal" ? <CandidatePortalPage search={search} /> : null}
    </AppShell>
  );
}
