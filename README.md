# Automated Hiring Process — AI Hiring Agent

An AI agent that automates the top of the recruitment funnel: a candidate applies, and the
system parses their resume, extracts structured data with a local LLM, scores them against
the job on both semantic and rule-based signals, decides whether they clear the bar, and
emails them the outcome — with a written, auditable rationale attached to every decision.

Built on **FastAPI**, **MongoDB**, **Qdrant**, **LangGraph** and **Ollama** — the AI runs
entirely on your own machine, so no resume ever leaves your infrastructure.

> **Quick links** — [Installation & running](INSTALLATION.md) ·
> [Architecture](ARCHITECTURE.md) · [19-module build plan](IMPLEMENTATION_PLAN.md)

---

## The problem this solves

A single job posting routinely draws hundreds of applications. What happens next is
familiar to every recruiter:

| The manual reality | The cost |
| --- | --- |
| A recruiter skims each resume for ~7 seconds | Good candidates are missed on formatting, not fit |
| Keyword search in an ATS | "React.js" fails to match "ReactJS"; synonyms and context are lost |
| Screening quality drifts across a long review session | The 150th resume is not judged like the 1st |
| "Why was this candidate rejected?" | Usually unanswerable after the fact |
| Most applicants never hear back | Employer-brand damage, and a poor candidate experience |
| Days pass before shortlisting | The strongest candidates accept another offer first |

Screening is high-volume, repetitive, rule-heavy work in which consistency matters more
than creativity. That is exactly the shape of work an agent should do — provided every
decision it makes can be explained.

---

## What this project does

```
   Candidate uploads a resume for a job
                 │
                 ▼
   ┌─────────────────────────────────┐
   │  1. Parse    PDF / DOCX -> text │
   ├─────────────────────────────────┤
   │  2. Extract  LLM -> name, email,│
   │              skills, experience,│
   │              education (JSON)   │
   ├─────────────────────────────────┤
   │  3. Embed    resume -> 768-dim  │
   │              vector in Qdrant   │
   ├─────────────────────────────────┤
   │  4. Score    similarity 50% +   │
   │              skills 30% +       │
   │              experience 20%     │
   ├─────────────────────────────────┤
   │  5. Explain  plain-English      │
   │              rationale + the    │
   │              matched/missing    │
   │              skill lists        │
   ├─────────────────────────────────┤
   │  6. Decide   LangGraph routes   │
   │              on a 70/100 bar    │
   ├─────────────────────────────────┤
   │  7. Notify   invitation or      │
   │              rejection email    │
   └─────────────────────────────────┘
                 │
                 ▼
   Recruiter opens a ranked, explained shortlist
```

Every application is judged by the **same criteria, in the same order, with the same
weights** — and the reasoning is stored alongside the score.

---

## How the scoring works

The screening score deliberately blends an AI signal with hard rules, so it is neither
keyword-blind nor a black box:

| Signal | Weight | What it measures | Why it is included |
| --- | --- | --- | --- |
| **Semantic similarity** | 50% | Cosine similarity between the resume embedding and the job-description embedding | Catches real fit that keyword search misses — "built REST APIs in Django" matches a Python backend role without sharing a single keyword |
| **Skill match** | 30% | Share of the job's required skills present on the resume | Hard requirements should be checked as hard requirements, not inferred |
| **Experience** | 20% | Years of experience against the job minimum, pro-rated below the bar | A near-miss on seniority should cost a candidate some points, not disqualify them |

```
screening_score = 0.5 x semantic_similarity + 0.3 x skill_score + 0.2 x experience_score
```

Candidates at or above **70/100** are invited; below it they are rejected. Both the
weights ([app/services/screening_service.py](app/services/screening_service.py)) and the
threshold ([app/agent/graph.py](app/agent/graph.py)) are single constants you can tune to
your own funnel.

**Sample output** from `GET /applications/{id}/screening`:

```json
{
  "candidate_name": "Shankar Ghimire",
  "screening_score": 78.4,
  "semantic_similarity": 71.2,
  "skill_score": 75.0,
  "experience_score": 100.0,
  "matched_skills": ["fastapi", "mongodb", "python"],
  "missing_skills": ["docker"],
  "rationale": "Candidate scored 78.4/100. Semantic resume-job similarity was 71.2%. Matched 3 of 4 required skills. Missing required skills: docker. Candidate has approximately 3 years of experience against a minimum of 2 years."
}
```

That `rationale` field is the point of the whole design: a recruiter — or an auditor, or
the candidate — can be told exactly why the score is what it is.

---

## Using it in a real hiring workflow

### 1. Recruiter posts a job

```bash
POST /jobs/
{
  "title": "Backend Python Engineer",
  "description": "Build and maintain FastAPI services, MongoDB data models and async pipelines.",
  "required_skills": ["python", "fastapi", "mongodb", "docker"],
  "minimum_experience": 2
}
```

`required_skills` and `minimum_experience` become the objective half of the score — so
write them as the genuine bar for the role, not a wish list.

### 2. Applications arrive

```bash
POST /applications/    job_id + resume file (PDF or DOCX)
```

Wire this to a careers page form, an email-inbox watcher, or an ATS webhook. The applicant
gets an instant confirmation response and a "we received your application" email; all the
heavy work happens in the background.

### 3. Screening happens automatically

Within seconds each candidate has: structured profile data, a stored resume vector, four
scores, matched and missing skill lists, and a written rationale — queryable at
`GET /applications/{id}/screening`.

### 4. The agent decides and notifies

```bash
POST /hiring/candidates/{id}/screen
```

The LangGraph agent routes the candidate to the reject or invite path, records the decision
on their record, and sends the matching email. Every applicant hears back — which is more
than most manual processes manage.

### 5. The recruiter works a shortlist, not a slush pile

