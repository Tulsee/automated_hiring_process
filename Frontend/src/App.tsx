import { useState } from "react";
import { AppShell } from "./components/AppShell";
import type { ViewId } from "./lib/nav";
import { useUrlState } from "./hooks/useUrlState";
import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/context";
import { Loading } from "./components/primitives";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { JobsPage } from "./pages/JobsPage";
import { CandidatesPage } from "./pages/CandidatesPage";
import { ReviewPage } from "./pages/ReviewPage";
import { InterviewsPage } from "./pages/InterviewsPage";
import { AccessControlPage } from "./pages/AccessControlPage";
import { CandidatePortalPage } from "./pages/CandidatePortalPage";
import { MyApplicationsPage } from "./pages/MyApplicationsPage";
import { InterviewPage } from "./pages/InterviewPage";

export default function App() {
  return (
    <AuthProvider>
      <AppRoot />
    </AuthProvider>
  );
}

function AppRoot() {
  // An invite link carries ?token=…, which belongs to one candidate and one
  // interview. It bypasses auth and the workspace entirely — a candidate
  // follows an emailed link without an account, as they always have.
  const inviteToken = new URLSearchParams(window.location.search).get("token");

  const { user, loading } = useAuth();

  if (inviteToken) {
    return <InterviewPage token={inviteToken} />;
  }

  // Wait for the "am I still signed in?" check before choosing a screen, so a
  // reload does not flash the login page at an authenticated user.
  if (loading) {
    return (
      <div className="login-shell">
        <Loading what="your session" />
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return <Workspace />;
}

function Workspace() {
  const { can, isAdministration } = useAuth();

  // Navigation lives in the URL, so Back, Forward, a mouse's side buttons and
  // a reload all work. See `useUrlState`.
  const { view, candidate, job, audience, go } = useUrlState();

  // Search is deliberately *not* in the URL: a history entry per keystroke
  // would make Back useless. It resets when the page changes.
  const [search, setSearch] = useState("");

  const [createJobOpen, setCreateJobOpen] = useState(false);

  // A candidate only ever sees the portal; the workspace nav is not theirs.
  const effectiveAudience = isAdministration ? audience : "applicant";

  function navigate(next: ViewId) {
    go({ view: next, candidate: null });
    setSearch("");
  }

  // A view the user is not allowed to see (a role lacking the permission, or a
  // candidate) falls back to one they can: the dashboard for administration,
  // their application tracker for a candidate.
  const home: ViewId = isAdministration ? "dashboard" : "myapps";

  // A candidate has just two screens — their application tracker and the open
  // roles. Anything else (e.g. a stale ?view from the recruiter side) lands on
  // the tracker.
  const APPLICANT_VIEWS: ViewId[] = ["myapps", "portal"];

  const showView =
    effectiveAudience === "applicant"
      ? APPLICANT_VIEWS.includes(view)
        ? view
        : home
      : view === "access" && !can("roles:manage") && !can("users:manage")
        ? home
        : view;

  return (
    <AppShell
      view={showView}
      onNavigate={navigate}
      audience={effectiveAudience}
      onAudienceChange={(next) =>
        go({
          // An administration user previewing the candidate side wants the
          // open-roles portal ("what candidates see"), not their own (empty)
          // application tracker — so preview lands on the portal. A real
          // candidate never uses this switch; they default to the tracker.
          audience: next,
          view: next === "applicant" ? "portal" : "dashboard",
          candidate: null,
        })
      }
      search={search}
      onSearchChange={setSearch}
    >
      {showView === "dashboard" ? (
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

      {showView === "jobs" ? (
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

      {showView === "candidates" ? (
        <CandidatesPage
          search={search}
          jobFilter={job}
          onJobFilterChange={(jobId) => go({ job: jobId })}
          openCandidateId={candidate}
          onOpenCandidate={(candidateId) => go({ candidate: candidateId })}
        />
      ) : null}

      {showView === "review" ? <ReviewPage search={search} /> : null}

      {showView === "interviews" ? <InterviewsPage search={search} /> : null}

      {showView === "access" ? <AccessControlPage /> : null}

      {showView === "myapps" ? (
        <MyApplicationsPage onBrowseRoles={() => navigate("portal")} />
      ) : null}

      {showView === "portal" ? <CandidatePortalPage search={search} /> : null}
    </AppShell>
  );
}
