# AI Hiring Agent — Full Implementation Plan (First Step to Last)

_A complete, learning-focused build: receive an application → parse it → screen it → run a video interview → analyze it → recommend accept/reject → a human confirms. Built in small agile modules so you can run and understand each piece before moving on._

**Stack:** FastAPI · MongoDB · Qdrant · LangGraph · Chainlit · faster-whisper · an LLM for parsing/scoring.

---

## How to use this plan

- Build modules **strictly in order** — each one depends on the ones before it.
- After every module, **run it and look at the output** before continuing. The sprints are arranged so you never depend on something you haven't built yet.
- Format for each module is **Build / Learn / Done when** so you always know what you're making, what concept it teaches, and how to check it works.
- The "aha" modules are **6, 9, 15, and 17** (structured LLM output, agent state, evidence-based scoring, and human-in-the-loop). Slow down there.

## The full flow you're building

```
Application received
  → Resume parsed into structured data
  → Screened & scored against the job
       ├─ below bar → reject path
       └─ above bar → invited to VIDEO INTERVIEW
                         → candidate records answers
                         → audio transcribed to text
                         → LLM scores answers against a rubric
                         → scorecard + evidence produced
                         → HUMAN reviews & confirms accept / reject
                         → candidate notified
```

Everything is orchestrated by a single **LangGraph** graph, exposed through **FastAPI**, with a **Chainlit** dashboard for the recruiter.

---

## Sprint 0 — Foundations (get the plumbing working)

**Module 1 — Project scaffold + FastAPI.**
Set up the repo, virtual environment, and a FastAPI app with a `/health` endpoint.
_Learn:_ project structure, running a server.
_Done when:_ `GET /health` returns `{"status": "ok"}`.

**Module 2 — Local services with Docker Compose.**
Spin up MongoDB and Qdrant as containers.
_Learn:_ how your app talks to external services.
_Done when:_ both containers run and are reachable from your machine.

**Module 3 — MongoDB connection + first model.**
Connect FastAPI to Mongo, define a `Job` document (title, description, required skills), and add endpoints to create and list jobs.
_Learn:_ database CRUD, Pydantic models.
_Done when:_ you can create a job and read it back.

---

## Sprint 1 — Application intake & parsing

**Module 4 — Application intake endpoint.**
Accept an application: a resume file upload plus the job it targets. Save the file and create a `Candidate` record with status `received`.
_Learn:_ file uploads, linking records together.
_Done when:_ an uploaded resume produces a candidate row.

**Module 5 — Resume text extraction.**
Extract plain text from PDF/DOCX (e.g. `pypdf`, `python-docx`). No AI yet — just get the words out.
_Learn:_ document parsing and the messy reality of resumes.
_Done when:_ you print clean text from a sample resume.

**Module 6 — Structured extraction with an LLM.**
Send the resume text to an LLM and get back structured JSON (name, email, skills, years of experience, education).
_Learn:_ prompting for structured output, validating LLM responses.
_Done when:_ messy text becomes clean JSON stored on the candidate.

---

## Sprint 2 — Matching & screening

**Module 7 — Embeddings + Qdrant.**
Create a Qdrant collection and store an embedding of each resume.
_Learn:_ what embeddings are and why vectors enable semantic search.
_Done when:_ a candidate's resume vector is stored and retrievable.

**Module 8 — Screening score.**
Embed the job description, compute similarity to the candidate, and combine it with rule checks (required skills present? minimum experience met?) into one screening score plus a short human-readable rationale.
_Learn:_ blending deterministic rules with AI signals.
_Done when:_ each candidate has a score and a plain-English reason.

---

## Sprint 3 — Your first agent (LangGraph)

**Module 9 — Your first LangGraph graph.**
Build a trivial one-node graph that reads and writes shared state. No hiring logic yet.
_Learn:_ LangGraph's core idea — state flowing through nodes.
_Done when:_ you can trace state going in and coming out.

**Module 10 — Screening node + routing.**
Turn Module 8 into a graph node, then add a conditional edge: below the bar → reject path; above the bar → invite-to-interview path.
_Learn:_ nodes as reusable units and conditional branching.
_Done when:_ different candidates take different paths automatically.

---

## Sprint 4 — Run the video interview

**Module 11 — Interview template + invite.**
Define a fixed, ordered list of questions per job (each tagged with the competency it tests). Generate a unique expiring invite link for above-the-bar candidates, and show a short intro screen the candidate acknowledges before recording begins. Create an `InterviewSession`.
_Learn:_ modeling a structured interview; session lifecycle. (Fixed questions also make later scoring fairer and easier to inspect.)
_Done when:_ a screened candidate gets a working invite and an interview session exists.

