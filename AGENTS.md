# AGENTS.md

Orientation for agents and contributors working in this repository. This
describes **what lives where** and the conventions that keep the monorepo
coherent. For setup and run instructions, see [README.md](README.md).

## Repository shape

This is a polyglot monorepo with two root-level packages plus a thin
orchestration layer at the root.

```
kt-agent-open-source/
├── package.json          Root dev runner (concurrently). NOT a pnpm workspace.
├── pnpm-lock.yaml        Lockfile for the root's dev tooling only.
├── README.md             Human setup + run instructions.
├── AGENTS.md             This file.
├── IMPLEMENTATION_PLAN.md / PRD.md   Product/planning docs (root copies).
│
├── backend/              Python package: FastAPI API + Typer CLI.
│   ├── pyproject.toml     uv-managed; package name "kt-agent", importable as kt_agent.
│   ├── uv.lock            Backend Python lockfile.
│   ├── .python-version    Pins Python 3.14.
│   ├── kt_agent/          The importable package (flat layout — no src/ wrapper).
│   │   ├── api/           FastAPI adapter layer. Thin; calls into core/.
│   │   │   ├── app.py       FastAPI app instance + routes (/api/health, /api/llm/complete).
│   │   │   └── deps.py      Cached dependencies (get_settings, get_llm); override in tests.
│   │   ├── core/          Shared business logic. NO fastapi/typer imports here.
│   │   │   └── search.py    Deterministic search (TODO: implementation).
│   │   ├── cli.py         Typer CLI. Thin; wraps core/ (currently placeholders).
│   │   ├── config.py      Settings (pydantic-settings, KT_LLM_* env vars / backend/.env).
│   │   ├── llm.py         Stateless Bedrock LLM layer (the ONLY boto3 importer).
│   │   ├── db.py          SQLite access.
│   │   └── models.py      Pydantic models (shared data shapes).
│   ├── .env.example       Template for backend/.env (gitignored). Sets KT_LLM_PROFILE.
│   └── tests/            pytest suite (testpaths = ["tests"]).
│
└── frontend/             Vite + React + TypeScript app (pnpm).
    ├── package.json       Declares pnpm as the only allowed PM.
    ├── pnpm-lock.yaml     Frontend lockfile.
    ├── vite.config.ts     Vite config incl. the /api -> :8000 dev proxy.
    ├── index.html         App HTML entry.
    ├── src/
    │   ├── main.tsx         React entry point.
    │   ├── App.tsx          Root component (probes /api/health, hosts LlmForm).
    │   ├── LlmForm.tsx      Prompt form calling POST /api/llm/complete.
    │   └── assets/          Static assets imported by components.
    └── public/            Static files served as-is.
```

## Architecture conventions

- **Shared-core pattern.** `backend/kt_agent/core/` holds pure logic that knows
  nothing about HTTP or the terminal. Both `api/` (FastAPI) and `cli.py` (Typer)
  are thin adapters that call `core/` and format its output. Put real logic in
  `core/`, not in route handlers or CLI commands.

- **LLM layer.** `kt_agent/llm.py` is a stateless phone line to Bedrock:
  `LLM.send(messages) -> Reply`. Callers supply the full message list; memory,
  prompt building and output validation belong to callers (future `core/`).
  boto3 is imported only there, and `core/` must receive an `LLM` instance rather
  than build one. Config lives in `config.py`; `api/deps.py` provides the cached
  instance (override `get_llm` in tests). Design: `docs/requirements/llm-connection.md`.

- **Dev traffic flow.** Browser → Vite (`:5173`) → proxy on `/api/*` →
  FastAPI (`:8000`). This avoids CORS in development. Frontend code should use
  **relative** `/api/...` URLs, never a hardcoded `http://localhost:8000`.

- **Production plan (not yet implemented).** FastAPI will serve the built
  frontend (`vite build` → `dist/`) as static files on a single origin, again
  avoiding CORS.

- **Flat Python layout.** The package is `backend/kt_agent/` (no `src/` wrapper).
  Hatchling is told where it is via `[tool.hatch.build.targets.wheel] packages`.

## Package managers (enforced, do not mix)

- **Frontend + root:** `pnpm` only. `npm`/`yarn` are blocked via the
  `packageManager` field (Corepack). Do not create `package-lock.json`.
- **Backend:** `uv` only. Use `uv add`/`uv sync`; do not hand-edit `uv.lock`.

## Where to make common changes

| Task | Location |
|------|----------|
| Add an API endpoint | `backend/kt_agent/api/app.py` (delegate to `core/`) |
| Add business logic | `backend/kt_agent/core/` |
| Add a CLI command | `backend/kt_agent/cli.py` (delegate to `core/`) |
| Change LLM profile/model/limits | `backend/.env` (see `.env.example`) or `config.py` defaults |
| Change how Bedrock is called | `backend/kt_agent/llm.py` (`_to_converse` / `_from_converse`) |
| Add a shared data model | `backend/kt_agent/models.py` |
| Add a Python dependency | `cd backend && uv add <pkg>` |
| Add a frontend dependency | `pnpm install --dir frontend <pkg>` |
| Change the dev proxy | `frontend/vite.config.ts` |
| Change the one-command dev runner | root `package.json` scripts |

## Notes / known loose ends

- `backend/README.md` and `backend/PRD.md` are leftover copies from the
  pre-monorepo layout; the canonical docs are the root `README.md` and `PRD.md`.
- `IMPLEMENTATION_PLAN.md` / `PRD.md` may still reference the old `src/kt_agent/`
  path and are pending a docs cleanup.
- `core/search.py` and most CLI commands are placeholders pending feature work
  (only `kt-agent llm` is implemented).
- `db.py` is listed above but does not exist yet.
- `backend/PRD.md` says no `.env` is required. That still holds for credentials
  (boto3 chain only); `backend/.env` is an optional place for `KT_LLM_*` settings.
