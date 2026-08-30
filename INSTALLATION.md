# Installation & Running Guide

Complete setup instructions for the **Automated Hiring Process** (AI Hiring Agent), a
FastAPI service that ingests resumes, extracts structured candidate data with a local LLM,
scores candidates against a job, and routes them through a LangGraph decision graph that
sends the appropriate email.

---

## 1. What you need before you start

| Requirement        | Version                               | Why it is needed                                               |
| ------------------ | ------------------------------------- | -------------------------------------------------------------- |
| **Python**         | 3.13+ (`.python-version` pins `3.13`) | Runtime for the FastAPI app                                    |
| **uv**             | 0.12+                                 | Dependency + virtualenv manager (`pyproject.toml` / `uv.lock`) |
| **Docker Desktop** | any recent                            | Easiest way to run MongoDB and Qdrant locally                  |
| **MongoDB**        | 7.x                                   | Stores jobs and candidate records                              |
| **Qdrant**         | 1.x                                   | Stores resume embeddings for semantic similarity               |
| **Ollama**         | 0.3+                                  | Runs the local LLM and embedding model                         |
| **SMTP account**   | —                                     | Sending candidate emails (a Gmail app password works)          |

Verify what you already have:

```bash
python --version      # 3.13.x
uv --version
docker --version
ollama --version
```

If `uv` is missing, install it:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 2. Clone and install dependencies

```bash
git clone https://github.com/Tulsee/automated_hiring_process automated_hiring_process
cd automated_hiring_process
```

Install with **uv** (recommended — uses the locked dependency set):

```bash
uv sync
```

This creates `.venv/` and installs everything declared in `pyproject.toml`:
`fastapi`, `uvicorn`, `pymongo`, `qdrant-client`, `langgraph`, `ollama`, `pypdf`,
`python-docx`, `aiosmtplib`, `pydantic-settings`, `python-multipart`.

<details>
<summary>Alternative: plain pip</summary>

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Note: `requirements.txt` is a frozen snapshot and lags behind `pyproject.toml`. If an
import fails, install the missing package directly:

```bash
pip install langgraph ollama pypdf python-docx aiosmtplib
```

</details>

---

## 3. Start the backing services

