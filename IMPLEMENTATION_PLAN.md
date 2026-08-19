# KT-Agent Implementation Plan

## Approach

Build KT-Agent clean-room from the PRD. Start with a short foundations track so each core building block is understood independently, then switch to vertical slices where every milestone adds observable product value.

Milestones are sized for roughly one or two development sessions. Use test-first development for behavior, especially state transitions, validation, ranking, and failure handling. Keep deterministic work in Python and explicit `sqlite3` SQL; introduce Bedrock only after the local ingestion and search core works end to end.

## Design Decisions

- Use a `src/kt_agent/` package and Typer CLI. This keeps packaging conventional and the interface thin over testable application functions.
- Use Pydantic at system boundaries, not as a substitute for the database layer. Typed records are most valuable for extracted documents, model contracts, and persisted JSON.
- Keep SQL in a small repository layer built on `sqlite3`. Explicit transactions and FTS5 queries make index behavior inspectable.
- Pass dependencies such as database connections, clocks, Git metadata, and Bedrock clients into application functions. This keeps unit tests offline without creating a framework.
- Treat each ingestion run as a planned set of file operations. Once enrichment is enabled, stage changed documents until their complete metadata batch validates, then commit the batch transactionally. Failures must never erase an older valid document.
- Keep model prompts and schemas versioned in code. Persist their versions with metrics so later evaluation results remain explainable.
- Begin with a small, attributed FastAPI corpus. Expand it only after the complete evaluation loop exists, so corpus growth creates measured retrieval pressure rather than bulk content.

## Phase 1: Foundations

These milestones establish isolated building blocks. They intentionally stop short of complete user workflows.

### Milestone 1: Project Skeleton

**Objective:** Produce an installable CLI with a reliable local development loop.

**Concepts:** `uv` project management, `src` packaging, Typer command composition, pytest fixtures, linting and type checking.

**Build:**

- Create `pyproject.toml`, `src/kt_agent/`, `tests/`, and the `kt-agent` console entry point.
- Add placeholder command groups matching the PRD without implementing their behavior.
- Configure pytest and lightweight lint/type-check commands.
- Add `.gitignore` rules for generated databases, caches, and local state.

**Test first:** A CLI smoke test invokes `kt-agent --help` and confirms the expected command names.

**Exit criterion:** A clean environment can run the CLI help and test suite through `uv`.

### Milestone 2: Domain Contracts

**Objective:** Define the typed data that crosses extraction, ingestion, retrieval, and model boundaries.

**Concepts:** Domain models versus persistence models, invariants, JSON serialization, schema evolution.

**Build:**

- Define focused Pydantic models for extracted documents and sections, front matter, generated/effective metadata, file outcomes, retrieval results, citations, and answer responses.
- Define enums or literals only where the PRD establishes a closed set.
- Establish stable document IDs and prompt/enrichment version constants.
- Keep run persistence models minimal until their tables are implemented.

**Test first:** Cover required fields, bounds, serialization round trips, exact metadata ID coverage, and invalid answer/citation shapes.

**Exit criterion:** Representative extraction, metadata, retrieval, and answer payloads validate without touching SQLite or AWS.

### Milestone 3: SQLite Foundation

**Objective:** Create an inspectable database with explicit migrations and transaction behavior.

**Concepts:** SQLite foreign keys, migrations, JSON columns, FTS5 external-content synchronization, transaction boundaries.

**Build:**

- Implement connection setup and numbered SQL migrations.
- Add the PRD's document, section, ingestion, session, answer-turn, and metrics entities at their minimum useful shape.
- Add the document-level FTS5 table and explicit synchronization functions.
- Implement small repository functions rather than a generic data-access abstraction.

**Test first:** Verify migration idempotence, foreign keys, transaction rollback, document replacement, deletion, and FTS synchronization using temporary databases.

**Exit criterion:** Tests can create, inspect, mutate, and rebuild a database entirely through the repository layer and standard SQL.

