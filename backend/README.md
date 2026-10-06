# KT-Agent Backend

KT-Agent is a local CLI that turns a shared documentation folder into a searchable, cited knowledge base. It uses SQLite for local indexing and Amazon Bedrock for metadata enrichment and grounded answers.

The v1 requirements are in [PRD.md](PRD.md).

See the [repo root README](../README.md) for the project overview.

## Architecture

<!-- TODO: describe the core/ + adapters pattern we designed:
       core/  = pure logic (no typer, no fastapi)
       cli.py = terminal adapter
       api/   = FastAPI adapter
     A tiny ASCII diagram here would earn its keep. -->

## Setup

<!-- TODO: the exact commands you run. Likely:
       uv sync
       uv run pytest -q
-->

## Running

<!-- TODO: two run modes:
       CLI:  uv run kt-agent --help
       API:  uv run uvicorn kt_agent.api.app:app --reload --port 8000
-->

## Dev ↔ Frontend wiring

<!-- TODO: one line on the strategy you chose (Vite proxy in dev,
     FastAPI serves the build in prod). Point readers at frontend/vite.config.ts. -->
