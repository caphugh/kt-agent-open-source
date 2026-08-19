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

## Suggested Code Shape

Use this as a starting map, not a requirement to create every module immediately:

```text
src/kt_agent/
  cli.py                 # Typer commands, option parsing, terminal output
  config.py              # paths, AWS region/model, version constants
  models.py              # cross-layer Pydantic contracts
  db.py                  # connection setup, migrations, transaction helper
  repositories.py        # explicit document/run/session SQL operations
  extraction/
    discover.py          # recursive file discovery and parser dispatch
    markdown.py          # one module per format as behavior warrants
  ingestion.py           # reconciliation and ingestion orchestration
  search.py              # FTS query construction and result mapping
  bedrock.py             # narrow Converse adapter and retry policy
  metadata.py            # enrichment request, validation, precedence merge
  answering.py           # retrieval, prompt assembly, response validation
  evaluation.py          # retrieval and answer evaluation runners
  metrics.py             # timings, pricing, Git revision, summaries
```

Keep dependencies directed inward: `cli.py` calls application functions; application functions coordinate extractors, repositories, and the Bedrock adapter; low-level modules never import the CLI. Commands should parse input and render output, not contain business rules.

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

**Implementation method:** Point `[project.scripts]` at a Typer `app` in `cli.py`. Use Typer's `CliRunner` in tests so CLI behavior is tested in-process. Add only direct dependencies needed by the current milestone; defer extraction and AWS packages until their milestones.

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

**Implementation method:** Start from payload examples, write their expected validation behavior, then introduce the smallest models that express it. Generate a stable document ID from a normalized corpus-relative path rather than file contents so updates retain identity. Represent sections as ordered records owned by an extracted document; represent metadata layers separately so precedence is an explicit merge, not mutation of generated data.

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

**Implementation method:** Have `connect(path)` enable foreign keys and return rows addressable by column name. Store a schema version in a small migration table and apply ordered migration functions inside transactions. Let the application layer own transaction boundaries by passing one connection into repository functions. Prefer an explicit `upsert_document`, `replace_sections`, `delete_document`, and `sync_fts` API over a generic repository class. Test whether the local Python build supports FTS5 before relying on it.

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

**Implementation method:** Discovery should yield sorted corpus-relative paths for reproducibility, then dispatch by lowercase suffix through a parser registry. Give every parser the same contract: raw path in, `ExtractedDocument` out. Normalize line endings once in shared code, but preserve meaningful interior whitespace in code blocks, tables, and prose; then hash the UTF-8 normalized content with SHA-256. Build sections during parsing rather than trying to reconstruct boundaries later. Catch exceptions around each file at the orchestration boundary, preserving the path and exception message in a failure result.

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

**Implementation method:** Centralize path derivation in one function returning source, state, and database paths. Have the CLI resolve arguments, call an `initialize()` application function, and render its result. Use `mkdir(parents=True, exist_ok=True)` and run migrations on every initialization so repeat calls are safe. Query status through repository functions rather than checking files independently in the CLI.

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

**Implementation method:** Split ingestion into three steps: discover/extract current files, load indexed `(source_path, source_hash)` values, and produce an `IngestionPlan`. Execute outcomes in deterministic path order. For a changed file, use one transaction to upsert its document, replace its sections, and synchronize FTS. Record failures separately and continue. Compute removals from the set of discovered supported paths, including paths whose extraction failed, so a corrupt current file is not mistaken for a deletion. Implement rebuild by recreating derived database state, never by modifying `source/`.

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

**Implementation method:** Tokenize the user query conservatively and quote tokens before composing an FTS `MATCH` expression; never interpolate raw input into SQL. Use bound parameters for values. Select `bm25(...)`, `snippet(...)`, and document columns in one query, then order by score followed by source path for stable ties. Put this in a `search_documents(connection, query, top_k)` function shared by `search`, `ask`, and evaluation.

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

**Implementation method:** Accept a boto3 `bedrock-runtime` client in a small adapter rather than constructing it inside business logic. Make the adapter take already assembled messages and return a neutral result containing response text, token usage, latency, model ID, and region. Parse and validate outside or immediately above this transport boundary. Retry the complete call once only for named transient/API/parse/schema failures; return a typed terminal error after the second attempt. Mark live tests with a pytest marker excluded by default.

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

**Implementation method:** Group planned added/changed documents with a simple slice iterator of size five. Serialize each request with document IDs as keys or explicit fields and require the validated response ID set to equal the request ID set. Compute effective metadata with one pure merge function where non-null front-matter fields replace generated fields. Do not open a database transaction while waiting on Bedrock: call and validate first, then open one transaction to write all documents in that batch and its metrics. On failure, write only run/file failure records in a separate transaction.

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

**Implementation method:** Make `answer_question()` call the shared search function, load the full documents for those result IDs, and assemble clearly delimited source blocks with stable IDs and paths. Ask for JSON matching `AnswerResponse`; validate it before any human-readable rendering. Compare citation IDs to a set built from retrieved IDs, then validate optional heading/page locators against that document's sections. Persist the turn only after all validation succeeds; persist terminal call failures as failures, not answer turns containing placeholder text.

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

**Implementation method:** Store one active-session marker in SQLite rather than process memory. At command start, `--new` creates and activates a session; otherwise load the active one or create it. A pure `build_conversation_context(previous_turn)` function should return either no prior messages or exactly the preceding user/assistant pair. Save every successful turn with its session ID and ordinal so complete history remains queryable without automatically entering the prompt.

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

**Implementation method:** Validate each JSONL line into an evaluation-case model and give every case a stable ID. For each case, call the same `search_documents` function, find the lowest rank among expected paths, and derive a hit from `rank <= k`. Store raw per-case results first, then calculate aggregates from those records. Keep corpus source paths identical to expected fixture paths so evaluation does not need fuzzy matching.

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

**Implementation method:** Add documents and cases in small batches, rebuild the index, and save a baseline result before changing ranking. Classify misses such as vocabulary mismatch, competing document, broad query, unsupported question, or bad fixture. Change one query rule or weight set at a time and compare the same fixture version. Keep improvements only when aggregate results rise without unexplained regressions in existing cases.

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

**Implementation method:** Run every case as a fresh session so prior questions cannot affect results. Score deterministic properties directly from the validated response and retrieved IDs; do not infer answer quality from prose. Persist model/config/prompt versions with each run. For manual review, sample a fixed case set and record a small rubric such as supported, complete, concise, and citation usefulness, along with reviewer notes.

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

**Implementation method:** Build `status` and `metrics` from read-only SQL queries returning typed summary records, then let the CLI format them. Keep the default output short and add limits or filters rather than dumping all rows. Map known domain failures to concise messages and non-zero exit codes at the CLI boundary; preserve technical details in persisted failure records for diagnosis.

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

**Implementation method:** Create a traceability table mapping each acceptance criterion to a test name, command, evaluation run, or manual check. Rehearse the README literally in a clean clone or temporary directory. Capture evaluation outputs with corpus, index, prompt, model, pricing, and Git versions so reported portfolio numbers can be reproduced rather than presented as isolated claims.

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