### Milestone 4: Extraction Pipeline

**Objective:** Normalize every supported source format into one deterministic document contract.

**Concepts:** Parser adapters, normalization policy, content hashing, structural preservation, front-matter precedence inputs.

**Build:**

- Implement recursive discovery and parser dispatch for Markdown, text, HTML, PDF, and DOCX.
- Normalize text consistently and hash normalized content.
- Preserve headings, section order, and page numbers where available.
- Extract deterministic titles and Markdown front matter without applying generated metadata yet.
- Return per-file failures instead of aborting discovery.

**Test first:** Add small committed fixtures for all formats, malformed files, unsupported files, Unicode/text normalization, and front matter.

**Exit criterion:** One application function turns a mixed fixture directory into typed extracted documents plus isolated errors, with no database or network access.

## Phase 2: Local Product Slices

Each milestone now adds user-visible value while building on the foundations.

### Milestone 5: Initialize and Inspect a Knowledge Base

**Objective:** Let a user create valid local KT-Agent state.

**Concepts:** Path resolution, idempotent commands, separation of tracked sources from derived state.

**Build:**

- Implement `kt-agent init` for the default or selected knowledge-base path.
- Create `source/`, `.ktagent/`, and the migrated database safely.
- Implement an initial `status` view showing paths, schema version, and document count.

**Test first:** Cover first initialization, repeated initialization, custom paths, and existing unrelated files.

**Exit criterion:** `init` followed by `status` produces a usable empty knowledge base without AWS access.

### Milestone 6: Deterministic Local Ingestion

**Objective:** Index source documents incrementally without generated metadata.

**Concepts:** Reconciliation, content-addressed change detection, transactional updates, run ledgers.

**Build:**

- Plan added, changed, unchanged, removed, and failed file outcomes by comparing discovery with indexed state.
- Persist extracted documents and sections, synchronize FTS, and prune deleted files.
- Record command/extraction duration, outcome counts, per-file results, and Git commit hash or `unavailable`.
- Implement `--rebuild` for derived state.
- Mark metadata as pending rather than inventing fallback generated values.

**Test first:** Cover initial ingest, skip, update, removal, rebuild, partial parser failure, and rollback preserving prior valid state.

**Exit criterion:** Repeated ingestion of a changing local corpus reports correct outcomes and leaves a reproducible index.

### Milestone 7: Deterministic Search

**Objective:** Make the indexed corpus useful without an LLM.

**Concepts:** FTS5 query syntax, BM25 ranking, field weighting, snippets, stable tie-breaking.

**Build:**

- Implement safe user-query translation into FTS5 expressions.
- Search title, path, full text, and available metadata with documented BM25 weights.
- Return ranked results, effective metadata, and matching excerpts.
- Add configurable `--top-k` while retaining the default of five.

**Test first:** Use a fixed corpus to assert ranking, tie behavior, snippets, empty results, punctuation, and malformed query handling.

**Exit criterion:** `kt-agent search` returns deterministic, inspectable results and makes no network call.

## Phase 3: Model Integration

Introduce Bedrock behind narrow interfaces only after the complete deterministic path is stable.

### Milestone 8: Bedrock Client Spike and Metrics

**Objective:** Prove one production-shaped Converse call and capture its operational evidence.

**Concepts:** boto3 credential resolution, Bedrock Converse, structured output, retries, token usage, pricing assumptions.

**Build:**

- Add configuration for model ID and AWS region using normal boto3 resolution.
- Wrap Converse in a narrow client returning validated content, usage, latency, and request metadata.
- Implement one retry for defined API, parse, and schema failures.
- Add a versioned pricing table and cost calculation.
- Keep the live integration test explicitly opt-in.

**Test first:** Mock successful, transient, malformed, and terminal responses; test usage and cost calculations independently.

**Exit criterion:** Offline tests cover the wrapper, and an opt-in test can make one authenticated call and report model, region, tokens, latency, and estimated cost.

