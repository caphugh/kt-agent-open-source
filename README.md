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

## LLM configuration (AWS Bedrock)

The backend talks to Claude on Amazon Bedrock through an AWS profile. Credentials
come from the normal boto3 chain only; you must create your own `.env` file with
your own Amazon Bedrock credentials. Follow the instructions below:

```bash
cp backend/.env.example backend/.env    # sets KT_LLM_PROFILE=ailab
aws sso login --profile ailab           # if your SSO session has expired
```

Setting `KT_LLM_PROFILE` as a normal environment
variable works too. Settings:

| Variable              | Default                           |
| --------------------- | --------------------------------- |
| `KT_LLM_PROFILE`      | none (required to call the model) |
| `KT_LLM_REGION`       | `us-east-1`                       |
| `KT_LLM_MODEL_ID`     | `us.anthropic.claude-sonnet-5-5`  |
| `KT_LLM_MAX_TOKENS`   | `1024`                            |
| `KT_LLM_MAX_RETRIES`  | `3`                               |
| `KT_LLM_READ_TIMEOUT` | `60` (seconds)                    |

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
