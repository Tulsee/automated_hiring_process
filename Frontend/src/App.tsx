import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import type { ViewId } from "./lib/nav";
import { useUrlState } from "./hooks/useUrlState";
import { applyStoredTheme } from "./hooks/useTheme";
import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/context";
import { Loading } from "./components/primitives";
import { LoginPage } from "./pages/LoginPage";
import { PublicBoardPage } from "./pages/PublicBoardPage";
import { currentEntry } from "./lib/entry";
import { DashboardPage } from "./pages/DashboardPage";
import { JobsPage } from "./pages/JobsPage";
import { CandidatesPage } from "./pages/CandidatesPage";
import { ReviewPage } from "./pages/ReviewPage";
import { InterviewsPage } from "./pages/InterviewsPage";
import { AccessControlPage } from "./pages/AccessControlPage";
import { CandidatePortalPage } from "./pages/CandidatePortalPage";
import { MyApplicationsPage } from "./pages/MyApplicationsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { InterviewPage } from "./pages/InterviewPage";

export default function App() {
  // Apply the theme for every screen, including the public pages that render
  // outside the shell (where the interactive `useTheme` does not run).
  useEffect(() => {
    applyStoredTheme();
  }, []);

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
    // Anonymous: the job board is public; the two login URLs show the right
    // sign-in. Browsing needs no account — only applying does.
    const entry = currentEntry();

    if (entry === "admin") return <LoginPage audience="admin" />;
    if (entry === "apply") return <LoginPage audience="candidate" />;

    return <PublicBoardPage />;
  }

  return <Workspace />;
}

function Workspace() {
  const { can, isAdministration, isSuperadmin } = useAuth();

  // Navigation lives in the URL, so Back, Forward, a mouse's side buttons and
  // a reload all work. See `useUrlState`.
  const { view, candidate, job, go } = useUrlState();

  // Search is deliberately *not* in the URL: a history entry per keystroke
  // would make Back useless. It resets when the page changes.
  const [search, setSearch] = useState("");

  const [createJobOpen, setCreateJobOpen] = useState(false);

  // Administration users work in the recruiter workspace; candidates get the
  // applicant side. There is no "preview the candidate view" switch anymore.
  const effectiveAudience = isAdministration ? "recruiter" : "applicant";

  function navigate(next: ViewId) {
    go({ view: next, candidate: null });
    setSearch("");
  }

  // A view the user is not allowed to see (a role lacking the permission, or a
  // candidate) falls back to one they can: the dashboard for administration,
  // their application tracker for a candidate.
  const home: ViewId = isAdministration ? "dashboard" : "myapps";

  // A candidate has their tracker, the open roles, and their profile. Anything
  // else (e.g. a stale ?view from the recruiter side) lands on the tracker.
  const APPLICANT_VIEWS: ViewId[] = ["myapps", "portal", "profile"];

  function adminView(requested: ViewId): ViewId {
    if (requested === "access" && !can("roles:manage") && !can("users:manage")) {
      return home;
    }
    if (requested === "approvals" && !isSuperadmin) return home;
    return requested;
  }

  const showView =
    effectiveAudience === "applicant"
      ? APPLICANT_VIEWS.includes(view)
        ? view
        : home
      : adminView(view);

  return (
    <AppShell
      view={showView}
      onNavigate={navigate}
      audience={effectiveAudience}
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

      {showView === "profile" ? <ProfilePage /> : null}

      {showView === "approvals" ? <ApprovalsPage /> : null}
    </AppShell>
  );
}
