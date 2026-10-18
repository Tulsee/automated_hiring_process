# Hirewise — UI design plan

The frontend for the automated hiring pipeline. Light SaaS, white/navy/violet,
serving two audiences from one codebase: recruiters who decide, and applicants
who are being assessed.

The governing product rule, which every decision below follows from:

> **The model recommends. A person decides.** Nothing in this UI presents an AI
> output as a verdict, and no score appears without the evidence it rests on.

---

## 1. Information architecture

Two audiences, one shell. The sidebar swaps its navigation rather than the app
switching to a different build, so a recruiter can open the candidate view and
see exactly what applicants see.

```
Sign in  ──▶  Administration workspace          Candidate view
              ├── Dashboard        overview      └── Open roles   browse + apply
              ├── Jobs             roles+rubric
              ├── Candidates       ranked list
              ├── Review queue     the decision screen
              ├── Interviews       pipeline ops
              └── Access control   roles, permissions, users
```

Nothing but the invite-link interview page and the login screen renders
without a signed-in user. An administration user sees the workspace; a
candidate sees the portal. Navigation entries are filtered by permission — a
`viewer` never sees "Access control", and the superadmin sees everything.

### Why these five

Each recruiter screen answers one question:

| Screen | The question it answers | Primary endpoint |
|---|---|---|
| Dashboard | What needs my attention today? | `/applications/`, `/interviews/sessions` |
| Jobs | What are we hiring for, and on what standard? | `/jobs/` |
| Candidates | Who applied, and how do they compare? | `/applications/` |
| Review queue | Should this person go forward? | `/interviews/sessions/{id}/scorecard` |
| Interviews | What is stuck in the pipeline? | `/interviews/sessions` |
| Access control | Who may do what? | `/auth/roles`, `/auth/users`, `/auth/permissions` |

## Authentication and permissions

Auth state lives in `AuthContext` (`src/auth/`). It holds the signed-in user,
mirrors the bearer token into the API client so every request carries it, and
persists the token to `localStorage` so a reload keeps the session. A 401 on a
request that carried a token (an expired session) signs the user out wherever
it happened.

The single gate the UI asks is `can(permission)`: true for the superadmin
always, true for an administration user whose role grants it, false otherwise.
Components use it to hide what a user cannot do — the per-row candidate
actions, the job editor, the Access control section. **This is clarity, not
security**: the server gates every administration endpoint independently, so a
hidden control is a convenience, and reaching its API directly still returns
403.

The login screen (`LoginPage`) serves both audiences: administration users
sign in, candidates sign in or self-register. Registration only ever calls
`/auth/register`, which the server restricts to candidate accounts, so the
public signup cannot mint an administration user.

Access control (`AccessControlPage`) is where the superadmin builds the model:
create a role, tick the permissions it grants, then create users and assign a
role. It shows only the sections the viewer may use (`roles:manage` /
`users:manage`).

**Interviews is separate from Review deliberately.** Reviewing is a judgement
task; transcribing and scoring are operational chores with prerequisites
(submitted → transcribed → scored). Mixing them puts a "run transcription"
button next to a hiring decision, which is the wrong mental mode.

### Navigation model

State-driven, via `<button>` elements, because the stylesheet's `.nav-item` is a
button and the active state is styled with `.nav-item--active`.

Navigation state lives in the **query string**, so Back, Forward, a mouse's
side buttons, a reload and a pasted link all work:

    /dashboard/?view=candidates&candidate=<id>&job=<id>&audience=applicant

Defaults are omitted, so a plain `/dashboard/` is the recruiter dashboard.
Opening a candidate's dialog is a navigation, which means Back closes the
dialog rather than leaving the page.

**Why the query string and not paths:** the app is served from `/dashboard/` by
`StaticFiles`, which serves `index.html` for a directory but not for an
arbitrary sub-path — `/dashboard/candidates` returns 404 on reload, while
`/dashboard/?view=candidates` cannot. Six flat views also do not need a router
dependency. If nested routes are ever wanted, `react-router-dom` plus a
catch-all route on the backend is the upgrade; the pages take their inputs as
props and would not change.

---

## 2. Design tokens