### Milestone 9: Metadata-Enriched Ingestion

**Objective:** Turn local ingestion into the PRD's complete one-command contribution workflow.

**Concepts:** Batch contracts, exact response coverage, metadata provenance, precedence, atomicity.

**Build:**

- Batch at most five added or changed documents per metadata request.
- Send stable IDs, paths, structure, and full normalized text.
- Reject missing, duplicate, or unknown IDs and invalid field bounds.
- Merge front matter over generated metadata while persisting all three views: user, generated, and effective.
- Replace the local-only write path with staged batch writes so source content, sections, metadata, and FTS updates commit together only after validation.
- Persist batch timing, usage, model, region, cost, and enrichment version.
- Implement `--refresh-metadata`; preserve prior valid indexed state after terminal batch failure.

**Test first:** Cover batch sizing, exact ID coverage, retry, no partial batch writes, precedence, refresh, and mixed successful/failed batches.

**Exit criterion:** `ingest` enriches changed files with the required call count, exposes provenance, and remains correct under mocked failures.

### Milestone 10: Grounded Ask

**Objective:** Answer one question from retrieved full documents with validated citations.

**Concepts:** Retrieval-augmented generation, untrusted-context delimiting, abstention, citation integrity.

**Build:**

- Reuse the exact search service to retrieve top-k documents.
- Build one answer request containing full documents and explicit untrusted-data boundaries.
- Validate answer, confidence, citations, next action, and human-review/abstention fields.
- Reject citations outside the retrieved set and resolve heading/page locators against stored sections when provided.
- Persist retrieval/model timing, documents, response, usage, cost, and Git commit hash.

**Test first:** Cover supported answers, unsupported questions, malformed responses, invented citations, retry, and terminal failure with no fabricated answer.

**Exit criterion:** `kt-agent ask` performs one normal model call, displays a grounded answer or abstention, and records complete evidence.

### Milestone 11: Local Sessions

**Objective:** Add bounded conversational continuity without changing retrieval behavior.

**Concepts:** Explicit session state, context windows, reproducible prompt assembly.

**Build:**

- Create and persist an active session on the first question.
- Include only the immediately preceding Q&A pair in a normal follow-up.
- Implement `ask --new` and print the active session ID.
- Store full history while keeping prompt selection policy isolated and testable.

**Test first:** Cover first session creation, active reuse, `--new`, missing prior turns, and exact context included in the request.

**Exit criterion:** Consecutive CLI calls exhibit the PRD's session policy and persisted turns remain inspectable.

## Phase 4: Evaluation and Evidence

Build evaluation after production paths exist so it measures the same code users execute.

### Milestone 12: Retrieval Evaluation Baseline

**Objective:** Produce the first reproducible quality measurement without an LLM.

**Concepts:** Fixture design, Recall@k, rank diagnostics, answerability categories, data leakage avoidance.

**Build:**

- Curate and attribute a small FastAPI documentation subset.
- Define versioned JSONL fixtures with answerable, ambiguous, and unsupported cases.
- Implement `eval retrieval` by calling the production search service.
- Persist per-case rank, duration, versions, and Git commit hash; summarize Recall@k.
- Analyze misses before changing ranking weights or fixture wording.

**Test first:** Test fixture validation, metric calculation, missing expected documents, and persisted run summaries with synthetic cases.

**Exit criterion:** A committed baseline corpus and fixtures produce a repeatable retrieval report from a rebuilt index.

### Milestone 13: Corpus Expansion and Retrieval Pressure Test

**Objective:** Establish whether document-level FTS5 meets the PRD target under realistic corpus competition.

**Concepts:** Dataset growth, regression analysis, query taxonomy, evidence-based architecture decisions.

**Build:**