Instead of reading 300 resumes, the recruiter opens a scored, explained, ranked list and
spends their time on the candidates who cleared the bar.

---

## What it is good for

- **High-volume roles** — the more applications per posting, the larger the payoff.
- **Consistency and defensibility** — identical criteria applied to every applicant, with
  a stored rationale, matters for internal review and for regulated hiring.
- **Speed to shortlist** — reduces days of screening to seconds per candidate.
- **Candidate experience** — nobody falls into a black hole; every applicant is answered.
- **Skill-gap visibility** — `missing_skills` aggregated across a posting tells you
  whether the requirements are realistic for your market.
- **Data privacy** — extraction and embeddings run locally through Ollama; resumes and
  personal data stay on your own infrastructure. No third-party AI vendor sees them.

## What it is not

- **Not an autonomous hiring decision-maker.** It screens; a person hires. The target
  design ([ARCHITECTURE.md](ARCHITECTURE.md)) puts an explicit human-in-the-loop interrupt
  before any final decision, and that is the intended end state.
- **Not a bias eliminator.** It applies consistent criteria, which removes *drift*, but a
  biased job description or skill list produces biased screening at scale. Review the
  criteria, and audit `missing_skills` and rejection patterns regularly.
- **Not appearance- or personality-scoring.** The planned interview stage scores **what a
  candidate says**, transcribed to text — never facial expression or tone. Content-based
  scoring is what actually predicts fit, and it is the only kind that can be explained.
- **Not compliance advice.** Automated screening is regulated differently across
  jurisdictions (EU AI Act, NYC Local Law 144, and others). Confirm your obligations —
  candidate notice, audit trails, human review — before using this on real applicants.

---

## Technology

| Component | Choice | Rationale |
| --- | --- | --- |
| API | **FastAPI** | Async throughout, automatic OpenAPI docs, Pydantic validation |
| Records | **MongoDB** | Candidate documents change shape as the pipeline progresses |
| Vectors | **Qdrant** | Purpose-built vector search with payload filtering |
| Orchestration | **LangGraph** | Explicit state, conditional routing, and durable interrupts for human review |
| LLM | **Ollama + `qwen3.5:4b`** | Local, free per token, JSON-mode structured output |
| Embeddings | **Ollama + `nomic-embed-text`** | Local 768-dim embeddings, strong on document similarity |
| Email | **aiosmtplib** | Async SMTP that does not block the request path |
| Files | **pypdf / python-docx** | The two formats that cover almost every resume |

---

## Getting started

Full instructions — prerequisites, services, environment variables, an end-to-end
walkthrough and troubleshooting — are in **[INSTALLATION.md](INSTALLATION.md)**.

The short version:

```bash
uv sync                                              # install dependencies
docker compose up -d --wait                          # MongoDB + Qdrant
ollama pull nomic-embed-text && ollama pull qwen3.5:4b
cp .env.example .env                                 # then fill in SMTP details
uv run uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/docs>.

---

## API at a glance

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe |
| `POST` | `/jobs/` | Create a job posting |
| `GET` | `/jobs/` | List job postings |
| `POST` | `/applications/` | Submit a resume against a job (starts the pipeline) |
| `GET` | `/applications/{id}/vector` | Inspect the stored resume embedding |
| `GET` | `/applications/{id}/screening` | Scores, matched/missing skills, rationale |
| `POST` | `/hiring/candidates/{id}/screen` | Run the agent — decision + email |

---

## Project status

**11 of 19 planned modules are built** — the complete intake-to-screening-decision path
runs end to end today.

**Working now**

- FastAPI service with health checks and lifespan-managed database connections
- Job posting create/list
- Resume upload (PDF/DOCX) with validation and non-blocking background processing
- Resume text extraction and cleanup
- LLM structured extraction into a validated Pydantic model
- 768-dimension embeddings stored in Qdrant with deterministic, re-runnable point ids
- Blended screening score with four sub-scores and a written rationale
- LangGraph agent with conditional reject/invite routing on a configurable threshold
- Transactional emails at every stage, with delivery status tracked per candidate

**Planned next** (Modules 11–19)

- Structured video interview: fixed question sets, expiring invite links, browser recording
- Audio extraction and transcription with faster-whisper
- Rubric-based interview scoring — every score backed by a quote from the transcript
- Aggregated scorecards with flags for answers a human should look at
- **Human-in-the-loop interrupt**: the graph pauses and nobody is accepted or rejected
  until a person acts
- Chainlit recruiter dashboard with Approve / Override controls that resume the paused graph
- LLM tracing, a pytest suite, and one-command Docker packaging

See [ARCHITECTURE.md](ARCHITECTURE.md) for the proposed-versus-delivered breakdown, and
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the full module-by-module plan.

---

## Repository layout

```
app/
├─ main.py          FastAPI app, lifespan, routers
├─ agent/graph.py   LangGraph hiring agent
├─ core/            settings + logging
├─ db/              MongoDB and Qdrant clients
├─ models/          Mongo document builders
├─ routes/          jobs · applications · hiring
├─ schemas/         Pydantic request/response models
├─ services/        parsing · extraction · embeddings · scoring · email
└─ test/            standalone verification scripts
```

---

## A note on responsible use

This system decides who advances in a hiring process, which makes it consequential for
real people. Three habits keep it honest:

1. **Read the rationales.** Spot-check rejected candidates regularly — if a rationale does
   not justify its score, the criteria or the weights need fixing.
2. **Treat the threshold as a policy choice.** `SCREENING_THRESHOLD = 70` is a default, not
   a truth. Tune it against outcomes you can observe.
3. **Keep a human in the loop for final decisions.** Screening out is reversible when a
   person reviews the shortlist; automated rejection with nobody watching is not.
