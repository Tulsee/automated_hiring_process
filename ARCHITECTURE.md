# Architecture

Two views of the system:

1. **[Proposed architecture](#1-proposed-architecture-target-state):** the complete target
   design from [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): intake → screening →
   video interview → transcription → rubric scoring → human-in-the-loop decision.
2. **[Delivered architecture](#2-delivered-architecture-what-runs-today):** what is
   actually built and running today (Modules 1-10).

A [gap table](#3-proposed-vs-delivered) at the end maps one onto the other.

---

## 1. Proposed architecture (target state)

### 1.1 System context

```
                    ┌────────────────────────────────────────┐
                    │              ACTORS                    │
                    ├──────────────┬─────────────────────────┤
                    │  Candidate   │        Recruiter / HR   │
                    └──────┬───────┴──────────┬──────────────┘
                           │                  │
            applies, records interview   reviews & decides
                           │                  │
                           ▼                  ▼
    ┌───────────────────────────────────────────────────────────────┐
    │                    FastAPI application                        │
    │   /jobs  /applications  /interviews  /hiring  /review         │
    └───────────────────────────────┬───────────────────────────────┘
                                    │
                                    ▼
    ┌───────────────────────────────────────────────────────────────┐
    │              LangGraph hiring agent (orchestrator)            │
    │   durable state · conditional routing · human interrupt       │
    └───┬───────────────┬───────────────┬───────────────┬───────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
   ┌─────────┐    ┌──────────┐   ┌────────────┐  ┌──────────────┐
   │ MongoDB │    │  Qdrant  │   │   Ollama   │  │faster-whisper│
   │ records │    │ vectors  │   │  LLM+embed │  │     STT      │
   └─────────┘    └──────────┘   └────────────┘  └──────────────┘
```

### 1.2 Target end-to-end pipeline

```
   Candidate applies
          │
          ▼
   ┌──────────────────┐
   │  Intake          │  resume upload + job_id, file stored, record created
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │  Resume parsing  │  PDF / DOCX  ->  clean plain text
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │  LLM extraction  │  text -> {name, email, skills, experience, education}
   └────────┬─────────┘
            ▼
       ┌────┴────┐
       ▼         ▼
  ┌─────────┐ ┌──────────────┐
  │ MongoDB │ │  Embedding   │  resume vector
  │ record  │ │      ↓       │
  │         │ │   Qdrant     │
  └────┬────┘ └──────┬───────┘
       └──────┬──────┘
              ▼
   ┌──────────────────────────────────────────┐
   │  Screening node                          │
   │  semantic similarity + skill match +     │
   │  experience rules -> score + rationale   │
   └────────────────┬─────────────────────────┘
                    │
        ┌───────────┴────────────┐
   below bar                above bar
        │                        │
        ▼                        ▼
  ┌───────────┐          ┌────────────────────┐
  │  Reject   │          │ Invite to interview│  expiring link + session
  └─────┬─────┘          └─────────┬──────────┘
        │                          ▼
        │                ┌────────────────────┐
        │                │  Video interview   │  fixed questions,
        │                │  (MediaRecorder)   │  one recording per answer
        │                └─────────┬──────────┘
        │                          ▼
        │                ┌────────────────────┐
        │                │  Audio extraction  │  ffmpeg
        │                │  + transcription   │  faster-whisper
        │                └─────────┬──────────┘
        │                          ▼
        │                ┌────────────────────┐
        │                │  Rubric scoring    │  per answer:
        │                │  (LLM + rubric)    │  {competency, score,
        │                │                    │   evidence_quote, reasoning}
        │                └─────────┬──────────┘
        │                          ▼
        │                ┌────────────────────┐
        │                │  Scorecard         │  weighted aggregate + flags
        │                │  aggregation       │
        │                └─────────┬──────────┘
        │                          ▼
        │           ╔══════════════════════════════════╗
        │           ║   HUMAN-IN-THE-LOOP INTERRUPT    ║
        │           ║   graph pauses — nobody is hired ║
        │           ║   or rejected without a person   ║
        │           ╚══════════════┬═══════════════════╝
        │                          ▼
        │                ┌────────────────────┐
        │                │ Chainlit dashboard │  Approve / Override /
        │                │ scorecard, quotes, │  Take another look
        │                │ transcript, flags  │
        │                └─────────┬──────────┘
        │                          ▼
        └──────────────────►┌────────────────────┐
                            │  Final decision    │
                            │  + candidate email │
                            └────────────────────┘
```

### 1.3 Target layer breakdown

| Layer                   | Responsibility                                                  | Technology                                  |
| ----------------------- | --------------------------------------------------------------- | ------------------------------------------- |
| **Interface**     | Candidate application + interview UI; recruiter review UI       | FastAPI, browser`MediaRecorder`, Chainlit |
| **API**           | REST endpoints, validation, background task dispatch            | FastAPI, Pydantic                           |
| **Orchestration** | Multi-step hiring workflow, routing, durable interrupts         | LangGraph                                   |
| **AI services**   | Structured extraction, embeddings, rubric scoring               | Ollama (LLM +`nomic-embed-text`)          |
| **Speech**        | Audio extraction and transcription of answers                   | ffmpeg + faster-whisper                     |
| **Records**       | Jobs, candidates, sessions, transcripts, scorecards, agent logs | MongoDB                                     |
| **Vectors**       | Resume embeddings, semantic job–candidate similarity           | Qdrant                                      |
| **Notification**  | Received / reject / invite / final-decision emails              | aiosmtplib (SMTP)                           |
| **Observability** | Structured logging, LLM tracing, replayable decisions           | logging`dictConfig`, LangSmith            |
| **Packaging**     | One-command startup of the whole stack                          | Docker / docker-compose                     |

### 1.4 Target data model

```
jobs                candidates                 interview_sessions
────                ──────────                 ──────────────────
_id                 _id                        _id
title               job_id ────────────────┐   candidate_id ──────┐
description         resume_filename        │   job_id             │
required_skills     resume_path            │   status             │
minimum_experience  name / email           │   invite_token       │
created_at          skills[]               │   expires_at         │
updated_at          years_of_experience    │   answers[]          │
                    education[]            │     ├─ question_id   │
                    status                 │     ├─ media_path    │
                    screening_score        │     ├─ transcript    │
                    semantic_similarity    │     └─ scores[]      │
                    skill_score            │   scorecard          │
                    experience_score       │   flags[]            │
                    matched_skills[]       │   created_at         │
                    missing_skills[]       │                      │
                    screening_rationale    │   agent_logs         │
                    decision               │   ──────────         │
                    decision_message       │   _id                │
                    email_status           │   candidate_id ──────┘
                    created_at / updated_at│   node / state / ts
                                           │
                    Qdrant: candidates ────┘
                    point_id = uuid5(candidate_id)
                    vector  = 768-dim resume embedding
                    payload = {candidate_id, job_id, name, email, skills}
```

---

## 2. Delivered architecture (what runs today)

Everything in this section is implemented, wired up and runnable.

### 2.1 Runtime view

```
                          ┌──────────────────┐
       HTTP client  ────► │   FastAPI app    │  app/main.py
   (curl / Swagger)       │  lifespan hooks  │
                          └────────┬─────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       ▼                           ▼                           ▼
┌──────────────┐          ┌──────────────────┐        ┌────────────────┐
│  /jobs       │          │  /applications   │        │  /hiring       │
│  routes/     │          │  routes/         │        │  routes/       │
│  jobs.py     │          │  applications.py │        │  hiring.py     │
└──────┬───────┘          └────────┬─────────┘        └───────┬────────┘
       │                           │                          │
       │                  BackgroundTasks                      │
       │                           ▼                          ▼
       │              ┌──────────────────────────┐   ┌──────────────────┐
       │              │  candidate_processor.py  │   │ agent/graph.py   │
       │              │  (async pipeline)        │   │ (LangGraph)      │
       │              └────────────┬─────────────┘   └────────┬─────────┘
       │                           │                          │
       └───────────┬───────────────┴──────────────┬───────────┘
                   ▼                              ▼
          ┌─────────────────┐            ┌──────────────────┐
          │    MongoDB      │            │     Qdrant       │
          │ jobs,candidates │            │   candidates     │
          └─────────────────┘            └──────────────────┘
                   ▲                              ▲
                   │                              │
          ┌────────┴──────────────────────────────┴────────┐
          │                  Ollama                        │
          │   qwen3.5:4b (extraction) · nomic-embed-text    │
          └────────────────────────────────────────────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ SMTP (aiosmtplib)│
                          │ candidate emails │
                          └──────────────────┘
```

### 2.2 Implemented application pipeline

Triggered by `POST /applications/`, executed as a FastAPI background task in
[app/services/candidate_processor.py](app/services/candidate_processor.py):

```
POST /applications/  (job_id + resume file)
        │
        │  validate job_id · validate PDF/DOCX content-type
        │  save file to uploads/ · insert candidate {status: "received"}
        │  return 200 immediately
        ▼
  ── background task ─────────────────────────────────────────────
        │
        ▼  status: "processing"
  ┌───────────────────────────────────────────┐
  │ resume_parser.extract_resume_text()       │  pypdf / python-docx
  │   PDF|DOCX -> clean_text()                │  whitespace normalised
  │   (run via asyncio.to_thread)             │
  └────────────────────┬──────────────────────┘
                       ▼
  ┌───────────────────────────────────────────┐
  │ llm_extractor.extract_candidate_data()    │  Ollama qwen3.5:4b
  │   format="json", think=False              │  JSON mode
  │   -> CandidateExtraction (Pydantic)       │  validated, not trusted raw
  └────────────────────┬──────────────────────┘
                       ▼  persist name/email/skills/experience/education
  ┌───────────────────────────────────────────┐
  │ embedding_service.generate_embedding()    │  nomic-embed-text -> 768 dims
  └────────────────────┬──────────────────────┘
                       ▼
  ┌───────────────────────────────────────────┐
  │ qdrant_service.store_candidate_embedding()│  upsert PointStruct
  │   id = uuid5(NAMESPACE_OID, candidate_id) │  deterministic -> re-runnable
  │   payload = {candidate_id, job_id, name,  │
  │              email, skills}               │
  └────────────────────┬──────────────────────┘
                       ▼
  ┌───────────────────────────────────────────┐
  │ candidate_screening.screen_candidate()    │  see 2.3
  │   -> score, sub-scores, matched/missing,  │
  │      human-readable rationale             │
  └────────────────────┬──────────────────────┘
                       ▼  persist screening fields
  ┌───────────────────────────────────────────┐
  │ email_service.send_application_received() │  email_status:
  │                                           │  sent | failed | not_found
  └────────────────────┬──────────────────────┘
                       ▼
                 status: "processed"

  Any exception  ->  status: "error", error message stored on the candidate
```

### 2.3 Implemented scoring model

[app/services/screening_service.py](app/services/screening_service.py) +
[app/services/candidate_screening.py](app/services/candidate_screening.py):

```
  ┌──────────────────────────┐
  │ Job text                 │  title + description + required skills
  │   -> embedding           │
  └────────────┬─────────────┘
               │  Qdrant query_points, filtered to this candidate_id
               ▼
  ┌──────────────────────────┐
  │ semantic_similarity      │  cosine score, clamped to 0..100
  └──────────────────────────┘            weight 0.50
  ┌──────────────────────────┐
  │ skill_score              │  |matched| / |required| * 100
  │                          │  case-insensitive set intersection
  └──────────────────────────┘            weight 0.30
  ┌──────────────────────────┐
  │ experience_score         │  100 if candidate >= minimum
  │                          │  else pro-rata; 0 if unknown
  └──────────────────────────┘            weight 0.20
               │
               ▼
      screening_score = 0.5*similarity + 0.3*skills + 0.2*experience
               │
               ▼
      rationale: plain-English sentence naming the score, the similarity %,
      the matched/missing required skills, and years vs. minimum
```

Every score is stored on the candidate document and exposed at
`GET /applications/{id}/screening`, so no decision is a black box.

### 2.4 Implemented LangGraph agent

[app/agent/graph.py](app/agent/graph.py) — `POST /hiring/candidates/{id}/screen`:

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         ▼
              ┌────────────────────────┐
              │    screening_node      │
              │  load candidate + job  │
              │  hydrate HiringState:  │
              │   job_id, job_title,   │
              │   name, email,         │
              │   score, rationale     │
              │  raises if unscreened  │
              └───────────┬────────────┘
                          ▼
                ┌───────────────────┐
                │ route_after_       │   conditional edge
                │ screening(state)   │   SCREENING_THRESHOLD = 70.0
                └─────┬────────┬─────┘
             score<70 │        │ score>=70
                      ▼        ▼
          ┌────────────────┐  ┌───────────────────────┐
          │  reject_node   │  │     invite_node       │
          │                │  │                       │
          │ decision:      │  │ decision:             │
          │  "reject"      │  │  "invite_to_interview"│
          │ write message  │  │ write message         │
          │ send rejection │  │ send invitation email │
          │  email         │  │                       │
          │ email status:  │  │ email status:         │
          │ sent/failed/   │  │ sent/failed/skipped   │
          │ skipped        │  │                       │
          └───────┬────────┘  └───────────┬───────────┘
                  └───────────┬───────────┘
                              ▼
                          ┌───────┐
                          │  END  │
                          └───────┘
```

`HiringState` (a `TypedDict`) carries `candidate_id`, `job_id`, `job_title`,
`candidate_name`, `candidate_email`, `screening_score`, `screening_rationale`, `decision`
and `message` through every node. Email failures are caught and recorded on the candidate
(`decision_email_status`, `decision_email_error`) rather than failing the graph run.

### 2.5 Implemented data model

**MongoDB — `jobs`**

| Field                           | Type     |
| ------------------------------- | -------- |
| `_id`                         | ObjectId |
| `title`                       | string   |
| `description`                 | string   |
| `required_skills`             | string[] |
| `minimum_experience`          | float    |
| `created_at` / `updated_at` | datetime |

**MongoDB — `candidates`**

| Field                                                          | Type                                                         | Written by      |
| -------------------------------------------------------------- | ------------------------------------------------------------ | --------------- |
| `_id`                                                        | ObjectId                                                     | intake          |
| `job_id`                                                     | string                                                       | intake          |
| `resume_filename`, `resume_path`                           | string                                                       | intake          |
| `status`                                                     | `received` → `processing` → `processed` \| `error` | pipeline        |
| `name`, `email`                                            | string\| null                                                | LLM extraction  |
| `skills`                                                     | string[]                                                     | LLM extraction  |
| `years_of_experience`                                        | float\| null                                                 | LLM extraction  |
| `education`                                                  | object[]                                                     | LLM extraction  |
| `screening_score`                                            | float                                                        | screening       |
| `semantic_similarity`, `skill_score`, `experience_score` | float                                                        | screening       |
| `matched_skills`, `missing_skills`                         | string[]                                                     | screening       |
| `screening_rationale`                                        | string                                                       | screening       |
| `decision`, `decision_message`                             | string                                                       | LangGraph agent |
| `email_status`, `email_sent_at`, `email_error`           | mixed                                                        | intake email    |
| `decision_email_status`, `decision_email_error`            | mixed                                                        | agent email     |
| `created_at` / `updated_at`                                | datetime                                                     | all stages      |

Collections `applications`, `interviews` and `agent_logs` are declared in
[app/db/mongodb.py](app/db/mongodb.py) but not yet used.

**Qdrant — `candidates` collection**

| Property    | Value                                                                             |
| ----------- | --------------------------------------------------------------------------------- |
| Vector size | 768 (COSINE distance)                                                             |
| Point id    | `uuid5(NAMESPACE_OID, candidate_id)` — deterministic, so re-processing upserts |
| Payload     | `candidate_id`, `job_id`, `name`, `email`, `skills`                     |

### 2.6 Delivered endpoints

| Method             | Endpoint                           | Module                             |
| ------------------ | ---------------------------------- | ---------------------------------- |
| `GET`            | `/health`                        | 1                                  |
| `POST` / `GET` | `/jobs/`                         | 3                                  |
| `POST`           | `/applications/`                 | 4–8 (triggers the whole pipeline) |
| `GET`            | `/applications/{id}/vector`      | 7                                  |
| `GET`            | `/applications/{id}/screening`   | 8                                  |
| `POST`           | `/hiring/candidates/{id}/screen` | 9–10                              |

### 2.7 Design decisions already made

- **Local-first AI.** Ollama runs both the extraction LLM and the embedding model, so no
  resume text leaves the machine and there is no per-token cost.
- **Deterministic Qdrant point ids.** `uuid5` over the Mongo `ObjectId` means reprocessing
  a candidate updates the same vector instead of duplicating it.
- **Rules blended with AI.** Semantic similarity alone is noisy; hard skill and experience
  checks carry 50% of the weight and are fully auditable.
- **Explainability by default.** Every sub-score plus a plain-English rationale is stored
  and returned — a recruiter can always see why a score is what it is.
- **Non-blocking intake.** The applicant gets an immediate response; parsing, extraction,
  embedding and scoring happen in a background task.
- **Emails never break the flow.** SMTP failures are caught and recorded as status fields
  on the candidate document.
- **Fail-fast configuration.** `pydantic-settings` requires every environment key at import
  time, so a misconfigured deployment fails at startup, not mid-pipeline.

---

## 3. Proposed vs. delivered

| #  | Module                       | Proposed capability                              | Status         | Where                                                                 |
| -- | ---------------------------- | ------------------------------------------------ | -------------- | --------------------------------------------------------------------- |
| 1  | Scaffold + FastAPI           | App with`/health`                              | ✅ Done        | [app/main.py](app/main.py)                                             |
| 2  | Docker Compose               | One-command Mongo + Qdrant                       | Done           | [docker-compose.yml](docker-compose.yml)                               |
| 3  | Mongo + Job model            | Create / list jobs                               | ✅ Done        | [app/routes/jobs.py](app/routes/jobs.py)                               |
| 4  | Application intake           | Resume upload + candidate record                 | ✅ Done        | [app/routes/applications.py](app/routes/applications.py)               |
| 5  | Resume text extraction       | PDF / DOCX → text                               | ✅ Done        | [app/services/resume_parser.py](app/services/resume_parser.py)         |
| 6  | Structured LLM extraction    | Text → validated JSON                           | ✅ Done        | [app/services/llm_extractor.py](app/services/llm_extractor.py)         |
| 7  | Embeddings + Qdrant          | Store & retrieve resume vectors                  | ✅ Done        | [app/services/qdrant_service.py](app/services/qdrant_service.py)       |
| 8  | Screening score              | Similarity + rules + rationale                   | ✅ Done        | [app/services/screening_service.py](app/services/screening_service.py) |
| 9  | First LangGraph graph        | State flowing through nodes                      | ✅ Done        | [app/agent/graph.py](app/agent/graph.py)                               |
| 10 | Screening node + routing     | Conditional reject / invite                      | ✅ Done        | [app/agent/graph.py](app/agent/graph.py)                               |
| — | Email notifications          | *(beyond the plan)* received / reject / invite | ✅ Done        | [app/services/email_service.py](app/services/email_service.py)         |
| 11 | Interview template + invite  | Question set, expiring link, session             | ❌ Not started | —                                                                    |
| 12 | Record & upload one answer   | `MediaRecorder` page + upload endpoint         | ❌ Not started | —                                                                    |
| 13 | Full multi-question flow     | Ordered questions, session`submitted`          | ❌ Not started | —                                                                    |
| 14 | Extract audio + transcribe   | ffmpeg + faster-whisper                          | ❌ Not started | —                                                                    |
| 15 | Rubric + per-answer scoring  | Quote-backed competency JSON                     | ❌ Not started | —                                                                    |
| 16 | Scorecard aggregation        | Weighted totals + review flags                   | ❌ Not started | —                                                                    |
| 17 | Full graph + human interrupt | Durable pause for a human decision               | ❌ Not started | —                                                                    |
| 18 | Chainlit review dashboard    | Approve / Override / resume the graph            | ❌ Not started | —                                                                    |
| 19 | Observability, tests, Docker | Tracing, pytest suite, one-command stack         | ❌ Not started | scripts exist in[app/test/](app/test/)                                 |

**Delivered: 11 of 19 modules** — the complete intake-to-screening-decision path.

### What the gap means in practice

The system today automates the top of the funnel end to end: an application arrives, is
parsed, scored, explained, decided against a threshold, and answered by email — with no
human touching it. What is missing is everything **after** the screening decision: the
structured video interview, transcription, evidence-based interview scoring, and the
human-in-the-loop review gate that Module 17 makes the centre of the design.

Consequently, the current `invite_to_interview` decision is a terminal state — the
candidate is told a recruiter will be in touch, and a person takes over from there.

### Nearest next steps

1. **Module 17's checkpointer first** — add a LangGraph checkpointer (Mongo-backed) to the
   existing graph now. Durable state is a prerequisite for every remaining module, and
   retrofitting it later is far more disruptive than adding it while the graph is small.
2. **Module 11** — interview templates and invite tokens, so `invite_node` writes a real
   session instead of ending the flow.
3. **Module 19's tests** — convert the scripts in [app/test/](app/test/) into a `pytest`
   suite before the graph grows further.
