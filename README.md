# KT Agent

Tool to organize your second brain into several different knowledge bases via inputting files and interacting in a chat-like interface.

This repository is a monorepo containing a Vite + React frontend and a FastAPI
backend (which also ships a Typer CLI). In development, a single command starts
both servers with hot-reload.

## Prerequisites

Two separate toolchains are required because this is a polyglot monorepo:

- **Node.js** (v22+) and **pnpm** (v10+) — for the frontend and the root dev runner.
  pnpm is enforced via the `packageManager` field; `npm`/`yarn` will be blocked.
- **uv** — for the Python backend. See https://docs.astral.sh/uv/ for install.
  The backend targets Python 3.12+ (pinned to 3.14 via `backend/.python-version`).

## First-time setup (fresh clone)

You must install dependencies for **both** ecosystems.

```bash
# 1. Install the root dev tooling (concurrently) + nothing else lives here
pnpm install

# 2. Install frontend dependencies
cd frontend && pnpm install

# 3. Install backend (Python) dependencies
cd backend && uv sync && cd ..
```

## Running in development

From the repository root:

```bash
pnpm dev
```

This runs both servers in one terminal via `concurrently`:

- `[backend]` FastAPI on http://localhost:8000 (auto-reloads on `.py` changes)
- `[frontend]` Vite on http://localhost:5173 (hot module replacement on `.tsx` changes)

Open http://localhost:5173. The Vite dev server proxies any request to `/api/*`
through to the FastAPI backend on port 8000, so there is no CORS configuration
needed in development. A single `Ctrl-C` stops both servers.

## Running pieces individually

```bash
pnpm dev:backend     # FastAPI only (uvicorn)
pnpm dev:frontend    # Vite only
```

## Backend tests

```bash
cd backend && uv run pytest -q
```