All defined on `:root` in `src/styles.css`. Components reference the token, never
the hex.

### Colour

| Token | Value | Role |
|---|---|---|
| `--navy` | `#172554` | Sidebar, headings |
| `--navy-2` | `#20356c` | Sidebar gradient end |
| `--ink` | `#17213c` | Body text |
| `--muted` | `#75819a` | Secondary text |
| `--violet` | `#6554e8` | Primary action, AI affordances |
| `--violet-dark` | `#5141ce` | Primary hover |
| `--teal` | `#0f8a76` | Positive / verified |
| `--border` | `#e5eaf3` | Hairlines |
| `--surface` | `#fff` | Cards |
| `--bg` | `#f6f8fc` | Page |
| `--shadow` | `0 4px 18px var(--shadow-color)` | Card lift |

Those are the light theme's values. There are 41 tokens in all; the table shows
the ones worth knowing by name. **Every colour in `styles.css` is a token**, so
a theme is a block that re-points tokens rather than a second stylesheet.

### Themes

| Theme | `data-theme` | Character |
|---|---|---|
| System | *(absent)* | Follows `prefers-color-scheme` |
| Light | `light` | The original white/navy/violet |
| Dark | `dark` | Neutral slate |
| Midnight | `midnight` | Deep navy, keeps the brand's blue cast |
| Warm | `warm` | Paper tones for long reading |
| High contrast | `contrast` | Black on white, heavier borders, outlined pills |

The theme is set as `data-theme` on `<html>` (so the sidebar, scrollbars and
page background follow) and persisted to `localStorage`. "System" removes the
attribute entirely, which is what lets the stylesheet's `prefers-color-scheme`
block apply — hence it is the default.

`color-scheme` is declared per theme so native form controls and scrollbars
match.

**Contrast is checked, not assumed.** Fifteen text/background pairs were
measured in all six themes; body and muted text clear 4.5:1 and meta text
clears 3:1 everywhere. Doing this surfaced that three of the original design's
status-pill inks (teal, amber, blue) sat at 3.6–4.3:1 on their own soft
backgrounds, below the 4.5:1 small-text bar — they were darkened slightly.

**Violet means AI.** It is used for the brand mark, the AI promo panel, scores,
and the `.notice` block — so "this number came from a model" is learnable as a
visual convention. Teal means verified/positive; amber means *look at this*; it
is never used to mean "bad candidate", only "the system is unsure".

### Type

Two families: **Manrope** (700/800) for headings and numbers, **DM Sans**
(400–600) for everything else. Numbers carry weight 800 and tight tracking so a
score reads as a figure, not prose.

Base scale: `29/24/21` headings · `15` panel titles · `12–13` body · `10–11`
meta. Headline sizes use `clamp()` so they shrink on phones without a
breakpoint.

**Every size is multiplied by `--font-scale`.** The stylesheet writes
`font-size: calc(11px * var(--font-scale))`, so one custom property resizes the
whole product. The default is `1.15`, because the design's raw values were too
small to read comfortably; the appearance menu offers 1.0 / 1.15 / 1.3 / 1.45.

That is also why there are no `font:` shorthands left — they were expanded to
`font-weight` / `font-size` / `font-family` longhands, since `calc()` inside the
shorthand is unreliable.

### Spacing & shape

4px base. Cards `12px` radius, pills/buttons `6–9px`, modal `15px`. Panel padding
`19px`, tightening to `13px` under 700px.

### Breakpoints

`1200px` (narrow sidebar) · `940px` (sidebar becomes a drawer) · `700px`
(single column) · `430px` (two-up metrics, stacked pipeline).

`prefers-reduced-motion` kills all transitions.

---

## 3. Page layouts

### Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ Greeting + "New role"                                   │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ Candidates│ Avg score│ Submitted│ Flagged  │  4 metrics  │
├────────────────────────────────┬────────────────────────┤
│ Pipeline (4 stages + bars)     │ Review queue promo     │
│ Recent candidates (table)      │ What needs doing       │
│                                │ Quick actions          │
└────────────────────────────────┴────────────────────────┘
```

Metrics are **derived from the list endpoints**, not a bespoke stats API, so a
number on the dashboard always equals the rows you get when you click through.

### Review queue — the important one

```
┌──────────────────┬──────────────────────────────────────┐
│ Submitted (list) │ Candidate + role + status            │
│  ▸ flagged first │ ⚠ Needs a human look        ← FIRST  │
│  ▸ then by score │ AI recommendation  3.4/5             │
│                  │ By competency (weight, bar, flags)   │
│                  │ ▸ How was this calculated?           │
│                  │ ▸ Show the scoring rubric            │
│                  │ Evidence — quote per score           │
│                  │ Transcripts + recordings (accordion) │
│                  │ Your decision: Advance / Override /  │
│                  │                 Second opinion       │
└──────────────────┴──────────────────────────────────────┘
```

**Order is the design.** The review banner precedes the score, so a reviewer
learns the result is unreliable *before* anchoring on a number. Evidence sits
above the decision buttons, so the quotes are passed through on the way to the
action.

The queue sorts flagged interviews first, then by score — the list is ordered by
*what needs a human*, not by who scored best.

### Candidates

Toolbar (role · decision · sort) over a table. Score, experience, stage and
interview progress per row; click opens a detail modal with the screening
breakdown. Filtering is server-side so `total` is the true count; only free-text
name search is client-side, and the empty state says so.

### Jobs

Three-up cards: role, skills, candidate count, question count, min experience.
A role with zero applicants reads `draft` rather than `published`, so a role
nobody can see is visible to you.

### Candidate portal

Hero + search, a disclosure panel, then a vertical role list. The disclosure is
the point of the page: it is the only screen where the person being scored can
read how the scoring works.

---

## 4. AI recommendation patterns

These are the accessibility and honesty rules, implemented in
`src/components/AiRecommendation.tsx`.

### Never a number alone

```tsx
<AiScoreBlock scorecard={card} model="qwen3.5:4b" />
```

Renders the eyebrow `AI RECOMMENDATION`, the score with its scale, and a caption
naming the model and stating it is not a decision. The figure carries
`aria-label="AI recommended score 3.4 out of 5"` — `3.4` alone tells a
screen-reader user nothing.

### Every score shows its quote, and whether the quote is real

`EvidenceItem` renders the model's `evidence_quote` inside `<q>`, with a tick
when `quote_verified` is true and a warning when it is not — plus a sentence
saying which:

- *"Quote verified against the transcript."*
- *"This quote could not be found in the transcript."*
- *"Score not backed by a quote."*

An unverified quote is **shown, not hidden**. The backend verifies quotes because
models fabricate them; the UI's job is to surface that, since a score whose
evidence cannot be located is a score you cannot defend.

### Uncertainty is content, not an error

`FLAG_COPY` in `src/lib/flags.ts` maps every backend flag to a recruiter-readable
sentence. `empty_answer` becomes *"No speech was recorded, so this question was
not scored."* Flags render as chips and in the review banner — never as a silent
omission.

### The arithmetic is openable

`WeightingDisclosure` prints a table of score × weight → contribution, totalling
to the overall score, plus which competencies were excluded and why. A reviewer
can redo the sum by hand. `RubricDisclosure` shows the 1–5 descriptors the score
was judged against.

### Colour is never the only signal

Every `.status` pill pairs its colour with a word and a `::before` dot. Every
progress bar has an `aria-label` spelling out the value. Verified/unverified
differ by icon *and* sentence, not just green/amber.

### Decisions that don't work yet say so

The Approve / Override buttons record a local choice and print: *"Nothing was
sent — the decision step needs the pipeline's human-in-the-loop hook."* A button
that looks live but isn't is worse than one that admits it.

---

## 5. Component inventory

```
src/
├── types.ts                  API response types, grouped by endpoint
├── api/client.ts             typed fetch wrapper; ApiError; FastAPI detail parsing
├── hooks/useApi.ts           useApi (fetch + derived loading), useAction (mutations)
├── lib/
│   ├── format.ts             formatDate, formatSeconds, humanise, initials
│   ├── flags.ts              flagLabel — plain-language flag copy
│   └── nav.ts                ViewId, RECRUITER_NAV, APPLICANT_NAV
├── components/
│   ├── Icon.tsx              28 inline SVGs, currentColor, aria-hidden by default
│   ├── primitives.tsx        Avatar · StatusPill · Panel · MetricCard ·
│   │                         ProgressBar · Notice · HelperText · Loading ·
│   │                         ErrorState · EmptyState · Modal
│   ├── AppShell.tsx          sidebar + topbar + footer, "/" search shortcut,
│   │                         skip link, mobile drawer; PageHeader
│   └── AiRecommendation.tsx  AiScoreBlock · CompetencyRow · EvidenceList ·
│                             ReviewBanner · WeightingDisclosure ·
│                             RubricDisclosure · ScreeningBreakdown ·
│                             SkillChips · ScoreCell · FlagList
└── pages/                    Dashboard · Jobs · Candidates · Review ·
                              Interviews · CandidatePortal