**Module 12 — Record & upload one answer.**
A minimal browser page shows one question and records a webcam answer via the `MediaRecorder` API; a FastAPI endpoint receives and stores it, linked to the session + question.
_Learn:_ browser media capture (the trickiest client-side bit) and media uploads.
_Done when:_ you can record an answer and retrieve it by session + question ID.

**Module 13 — Full multi-question flow.**
Walk the candidate through all questions in order, one recording each, then mark the session `submitted`.
_Learn:_ orchestrating a multi-step user flow with state.
_Done when:_ a candidate completes a whole interview end to end.

---

## Sprint 5 — Analyze the interview (content, not appearance)

> Design choice worth knowing: you analyze **what the candidate says**, transcribed to text — not facial expressions or tone. Content-based scoring is what actually predicts fit, and it's far easier to explain and debug.

**Module 14 — Extract audio + transcribe.**
Pull the audio track from each answer (e.g. with `ffmpeg`) and transcribe it with **faster-whisper**. Store transcripts on the session.
_Learn:_ speech-to-text and its error modes (keep the audio; STT sometimes drops or invents words).
_Done when:_ every answer has a stored, readable transcript.

**Module 15 — Rubric + per-answer scoring.**
Write a rubric of 3–5 **job-related** competencies, each on a 1–5 scale with descriptors. Prompt the LLM to score each transcript against it and return JSON: `{competency, score, evidence_quote, reasoning}` — a supporting quote required for every score.
_Learn:_ that a good rubric, not a clever model, is what makes scoring consistent; evidence-grounded structured output.
_Done when:_ one interview answer yields valid, quote-backed JSON scores.

**Module 16 — Aggregate into a scorecard.**
Run all answers, aggregate into per-competency and overall scores with a transparent weighting, and flag anything a human should look at (empty/off-topic/very short answers).
_Learn:_ combining signals into one explainable result.
_Done when:_ a completed interview produces one scorecard with evidence and flags.

---

## Sprint 6 — Decision, human review & wiring it all together

**Module 17 — Full graph + human-in-the-loop.**
Wire the whole pipeline into one LangGraph graph: intake → parse → screen → route → interview → transcribe → score → aggregate → **decision**. At the decision point the graph **interrupts and waits** — nothing is accepted or rejected until a person acts. Save state to Mongo at each step.
_Learn:_ orchestrating a real multi-step agent; durable interrupts (this is the concept most agent tutorials skip).
_Done when:_ one application flows through the entire pipeline and pauses for a human at the end.

**Module 18 — Chainlit review dashboard + notifications.**
Build a Chainlit view showing each candidate's scorecard, evidence quotes, transcript, and flags, with **Approve / Override / Take another look** buttons that resume the paused graph. On the decision, generate the right email (accept / reject / next round) — start by printing drafts to the console.
_Learn:_ connecting a review UI to a paused agent and closing the loop.
_Done when:_ a recruiter can review a candidate and make the final call from one screen, and the correct message is produced.

**Module 19 — Observability, tests & packaging.**
Add structured logging and LLM tracing (e.g. LangSmith) so you can replay every prompt and score; write unit tests for parsing/scoring and one integration test for the full graph; package the whole stack with Docker.
_Learn:_ debugging agents (otherwise very hard) and making the project robust and shippable.
_Done when:_ you can trace any decision, tests pass, and the whole stack starts with one command.

---

## Rubric cheat-sheet (for Module 15)

A good competency row looks like this:

- **Competency:** _Problem-solving approach_
- **1** — no structured approach; misses the problem.
- **3** — reasonable approach with some gaps; addresses the core problem.
- **5** — clear, structured reasoning; considers trade-offs and edge cases.
- **Evidence required:** a direct quote from the transcript.

Keep every competency tied to the job. If you can't explain a score in one sentence backed by a quote, drop that competency.

---

## Module map at a glance

| Sprint             | Modules | You end up with                           |
| ------------------ | ------- | ----------------------------------------- |
| 0 Foundations      | 1–3     | Running API + databases + jobs            |
| 1 Intake & parsing | 4–6     | Resumes turned into structured data       |
| 2 Screening        | 7–8     | Scored, ranked candidates                 |
| 3 First agent      | 9–10    | A LangGraph that routes candidates        |
| 4 Interview        | 11–13   | Candidates recording video answers        |
| 5 Analysis         | 14–16   | Transcripts → evidence-backed scorecards  |
| 6 Decision         | 17–19   | Full agent + human review + shippable app |

19 small modules, each runnable and inspectable — build them in order and you'll have gone from an empty repo to a complete, human-supervised hiring agent while understanding every piece.
