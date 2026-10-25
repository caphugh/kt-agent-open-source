---
date: 2026-10-24
status: draft
author: htoomey
---

# Requirements: LLM Connection (Bedrock one-off request via API, UI, CLI)

## Problem Statement
The backend has no way to talk to an LLM. Before building knowledge-base chat or
document summarization, we need a single, reusable LLM layer and proof that the
AWS "ailab" profile can reach Claude Sonnet on Bedrock from both the UI and CLI.

## Goals
- A stateless LLM layer (`llm.py`) that sends a list of messages to Bedrock and
  returns a reply. It is the only code that knows about boto3/Bedrock.
- A user can type a prompt in the web UI or CLI and see the model's reply.
- The layer's shape supports two future uses without redesign:
  1. KB chat with conversation memory (multi-message input; memory owned by core/ + DB)
  2. Internal one-off structured calls (summarize/translate; single message, no memory)

## Non-Goals
- Ingestion, search, retrieval, citations, `AnswerResponse`
- Conversation memory/sessions, SQLite
- System prompts, temperature, structured output, tools, streaming
- The existing `ask` CLI stub (untouched)
- Live Bedrock tests in CI

## Functional Requirements

### Settings (`kt_agent/config.py`)
1. Loaded via pydantic-settings from env vars (prefix `KT_LLM_`), optional `backend/.env`.
2. Fields and defaults:

   | Env var | Default |
   |---|---|
   | `KT_LLM_PROFILE` | none (required to call the model; `Settings` itself loads without it and the LLM layer raises a config error on first use) |
   | `KT_LLM_REGION` | `us-east-1` |
   | `KT_LLM_MODEL_ID` | `us.anthropic.claude-sonnet-5-5` |
   | `KT_LLM_MAX_TOKENS` | `1024` |
   | `KT_LLM_MAX_RETRIES` | `3` |
   | `KT_LLM_READ_TIMEOUT` | `60` (seconds) |

3. A committed `backend/.env.example` documents these with `KT_LLM_PROFILE=ailab`.
   The real `.env` is gitignored.

### LLM layer (`kt_agent/llm.py`)
1. Types: `Message(role: "user"|"assistant", text)`, `Reply(text, model_id,
   input_tokens, output_tokens, stop_reason, latency_ms)`, `LLMError` with
   subclasses for: config/credentials, access denied, throttled, unavailable
   (timeout or unreachable), bad response.
2. `LLM(settings, client=None)` with one method: `send(messages: list[Message]) -> Reply`.
3. Stateless: holds no conversation history; the caller supplies all messages.
4. Uses `boto3.Session(profile_name=...).client("bedrock-runtime")` and the Converse API.
   Retries via botocore `Config(retries={"max_attempts": N, "mode": "adaptive"})`
   plus the read timeout.
5. The client is created lazily on the first `send()`, so `--help`, `/api/health`, and
   tests work without AWS credentials. The client can be injected for tests.
6. All botocore/boto3 exceptions are translated to `LLMError` subclasses; none leak.
7. Translation to/from the Converse format lives in two private helpers only.

### API (`kt_agent/api/`)
1. `POST /api/llm/complete`, body `{ "prompt": str }` (non-empty, else 422).
2. Wraps the prompt in a single user `Message`, calls `LLM.send()`.
3. Returns `{ response, model_id, usage: { input_tokens, output_tokens }, latency_ms }`.
4. `LLMError` -> 503 (config/credentials/access/throttle/timeout) or 502 (bad response),
   body `{ "detail": "<human-readable message>" }`.
5. Sync route (boto3 is blocking; FastAPI runs it in its threadpool).
6. Settings and LLM are provided via cached FastAPI dependencies (`get_settings`, `get_llm`)
   in `api/deps.py`, overridable in tests.
7. API request/response schemas are separate from `Message`/`Reply`.

### CLI (`kt_agent/cli.py`)
1. New command: `kt-agent llm "prompt"`. Prints the reply text to stdout, exits 0.
2. On `LLMError`: prints the message to stderr, exits 1.

### Frontend
1. Minimal form: textarea, Send button, loading state, reply or error shown below.
2. Calls the relative URL `/api/llm/complete` (Vite proxy). The existing health probe remains.
3. Send is disabled while the request is in flight or the prompt is empty.

### Tests (mocked only)
1. `llm.py`: botocore `Stubber` covering success, each error mapping, and the missing-profile config error.
2. API: `TestClient` + `get_llm` overridden with a FakeLLM (success, 422, 502/503).
3. CLI: `CliRunner` + FakeLLM (success exit 0, error exit 1).
4. Settings: defaults and env overrides.
5. Existing tests continue to pass.

## Non-Functional Requirements
- **Security**: credentials come only from the AWS profile/boto3 chain; nothing secret
  is committed; the frontend never calls AWS directly.
- **Performance**: single local user; the worst case is retries x timeout, so the UI must show loading.

## Constraints & Assumptions
- New deps: `boto3`, `pydantic-settings` (`cd backend && uv add ...`).
- `core/` must not import boto3, fastapi, or typer. Future core services receive an `LLM` instance.
- Verified 2026-10-24: profile `ailab` exists; `us.anthropic.claude-sonnet-5-5` is ACTIVE in us-east-1.
  Invoke permission is unconfirmed until the first live call.
- An expired SSO session requires `aws sso login --profile ailab` and is surfaced as a clear error.

## User Flows

### Web
1. Run `pnpm dev`, open :5173.
2. Type a prompt and click Send. The button disables and a loading indicator shows.
3. The reply appears, or a readable error appears.

### CLI
1. `cd backend && uv run kt-agent llm "hello"` prints the reply.

## Future Fit (informative, not in scope)
- KB chat: `core/ask` loads history from the DB, adds KB context and the new question,
  calls `send(messages)`, and saves the result.
- Summarize/translate: `core/summarize` sends one message, then validates the structured reply.
  Optional `system` and structured-output parameters get added to `send()` at that point.

## References
- backend/PRD.md (Bedrock/Converse, boto3 credential chain)
- backend/kt_agent/models.py, api/app.py, cli.py
- AGENTS.md (shared-core convention)
