# MemoryMesh

![Hackathon](https://img.shields.io/badge/Hackathon-The%20Hangover%20Part%20AI-6366f1)
![Cognee](https://img.shields.io/badge/Cognee-Memory%20Layer-8b5cf6)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)

> Your AI woke up in Vegas with no memory of last night. **Build AI that doesn't forget** with Cognee's self-hosted, hybrid graph-vector memory layer.
>
> — [*The Hangover Part AI: Where's My Context?*](https://www.wemakedevs.org/hackathons/cognee) · WeMakeDevs Hackathon (Jun 29 – Jul 5, 2026)

**MemoryMesh** is an AI-powered meeting memory platform that turns pasted meeting transcripts into a searchable, evolving knowledge graph. It demonstrates [Cognee](https://github.com/topoteretes/cognee)'s full memory lifecycle — **Remember**, **Recall**, **Improve**, and **Forget** — applied to organizational meeting intelligence.


## Purpose

Teams lose context between meetings. Decisions get re-litigated, ownership is unclear, and finding what was said three sprints ago means digging through notes or Slack threads.

MemoryMesh solves this by:

1. **Ingesting** pasted meeting transcripts (no audio upload required).
2. **Extracting** structured entities — people, projects, decisions, tasks, risks, blockers, and topics — using an LLM.
3. **Indexing** transcript content into Cognee's knowledge graph and vector store so it can be recalled semantically.
4. **Tracking evolution** — when a new meeting revises an old decision, MemoryMesh links the history and calls Cognee **Improve()**.
5. **Surfacing memory** through search, AI chat, a force-directed knowledge graph, and decision timelines.

Each workspace (tenant) gets isolated memory. Users register, create meetings, and interact with memory through a React dashboard backed by a FastAPI + Cognee backend.

---

## What You Can Do

| Area | Description |
|------|-------------|
| **Dashboard** | Overview of entity counts, breakdown by type, and recent meetings |
| **Meetings** | Create meetings, paste transcripts, trigger Remember / Improve / Forget |
| **Knowledge Graph** | Interactive force-directed graph of entities, meetings, and relationships |
| **Search** | Semantic, graph, or hybrid search across indexed memory |
| **AI Chat** | Ask questions answered from Cognee Recall + LLM synthesis |
| **Decisions** | Track architectural decisions and their evolution across meetings |
| **Timeline** | Chronological view of meetings and decisions |
| **Memory Control** | Manage stored memory at workspace, meeting, project, or entity scope |
| **Entities** | Browse people, technologies, projects, and topics extracted from transcripts |
| **Settings** | View the active LLM provider configuration |

---

## How Cognee Powers MemoryMesh

Cognee is the **persistent memory engine** behind MemoryMesh. The app wraps Cognee's four lifecycle operations in `backend/services/cognee_service.py` and exposes them through REST API routes and the UI.

### The Four Cognee Operations

```mermaid
flowchart LR
    subgraph ingest [Meeting Ingestion]
        T[Transcript] --> LLM[LLM Extraction]
        LLM --> SQL[(PostgreSQL)]
        LLM --> R[Cognee Remember]
    end

    subgraph query [Query & Explore]
        R --> G[Knowledge Graph]
        R --> V[(LanceDB Vectors)]
        Q[User Query] --> RC[Cognee Recall]
        RC --> Chat[AI Chat]
        RC --> Search[Search Page]
    end

    subgraph evolve [Memory Evolution]
        ND[New Decision] --> IM[Cognee Improve]
        IM --> G
    end

    subgraph cleanup [Cleanup]
        FG[Cognee Forget] --> G
        FG --> V
    end
```

#### 1. Remember — Store meeting memory

**When:** A meeting is created or manually re-indexed.

**What happens:**

1. The LLM extracts structured entities into PostgreSQL (people, projects, decisions, etc.).
2. `cognee_service.remember()` calls `cognee.remember()` with the transcript, prefixed with meeting metadata (`Meeting ID`, `Title`, `Date`) for source citation during Recall.
3. Cognee runs its internal pipeline (add + cognify) to build graph nodes and vector embeddings in LanceDB.
4. Each meeting is stored in a tenant-scoped dataset: `tenant_{tenant_id}_meeting_{meeting_id}`.

**UI:** Meetings page → **Remember** button, or automatic processing on upload.

**API:** `POST /api/memory/remember`

---

#### 2. Recall — Retrieve relevant memories

**When:** User searches, chats, or the backend needs context.

**What happens:**

1. `cognee_service.recall()` calls `cognee.recall()` with the user's query.
2. Search mode maps to Cognee search types:
   - **Hybrid / graph** → `GRAPH_COMPLETION`
   - **Semantic** → `CHUNKS`, `RAG_COMPLETION`, or `SUMMARIES`
3. Results are normalized into `RecallItem` objects with meeting ID, title, entity type, and content snippets.
4. **AI Chat** injects Recall results into the LLM system context before generating a streamed answer.
5. **Search page** displays Recall hits alongside SQL keyword fallback when Cognee is inactive.

**UI:** Search page, AI Chat.

**API:** `POST /api/memory/recall`, `POST /api/search`, `POST /api/chat`

---

#### 3. Improve — Evolve existing memory

**When:** A new meeting supersedes or updates a prior decision, or the user manually triggers Improve.

**What happens:**

1. During ingestion, `_detect_decision_evolution()` compares new decisions against existing ones in PostgreSQL.
2. When a match is found (e.g., a JWT auth decision superseded by OAuth), `cognee_service.improve()` calls `cognee.remember()` with enriched text tagged `[IMPROVEMENT: supersedes]` linking old and new context.
3. PostgreSQL stores decision history (`decision_history` table) and updates decision status (`active` → `superseded`).
4. Manual Improve from the Memory Control UI targets a specific entity and relationship type.

**UI:** Decision Evolution page, Memory Control → Improve.

**API:** `POST /api/memory/improve`

---

#### 4. Forget — Remove memory cleanly

**When:** User clears memory at workspace, meeting, project, or entity scope.

**What happens:**

1. `cognee_service.forget()` calls Cognee's forget API:
   - **Workspace** → `cognee.forget(everything=True)`
   - **Meeting** → `cognee.forget(dataset=dataset_name)`
   - **Project** → forget all matching datasets
2. PostgreSQL rows (meetings, entities, decisions, relationships) are deleted in sync so SQL and Cognee stay consistent.

**UI:** Memory Control page, meeting detail → Forget.

**API:** `POST /api/memory/forget`

---

### Dual Storage Model

MemoryMesh uses **two layers** that work together:

| Layer | Technology | Role |
|-------|------------|------|
| **Structured store** | PostgreSQL | Entities, decisions, tasks, relationships, auth, activity log |
| **Memory engine** | Cognee (LanceDB + graph) | Semantic recall, knowledge graph visualization, Improve/Forget lifecycle |

If Cognee fails to import or initialize, the app runs in **degraded SQL-only mode** — search falls back to keyword matching and the graph uses PostgreSQL projections. Set `COGNEE_REQUIRED=true` in `.env` to fail hard instead.

Cognee data is stored locally at `data/cognee/` (vectors at `data/cognee/cognee.lancedb`).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  React Frontend (Vite, port 5173)                           │
│  Dashboard · Meetings · Graph · Search · Chat · Decisions   │
└──────────────────────────┬──────────────────────────────────┘
                           │ /api/* (proxied in dev)
┌──────────────────────────▼──────────────────────────────────┐
│  FastAPI Backend (port 8000)                                │
│  auth · meetings · memory · graph · search · chat · ...     │
├─────────────────────────────────────────────────────────────┤
│  meeting_service     → LLM extraction + Cognee Remember     │
│  cognee_service      → Remember / Recall / Improve / Forget   │
│  extraction_service  → Entity extraction via LLM              │
│  llm_service         → OpenAI / Gemini / Groq               │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
        ┌──────▼──────┐           ┌───────▼────────┐
        │ PostgreSQL  │           │ Cognee Engine  │
        │ (entities,  │           │ LanceDB + Graph│
        │  decisions) │           │ data/cognee/   │
        └─────────────┘           └────────────────┘
```

**Ingestion pipeline** (triggered when a meeting is created):

```
Create meeting → LLM extract entities → Store in PostgreSQL
              → Cognee Remember() → Detect decision evolution → Cognee Improve()
              → Store decisions/tasks → status: indexed
```

---

## Prerequisites

Pick **one LLM path** — you do not need both Ollama and cloud API keys.

### Option A — Cloud API keys (recommended for local dev)

| Requirement | Version |
|-------------|---------|
| **Node.js** | 20+ |
| **pnpm** | 9+ |
| **Python** | 3.11+ |
| **PostgreSQL** | 14+ (16 recommended) |
| **LLM API key** | OpenAI, Gemini, or Groq |

### Option B — Docker + Ollama (no API keys)

| Requirement | Notes |
|-------------|-------|
| **Docker Desktop** | Only requirement |
| **Disk / RAM** | ~10 GB disk, 8 GB+ RAM |
| **First run** | 15–30 min (Ollama model download) |

---

## Local Setup (Step by Step)

These steps assume **Option A** (cloud API keys) on your machine.

### Step 1 — Clone the repository

```bash
git clone <your-repo-url>
cd Cognee-Memory-Mesh
```

### Step 2 — Install PostgreSQL and create the database

**Windows (using psql or pgAdmin):**

```sql
CREATE DATABASE memorymesh;
```

**macOS (Homebrew):**

```bash
brew install postgresql@16
brew services start postgresql@16
createdb memorymesh
```

**Linux:**

```bash
sudo apt install postgresql postgresql-contrib
sudo -u postgres createdb memorymesh
```

Default connection assumed in `.env`: `postgresql://postgres:postgres@localhost:5432/memorymesh` — adjust user/password if yours differ.

### Step 3 — Create the root `.env` file

Create `.env` in the **repository root** (same folder as `package.json`):

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/memorymesh

# LLM (pick one provider)
LLM_PROVIDER=openai
LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-your-openai-key-here

# Embeddings (OpenAI recommended with OpenAI LLM)
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

# Frontend (required by Vite)
FRONTEND_PORT=5173
BASE_PATH=/
API_PORT=8000

# Auth
JWT_SECRET=change-me-in-production-use-a-long-random-string
JWT_EXPIRE_MINUTES=10080

# Optional
DEBUG=true
COGNEE_REQUIRED=false
```

**Alternative providers** — set `LLM_PROVIDER` and the matching key:

| Provider | LLM_PROVIDER | API key variable | Example model |
|----------|--------------|------------------|---------------|
| OpenAI | `openai` | `OPENAI_API_KEY` | `openai/gpt-4o-mini` |
| Gemini | `gemini` | `GEMINI_API_KEY` | `gemini/gemini-2.5-flash` |
| Groq | `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |

> Do **not** install Ollama for Option A. Cloud LLMs handle chat, extraction, and Cognee indexing.

### Step 4 — Install Node dependencies

```bash
pnpm install
```

### Step 5 — Install Python dependencies

From the repository root:

```bash
pnpm backend:install
```

This runs `pip install -r backend/requirements-local.txt` (includes `cognee==1.2.2`, FastAPI, SQLAlchemy, etc.).

**Tip:** Use a virtual environment:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r backend/requirements-local.txt
```

### Step 6 — Start the backend

From the repository root:

```bash
pnpm backend:dev
```

Or directly:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

On startup the backend will:

- Create PostgreSQL tables automatically (`init_db()`)
- Initialize Cognee with your LLM/embedding config
- Create `data/cognee/` and `logs/` directories

Verify the backend:

- Health: http://localhost:8000/api/healthz
- API docs: http://localhost:8000/api/docs

### Step 7 — Start the frontend (new terminal)

From the repository root:

```bash
pnpm --filter @workspace/frontend run dev
```

Open http://localhost:5173

The Vite dev server proxies `/api` requests to `http://localhost:8000`.

### Step 8 — Register and sign in

1. Go to http://localhost:5173/register
2. Create an account with email, password, name, and workspace name
3. You are redirected to the dashboard after registration

Each registration creates a **tenant** (workspace). All meetings and Cognee datasets are scoped to that tenant.

### Step 9 — (Optional) Seed sample data

Pre-load sample meetings through the same pipeline as manual upload:

```bash
pnpm run seed
```

Requires a running LLM provider and Cognee. The seed script clears existing meeting data and re-ingests sample transcripts.

---

## Docker Setup (Alternative)

### Option A — Docker + cloud API keys (no Ollama)

```bash
cd docker
cp .env.example .env
# Edit .env — set OPENAI_API_KEY (or Gemini/Groq keys)
docker compose -f docker-compose.cloud.yml up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend health | http://localhost:8000/api/healthz |
| API docs | http://localhost:8000/api/docs |

### Option B — Docker + Ollama (no API keys)

```bash
cd docker
docker compose up --build
```

First run downloads `qwen2.5` and `nomic-embed-text` via the `ollama-init` container. Wait until all containers are healthy (~15–30 minutes).

Uses ~10 GB disk and 8 GB+ RAM. CPU-only by default (no GPU required).

---

## First Run Walkthrough

After logging in, try this flow to see Cognee in action:

1. **Create a meeting** — Go to **Meetings → New Meeting**, enter a title and date, paste a transcript, and save.
2. **Wait for indexing** — Status moves `pending` → `processing` → `indexed`. This runs LLM extraction + Cognee Remember.
3. **Explore the graph** — Open **Knowledge Graph** to see Cognee-derived nodes and edges (falls back to SQL graph if Cognee is inactive).
4. **Search** — Use **Search** with hybrid/semantic/graph modes powered by Cognee Recall.
5. **Chat** — Ask "What decisions were made about authentication?" on the **AI Chat** page. Recall results are injected into the LLM context.
6. **Add a follow-up meeting** — Paste a transcript that revises an earlier decision. Watch **Decisions** for evolution chains and Cognee Improve activity.
7. **Memory Control** — Use **Forget** to remove a meeting's Cognee dataset, or clear the entire workspace.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `LLM_PROVIDER` | Yes | `openai` | `openai`, `gemini`, or `groq` |
| `LLM_MODEL` | Yes | `openai/gpt-4o-mini` | LiteLLM-style model string |
| `OPENAI_API_KEY` | If OpenAI | — | OpenAI API key |
| `GEMINI_API_KEY` | If Gemini | — | Google Gemini API key |
| `GROQ_API_KEY` | If Groq | — | Groq API key |
| `EMBEDDING_PROVIDER` | Yes | `openai` | Embedding provider for Cognee vectors |
| `EMBEDDING_MODEL` | Yes | `openai/text-embedding-3-small` | Embedding model |
| `EMBEDDING_DIMENSIONS` | Yes | `1536` | Vector dimensions |
| `FRONTEND_PORT` | Yes (dev) | — | Vite dev server port |
| `BASE_PATH` | Yes (dev) | — | Vite base path (use `/`) |
| `API_PORT` | No | `8000` | Backend port for Vite proxy |
| `JWT_SECRET` | Yes | — | Secret for JWT auth tokens |
| `JWT_EXPIRE_MINUTES` | No | `10080` | Token expiry (7 days) |
| `COGNEE_REQUIRED` | No | `false` | If `true`, memory endpoints return 503 when Cognee is down |
| `VECTOR_DB_PROVIDER` | No | `lancedb` | Cognee vector store |
| `VECTOR_DB_PATH` | No | `./data/lancedb` | Overridden to `data/cognee/cognee.lancedb` locally |
| `DEBUG` | No | `false` | Enable FastAPI reload mode |

See `docker/.env.example` for a Docker-ready template.

---

## Project Structure

```
Cognee-Memory-Mesh/
├── frontend/                 # React + Vite UI
│   └── src/
│       ├── pages/            # Dashboard, meetings, graph, chat, search, ...
│       ├── components/       # Layout, UI primitives
│       └── context/          # Auth context
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── api/routers/          # REST routes (auth, memory, chat, graph, ...)
│   ├── services/
│   │   ├── cognee_service.py # Remember / Recall / Improve / Forget
│   │   ├── meeting_service.py# Ingestion pipeline
│   │   ├── extraction_service.py
│   │   └── llm_service.py
│   ├── database/             # SQLAlchemy models + connection
│   ├── models/               # Pydantic request/response schemas
│   └── scripts/              # seed.py, seed_data.py
├── lib/
│   ├── api-spec/             # OpenAPI spec
│   └── api-client-react/     # Generated React Query hooks
├── docker/
│   ├── docker-compose.yml           # Full stack + Ollama
│   ├── docker-compose.cloud.yml     # Postgres + backend + frontend
│   └── .env.example
├── data/
│   └── cognee/               # Cognee LanceDB + graph files (created at runtime)
├── package.json              # pnpm workspace root scripts
└── .env                      # Local config (not committed)
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19, Vite 7, Tailwind CSS 4, Wouter, TanStack Query |
| Graph viz | react-force-graph-2d, d3-force |
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async) |
| Memory engine | Cognee 1.2.2 (LanceDB vectors + knowledge graph) |
| Database | PostgreSQL 16 |
| LLM | OpenAI / Gemini / Groq (local dev) or Ollama (Docker default) |
| Auth | JWT (python-jose + bcrypt) |
| API codegen | Orval from OpenAPI spec |

---

## Development Commands

```bash
# Install Python deps
pnpm backend:install

# Run backend (port 8000)
pnpm backend:dev

# Run frontend (port from FRONTEND_PORT in .env)
pnpm --filter @workspace/frontend run dev

# Seed sample meetings
pnpm run seed

# Typecheck everything
pnpm run typecheck

# Build all packages
pnpm run build

# Regenerate API client from OpenAPI spec
pnpm --filter @workspace/api-spec run codegen
```

---

## Acknowledgements

This project was built for [**The Hangover Part AI: Where's My Context?**](https://www.wemakedevs.org/hackathons/cognee) hackathon hosted by [WeMakeDevs](https://www.wemakedevs.org/).

- **[WeMakeDevs](https://www.wemakedevs.org/)** — For organizing the hackathon, fostering the developer community, and providing a platform to build with persistent AI memory.
- **[Cognee](https://github.com/topoteretes/cognee)** — For the open-source hybrid graph-vector memory layer and the **Remember / Recall / Improve / Forget** lifecycle that powers MemoryMesh.

---

## License

MIT