```

### Conventions

- **Components render existing class names.** No new CSS was added;
  `styles.css` stays the single source of visual truth. The few inline styles
  are one-off layout nudges, each next to the thing it adjusts.
- **Helpers live outside component files.** React's fast-refresh lint rule
  requires a module to export only components, hence `src/lib/`.
- **Pages take their inputs as props.** No page reads global state directly,
  which is what makes adding a router later a mechanical change.

### `useApi`, and why `loading` is derived

```tsx
const list = useApi(() => api.listCandidates({ job_id }), [job_id]);
```

`loading` is computed by comparing the current request key with the key of the
last settled result, rather than being its own state. That keeps every
`setState` inside an async callback instead of an effect body (React 19's
`set-state-in-effect` rule), and makes stale responses impossible to render: a
result tagged with an old key is simply not current.

---

## 6. Accessibility decisions

| Concern | What was done |
|---|---|
| Keyboard | Skip link to `#main`; `/` focuses search; `Escape` closes drawer and modals; every control is a real `<button>` |
| Focus | `:focus-visible` 3px indigo ring with offset, inherited from `styles.css` |
| Async regions | `Loading` uses `role="status" aria-live="polite"`; `ErrorState` and the review banner use `role="alert"` |
| Current page | `aria-current="page"` on the active nav item |
| Tables | `<caption class="sr-only">` describing each table; `scope="col"` on headers |
| Numbers | Scores carry `aria-label` with the scale; progress bars use `role="progressbar"` with min/now/max |
| Icons | `aria-hidden` by default; `title` only when an icon is a control's sole content |
| Images | Avatars are monograms marked `aria-hidden`, since the adjacent text names the person |
| Motion | `prefers-reduced-motion` honoured by the stylesheet |
| Video | `<video controls preload="none">` with an explicit "no captions available" track, so the gap is declared rather than implied |

**Known gap:** the modal does not trap focus or restore it on close. It sets
`role="dialog" aria-modal="true"` and closes on Escape and backdrop click, but a
keyboard user can tab out of it. Fixing that properly needs a focus-trap
(≈30 lines or a small dependency) and is the first accessibility item I would
pick up.

---

## 7. Running it

```bash
cd Frontend
npm install
npm run dev                  # http://localhost:5173/dashboard/
```

Dev serves at `/dashboard/` (the same base as production) and proxies `/jobs`,
`/applications`, `/interviews`, `/hiring` and `/health` to
`http://127.0.0.1:8000`. Override with
`VITE_API_TARGET=http://127.0.0.1:8090 npm run dev`.

```bash
npm run build                # → ../app/static/dashboard
```

FastAPI mounts that directory at `/dashboard`, so the production app is
same-origin with the API and needs no CORS. Requests use relative paths, so dev
and production need no base-URL switching.

**The candidate interview page is deliberately not part of this app.**
`app/static/interview.html` stays vanilla — it is a single-purpose page a
candidate opens once from an invite link, and wrapping `MediaRecorder` in React
would add a build step for no benefit.

---

## 8. What is not built

- **Auth.** Every screen assumes a trusted viewer. The sidebar user is hardcoded.
- **Working decisions.** Approve/Override need Module 17's graph interrupt.
- **Notifications.** The bell is decorative.
- **Focus trap in modals.** See the accessibility gap above.