MongoDB and Qdrant both run as containers. The repo ships a
[docker-compose.yml](docker-compose.yml) that starts both with one command; the manual
`docker run` equivalents are in [section 3.2](#32-manual-alternative-docker-run) if you
prefer.

### 3.1 Recommended: docker compose

```bash
docker compose up -d --wait      # start both, block until both report healthy
docker compose ps                # status
docker compose down              # stop (named volumes are kept)
```

`--wait` blocks until both healthchecks pass, so the next step never races a database that
is still starting:

```
Container hiring-qdrant  Healthy
Container hiring-mongo   Healthy
```

Verify each one:

```bash
docker exec hiring-mongo mongosh --quiet --eval "db.runCommand({ping:1}).ok"   # -> 1
curl http://localhost:6333/collections                                         # -> {"result":...,"status":"ok"}
```

The Qdrant dashboard is at <http://localhost:6333/dashboard>.

Data lives in the named volumes `mongo_data` and `qdrant_storage`, so `docker compose down`
and a later `up` preserve your jobs, candidates and vectors. **`docker compose down -v`
deletes them.**

#### If a port is already in use

`up` fails with `Bind for 0.0.0.0:6333 failed: port is already allocated` when something
else already holds the port — commonly a native MongoDB Windows service on 27017, or a
Qdrant container you started by hand earlier.

Either stop the conflicting service:

```bash
docker stop qdrant                                    # an existing container
powershell -Command "Stop-Service MongoDB"            # a native Windows service (admin)
```

or remap the host ports — they are overridable, so you do not need to edit the compose
file. Set them in your shell or in a `.env` file beside `docker-compose.yml`:

```ini
MONGO_PORT=27018
QDRANT_HTTP_PORT=6335
QDRANT_GRPC_PORT=6336
```

If you remap, update the app's own `.env` to match:

```ini
MONGO_URI=mongodb://127.0.0.1:27018
QDRANT_URL=http://localhost:6335
```

> **Watch out on Windows:** Docker Desktop can bind a port that a native Windows service is
> already listening on without reporting an error. If you have the MongoDB service running
> *and* start a container on 27017, connections may silently reach the empty container
> instead of your real database. Stop one of the two rather than running both.

### 3.2 Manual alternative: docker run

If you would rather not use compose:

```bash
docker run -d --name hiring-mongo -p 27017:27017 -v hiring_mongo_data:/data/db mongo:7

docker run -d --name hiring-qdrant -p 6333:6333 -p 6334:6334 -v hiring_qdrant_data:/qdrant/storage qdrant/qdrant
```

Check them:

```bash
docker exec -it hiring-mongo mongosh --eval "db.runCommand({ping:1})"
curl http://localhost:6333/collections
```

Note that these use different volume names than compose, so the two approaches do not share
data.

### 3.3 Ollama (LLM + embeddings)

Install Ollama from [https://ollama.com/download](https://ollama.com/download), then pull the two models the app uses:

```bash
ollama pull nomic-embed-text   # 768-dim embeddings -> EMBED_MODEL
ollama pull qwen3.5:4b         # structured resume extraction
```

Confirm both are present and the daemon is reachable:

```bash
ollama list
curl http://localhost:11434/api/tags
```

> **Important:** `nomic-embed-text` produces **768-dimensional** vectors. This must match
> `EMBEDDING_DIMENSION=768` in `.env` and the vector size used when the Qdrant collection
> is created in [app/services/qdrant_service.py](app/services/qdrant_service.py). If you
> swap the embedding model, delete the Qdrant collection and update both values.

---

## 4. Configure environment variables

Copy the template and edit it:

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

`.env` is read by [app/core/config.py](app/core/config.py) through `pydantic-settings`.
**Every field below is required**: the app fails fast at import time if one is missing.

```ini
# ---- MongoDB ----
MONGO_URI=mongodb://127.0.0.1:27017
MONGO_DB=hiring_db

# ---- Qdrant ----
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=candidates
EMBEDDING_DIMENSION=768

# ---- Logging: DEBUG | INFO | WARNING | ERROR ----
LOG_LEVEL=INFO

# ---- Email (SMTP over STARTTLS) ----
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com

# ---- Ollama embedding model ----
EMBED_MODEL=nomic-embed-text
```

### Gmail SMTP setup

1. Enable 2-Step Verification on the Google account.
2. Create an **App Password** (Google Account → Security → App passwords).
3. Use that 16-character password as `SMTP_PASSWORD` — not your normal login password.

The chat/extraction model is currently hard-coded as `OLLAMA_MODEL = "qwen3.5:4b"` in
[app/services/llm_extractor.py](app/services/llm_extractor.py); change it there to use a
different model.

---

## 5. Run the application

```bash
uv run uvicorn app.main:app --reload
```

or, with an activated virtualenv:

```bash
uvicorn app.main:app --reload
```

On startup the lifespan handler in [app/main.py](app/main.py) pings MongoDB and Qdrant,
logs the connection status, and creates the Qdrant collection if it does not exist:

```
Starting AI Hiring Agent...
Database connection status
MongoDB : CONNECTED
Qdrant  : CONNECTED
Collection 'candidates' created successfully.
```

Open:

- Interactive API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) returns `{"status":"ok"}`

---

## 6. End-to-end walkthrough

### Step 1: Create a job

```bash
curl -X POST http://127.0.0.1:8000/jobs/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Backend Python Engineer",
    "description": "Build and maintain FastAPI services, MongoDB data models and async pipelines.",
    "required_skills": ["python", "fastapi", "mongodb", "docker"],
    "minimum_experience": 2
  }'
```

The response contains the `id` save it as `JOB_ID`.

List jobs:

```bash
curl http://127.0.0.1:8000/jobs/
```

### Step 2: Submit an application (resume upload)

```bash
curl -X POST http://127.0.0.1:8000/applications/ \
  -F "job_id=<JOB_ID>" \
  -F "resume=@uploads/Shankar_Ghimire_CV.pdf;type=application/pdf"
```

Only **PDF** and **DOCX** are accepted. The response returns immediately with
`status: "received"`; a FastAPI **background task** then runs the full pipeline:

```
received -> processing -> parse resume text -> LLM extraction -> embedding
        -> store vector in Qdrant -> screening score -> "application received" email
        -> processed
```

Watch the server logs to follow it. Save the returned candidate `id` as `CANDIDATE_ID`.

### Step 3 — Inspect the stored embedding

```bash
curl http://127.0.0.1:8000/applications/<CANDIDATE_ID>/vector
```

Returns the Qdrant payload and `vector_dimensions` (should be `768`).

### Step 4 — Read the screening result

```bash
curl http://127.0.0.1:8000/applications/<CANDIDATE_ID>/screening
```

```json
{
  "candidate_id": "...",
  "candidate_name": "Shankar Ghimire",
  "screening_score": 78.4,
  "semantic_similarity": 71.2,
  "skill_score": 75.0,
  "experience_score": 100.0,
  "matched_skills": ["fastapi", "mongodb", "python"],
  "missing_skills": ["docker"],
  "rationale": "Candidate scored 78.4/100. Semantic resume-job similarity was 71.2% ..."
}
```

If it returns `"Screening has not completed yet"`, the background task is still running —
wait a few seconds and retry.

### Step 5 — Run the hiring agent (LangGraph decision)

```bash
curl -X POST http://127.0.0.1:8000/hiring/candidates/<CANDIDATE_ID>/screen
```

The graph loads the candidate, routes on the score against the **70.0** threshold, writes
the decision back to MongoDB, and emails the candidate:

| Score | Route    | Decision stored       | Email sent           |
| ----- | -------- | --------------------- | -------------------- |
| >= 70 | `invite` | `invite_to_interview` | Interview invitation |
| < 70  | `reject` | `reject`              | Polite rejection     |

```json
{
  "candidate_id": "...",
  "decision": "invite_to_interview",
  "screening_score": 78.4,
  "rationale": "Candidate scored 78.4/100 ...",
  "message": "Candidate scored 78.4/100 and passed the screening threshold."
}
```

Change the cut-off via `SCREENING_THRESHOLD` in
[app/agent/graph.py](app/agent/graph.py#L31).

---

## 7. API reference

| Method | Endpoint                                   | Purpose                                             |
| ------ | ------------------------------------------ | --------------------------------------------------- |
| `GET`  | `/health`                                  | Liveness probe                                      |
| `POST` | `/jobs/`                                   | Create a job posting                                |
| `GET`  | `/jobs/`                                   | List all job postings                               |
| `POST` | `/applications/`                           | Upload a resume against a job (starts the pipeline) |
| `GET`  | `/applications/{candidate_id}/vector`      | Inspect the stored resume embedding                 |
| `GET`  | `/applications/{candidate_id}/screening`   | Read scores, matched/missing skills, rationale      |
| `POST` | `/hiring/candidates/{candidate_id}/screen` | Run the LangGraph agent -> decision + email         |

Interactive documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 8. The compose stack in detail

[docker-compose.yml](docker-compose.yml) defines the two backing services. Ollama is
deliberately **not** included — it runs on the host so it can use your GPU directly.

| Service | Container | Image | Default host ports | Volume |
| --- | --- | --- | --- | --- |
| MongoDB | `hiring-mongo` | `mongo:7` | 27017 | `mongo_data` |
| Qdrant | `hiring-qdrant` | `qdrant/qdrant:latest` | 6333 (REST), 6334 (gRPC) | `qdrant_storage` |

Both define a healthcheck, which is what makes `--wait` reliable:

- **MongoDB** runs `mongosh --eval "db.runCommand({ping:1}).ok"`.
- **Qdrant** opens a TCP connection to port 6333 with bash's `/dev/tcp`. The Qdrant image
  ships no `curl` or `wget`, so the usual HTTP healthcheck does not work there.

Everyday commands:

```bash
docker compose up -d --wait     # start, block until healthy
docker compose ps               # status and port mappings
docker compose logs -f qdrant   # follow one service's logs
docker compose restart mongo    # restart one service
docker compose down             # stop and remove containers; volumes kept
docker compose down -v          # stop and DELETE all stored data
```

Both services use `restart: unless-stopped`, so they come back automatically after a
Docker Desktop or machine restart until you explicitly `down` them.

## 9. Running the standalone test scripts

These are runnable scripts, not `pytest` suites — each verifies one module in isolation.
Run them from the project root so the `app.*` imports resolve:

```bash
# Module 5 — resume text extraction only (no AI, no DB)
uv run python app/test/test_parser.py

# Module 6 — resume text -> structured JSON via the LLM (needs Ollama)
uv run python app/test/test_llm_extraction.py

# Modules 9-10 — run the LangGraph agent directly (needs Mongo + a screened candidate)
uv run python app/test/test_langgraph.py
```

`test_langgraph.py` has a hard-coded `candidate_id` near the top — replace it with a real
ID from your database before running it.

---

## 10. Troubleshooting

| Symptom                                                           | Cause                                            | Fix                                                                                                       |
| ----------------------------------------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `ValidationError` for `Settings` on startup                       | A required key is missing from`.env`             | Copy every key from`.env.example`; all Mongo/Qdrant/SMTP fields are mandatory                             |
| `MongoDB : FAILED` in the startup log                             | Mongo container not running, or wrong`MONGO_URI` | `docker start hiring-mongo`; confirm port 27017                                                           |
| `Qdrant : FAILED`                                                 | Qdrant not running, or wrong`QDRANT_URL`         | `docker start hiring-qdrant`; open [http://localhost:6333/dashboard](http://localhost:6333/dashboard)     |
| Connection error to`localhost:11434`                              | Ollama daemon not running                        | Start the Ollama app, or run`ollama serve`                                                                |
| `model 'qwen3.5:4b' not found`                                    | Model not pulled                                 | `ollama pull qwen3.5:4b`                                                                                  |
| Candidate stuck at`status: "processing"`                          | The background task raised                       | Check server logs; the error is also written to the candidate's`error` field in Mongo                     |
| `"Screening has not completed yet"`                               | Pipeline still running                           | Wait and retry — LLM extraction takes several seconds                                                     |
| `"Candidate has not been screened yet"` from `/hiring/.../screen` | Screening never produced a score                 | Check`/applications/{id}/screening` first                                                                 |
| Vector dimension mismatch in Qdrant                               | `EMBED_MODEL` changed                            | Delete the collection (`curl -X DELETE http://localhost:6333/collections/candidates`) and restart the app |
| `email_status: "failed"` on the candidate                         | SMTP rejected the credentials                    | Use a Gmail**App Password**, port `587`, STARTTLS                                                         |
| `Resume must be a PDF or DOCX file`                               | Wrong`content_type` sent                         | Pass an explicit type in curl:`;type=application/pdf`                                                     |
| A file in`uploads/` was overwritten                               | Resumes are saved under their original filename  | Expected today; unique filenames are a known follow-up                                                    |

---

## 11. Project layout

```
automated_hiring_process/
├─ app/
│  ├─ main.py                     FastAPI app, lifespan, router registration
│  ├─ agent/
│  │  └─ graph.py                 LangGraph: screening -> route -> reject / invite
│  ├─ core/
│  │  ├─ config.py                Pydantic settings loaded from .env
│  │  └─ logging_config.py        dictConfig logging setup
│  ├─ db/
│  │  ├─ mongodb.py               Async Mongo client + collection handles
│  │  └─ qdrant.py                Async Qdrant client + collection init
│  ├─ models/                     Mongo document builders (job, candidate)
│  ├─ routes/                     jobs, applications, hiring endpoints
│  ├─ schemas/                    Pydantic request/response + extraction models
│  ├─ services/
│  │  ├─ resume_parser.py         PDF/DOCX -> clean text
│  │  ├─ llm_extractor.py         text -> structured JSON (Ollama)
│  │  ├─ embedding_service.py     text -> 768-dim vector (Ollama)
│  │  ├─ qdrant_service.py        upsert / retrieve / similarity search
│  │  ├─ screening_service.py     skill, experience and weighted score math
│  │  ├─ candidate_screening.py   orchestrates the full screening calculation
│  │  ├─ candidate_processor.py   background pipeline for one application
│  │  └─ email_service.py         SMTP templates (received / reject / invite)
│  └─ test/                       standalone verification scripts
├─ uploads/                       stored resumes (gitignored)
├─ ARCHITECTURE.md                proposed vs. delivered architecture
├─ IMPLEMENTATION_PLAN.md         19-module build plan
├─ README.md                      what this is and how to use it
└─ INSTALLATION.md                this file
```

---

## 12. Current status

Modules **1-10** of the 19-module plan are implemented and runnable: intake,
parsing, LLM extraction, embeddings, screening, and the LangGraph routing agent with email
notifications. Module 2 is covered by [docker-compose.yml](docker-compose.yml) (sections 3 and 8).

Modules **11–19:** video interview, transcription, rubric scoring, human-in-the-loop
review and packaging — are not built yet. See [ARCHITECTURE.md](ARCHITECTURE.md) for the
side-by-side proposed vs. delivered view.