- Expand toward a broader, versioned FastAPI snapshot with license and provenance records.
- Grow the fixture set to at least 30 cases across distinct query types.
- Compare results with the small baseline and categorize every miss.
- Tune only inspectable FTS query construction or field weights, recording before/after results.
- Document whether failures justify any deferred retrieval feature; do not add embeddings or chunking in v1.

**Test first:** Add each fixture with an explicit expected source and rationale before tuning retrieval for it.

**Exit criterion:** Recall@5 reaches at least 80%, or the measured gap and causes are documented clearly enough to motivate a later architecture decision.

### Milestone 14: Answer Evaluation

**Objective:** Quantify grounding behavior, abstention, latency, and cost on the retrieval fixtures.

**Concepts:** Pipeline evaluation, deterministic versus model-dependent checks, cost-controlled experiments.

**Build:**

- Implement opt-in `eval answers` using the production ask path without conversational carryover.
- Measure schema validity, citation validity, expected-source citation, unsupported-case abstention, latency, tokens, and cost.
- Persist per-case outcomes and aggregate summaries.
- Add a small documented manual-review protocol rather than an LLM judge.

**Test first:** Use mocked answer responses to verify scoring and persistence before any paid run.

**Exit criterion:** One versioned evaluation run can be reproduced and yields portfolio-ready quality, latency, and cost evidence.

## Phase 5: Production Hardening and Release

### Milestone 15: Operational Visibility

**Objective:** Make local state, failures, and costs understandable from the CLI and SQLite.

**Concepts:** Operational summaries, auditability, actionable errors, metric integrity.

**Build:**

- Complete `status` with corpus health, pending/failed metadata, model configuration, and active session.
- Implement `metrics` for recent ingestion, answer, and evaluation runs.
- Review error messages for missing credentials, model access, corrupt files, invalid responses, and database failures.
- Document useful `sqlite3` inspection queries.

**Test first:** Assert concise command output for healthy, empty, partial-failure, and unavailable-configuration states.

**Exit criterion:** A user can diagnose corpus state and inspect every required PRD metric without reading application code.

### Milestone 16: Acceptance and Portfolio Release

**Objective:** Demonstrate the complete product from a clean clone with credible evidence.

**Concepts:** Acceptance testing, reproducibility, least privilege, technical storytelling.

**Build:**

- Turn every PRD acceptance criterion into a checked test, documented manual check, or evaluation result.
- Add the end-to-end README path: install, AWS setup, init, demo ingest, inspect, search, ask, metrics, and evaluation.
- Document model access, boto3 configuration, least-privilege IAM guidance, pricing assumptions, corpus license, and known limits.
- Run offline tests from a clean environment, then the opt-in Bedrock smoke test and versioned evaluations.
- Publish a concise architecture diagram and results table only after measured values exist.

**Test first:** Maintain a release checklist that distinguishes automated, integration, evaluation, and manual verification.

**Exit criterion:** A new contributor can reproduce the demo and its metrics from the README, and all v1 acceptance criteria have linked evidence.

## Recommended Working Rhythm

For each milestone:

1. Restate the behavior and define the smallest observable result.
2. Write one failing behavior test.
3. Implement the minimum path that passes it.
4. Add edge and failure cases named in the milestone.
5. Exercise the CLI manually when the milestone has user-facing behavior.
6. Inspect the SQLite state or captured model request directly.
7. Record decisions that affect contracts, evaluation comparability, or deferred scope.

Do not optimize retrieval, prompts, or cost from intuition alone. Establish a baseline first, change one factor, rerun the same versioned cases, and retain the comparison.

## Scope Guardrails

- Do not add chunk retrieval, embeddings, reranking, a vector database, web APIs, or a browser UI during v1.
- Do not make Bedrock calls from `init`, `search`, retrieval evaluation, or deterministic extraction tests.
- Do not commit SQLite state, credentials, private documents, or generated evaluation results containing sensitive content.
- Do not hide database behavior behind a generic repository framework or introduce abstractions before a second concrete use.
- Do not expand the demo corpus without adding provenance and corresponding evaluation intent.
