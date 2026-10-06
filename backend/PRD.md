# KT-Agent Open-Source v1 Product Requirements Document

## Summary

KT-Agent is a local command-line knowledge-base agent for shared repositories. Contributors add supported documents to a version-controlled source directory. A single ingestion command extracts their text, produces derived metadata with Amazon Bedrock, and builds a local SQLite index. Users can search that index without an LLM or ask grounded questions answered from the full text of retrieved documents.

The open-source implementation generalizes the architecture and workflow patterns of a private knowledge-transfer tool. It uses an openly licensed FastAPI documentation corpus for the committed example and evaluation fixture. It must not contain private source documents, prompts, implementation details, or client data.

## Problem

Knowledge is often distributed across technical documents and team members. A shared repository can preserve that knowledge, but it is hard to discover and consume when contributors must manually curate an index or know exact file paths.

KT-Agent reduces this friction by:

- accepting common documentation formats through one ingestion command;
- deriving searchable summaries and themes automatically;
- preserving original documents as the source of truth;
- retrieving relevant full documents, rather than out-of-context text fragments; and
- producing cited, grounded answers with minimal LLM calls.

## Goals

- Make contribution to a shared repository knowledge base as simple as adding documents and running an incremental ingest command.
- Support Markdown, plain text, HTML, PDF, and DOCX in v1.
- Use deterministic Python extraction and SQLite search wherever practical.
- Use AWS Bedrock Claude Sonnet only for metadata enrichment and answer generation.
- Make one Bedrock call per metadata batch and one Bedrock call per answer turn under normal operation.
- Preserve full documents for answer grounding and retain section/page boundaries for a future chunking strategy.
- Keep the source corpus version-controlled and the local index reproducible.
- Demonstrate quality with a committed FastAPI corpus, retrieval fixtures, tests, and persisted metrics.

## Non-Goals

- Zero-configuration operation. Users must install dependencies with `uv` and provide AWS credentials resolvable by boto3.
- Support for arbitrary file formats, OCR, scanned-PDF transcription, or spreadsheet ingestion.
- Chunk-level retrieval, vector databases, embeddings, semantic search, reranking, or hybrid retrieval in v1.
- A browser UI, hosted service, multi-user authentication, access controls, or shared database.
- Autonomous multi-agent workflows or a general-purpose agent framework.
- Fine-tuning, custom model training, or complex MLOps infrastructure.
- Committing SQLite databases or generated state to Git.

## Users and Primary Use Case

### Primary Users

Small engineering teams that maintain a shared Git repository and want contributors to add institutional knowledge as documents. Individual engineers may also initialize an empty knowledge base for local use.

### Primary Workflow

1. A contributor places documents under the repository's source directory and optionally adds Markdown front matter.
2. The contributor runs `kt-agent ingest`.
3. KT-Agent deterministically extracts content and structure, enriches new or changed documents in Bedrock batches, and updates the local SQLite index.
4. Another contributor pulls the repository, runs the same ingest command, and asks questions or searches the corpus.
5. The user receives full-document citations, performance and cost metrics, and an active session ID for a follow-up question.

## Product Principles

- **Source files are authoritative.** SQLite, generated metadata, metrics, and sessions are derived local state that can be rebuilt.
- **Document-level first.** Retrieve full semantically coherent documents before adding chunking complexity.
- **Script deterministic work.** Parsing, hashing, indexing, ranking, validation, and state management are Python/SQLite responsibilities.
- **Use LLM calls deliberately.** Metadata enrichment is batched; each answer turn normally uses one model call.
- **Fail visibly, preserve state.** A bad source file or Bedrock failure must not corrupt indexed documents or block unrelated work.
- **Make evidence inspectable.** Tests, JSONL fixtures, SQLite tables, and CLI summaries must make results explainable.
- **Repository-native collaboration.** Documents are reviewed and shared through normal Git workflows; each clone builds local generated state.

## Technical Scope

### Runtime and Dependencies

- Python 3.12 managed with `uv`.
- A CLI-only interface, implemented with Typer or an equivalent Python CLI library.
- SQLite database stored beneath the knowledge-base directory.
- SQLite FTS5 for document-level full-text search.
- boto3 using Amazon Bedrock's Converse API.
- Claude Sonnet as the v1 Bedrock model for metadata enrichment and grounded answers.
- Pydantic models for all LLM inputs/outputs and persisted structured records.
- Python extraction libraries selected by source format, including PyMuPDF for PDF, `python-docx` for DOCX, and an HTML parser.

### AWS Credentials

KT-Agent relies exclusively on normal boto3 credential resolution. Supported mechanisms include AWS profiles, environment variables, IAM roles, and AWS SSO. The repository must not implement custom key storage, commit credentials, or require a `.env` file.

The README must document required Bedrock model access, AWS region selection, least-privilege guidance, and standard boto3 configuration options.

### Repository Layout

```text
kt-agent/
  knowledge/
    source/                    # Git-tracked contributed documents
    .ktagent/                  # Gitignored derived local state
      knowledge.db
  examples/
    fastapi-docs/              # Git-tracked public demo corpus
  eval/
    retrieval_cases.jsonl      # Git-tracked evaluation fixtures
  tests/
  src/
  README.md
```

`knowledge/source/` is the default shared corpus. A user may point ingestion at another directory. `knowledge/.ktagent/` is local to each clone and must be ignored by Git.

## Functional Requirements

### Initialization

`kt-agent init` creates the expected directory structure and initializes the SQLite schema without requiring an LLM call.

The repository includes an example FastAPI corpus that can be ingested for a working demonstration. Users can also initialize an empty source directory and populate it with their own documents.

### Ingestion

`kt-agent ingest [PATH]` recursively discovers supported files, using `knowledge/source/` when no path is provided.

V1 supported formats:

- `.md`
- `.txt`
- `.html` and `.htm`
- `.pdf`
- `.docx`

The command must:

1. Identify files and supported parsers.
2. Extract normalized text with deterministic Python libraries.
3. Extract deterministic metadata: source path, file type, content hash, modification time, title when available, headings, and page boundaries when available.
4. Parse user-provided Markdown front matter.
5. Skip unchanged documents by content hash.
6. Batch new or changed documents, assumed to be reasonably sized by v1 users, into groups of at most five sources.
7. Make one Bedrock metadata-enrichment call per batch.
8. Validate the returned schema and write valid generated metadata and document records transactionally.
9. Synchronize the FTS5 document index.
10. Remove index records for formerly indexed source files no longer present in the ingested directory.
11. Continue after corrupt, unreadable, or unsupported files and present a final error report.

An ingestion run must retain enough detail to identify which files were added, updated, skipped, removed, and failed.

### Generated and User-Provided Metadata

For each metadata batch, Claude Sonnet receives stable document IDs, paths, deterministically extracted structure, and extracted source text. It returns exactly one typed metadata object per submitted document.

Generated fields:

- `summary`: concise retrieval-oriented description;
- `themes`: short list of topical domains;
- `tags`: short list of search keywords;
- `content_type`: inferred documentation type;
- `suggested_title`: only when deterministic title extraction is weak.

Metadata response validation must require exact document-ID coverage, reject unknown IDs, enforce field lengths and types, and retry once on model/API/schema failure. After a second failure, that batch is reported as failed and no partial generated metadata is written.

Markdown front matter may override:

- `title`
- `themes`
- `tags`
- `content_type`
- `status`
- `summary`
- `version`

User-provided front matter has precedence over generated metadata. Generated metadata must remain identifiable as derived data, even if some fields are overridden.

`kt-agent ingest --refresh-metadata` re-runs metadata enrichment for indexed documents even when their source hash is unchanged. The system records an enrichment/prompt version to make metadata refreshes auditable.

`kt-agent ingest --rebuild` deletes and recreates derived index state for the selected corpus, then ingests all supported documents.

### Full-Document Preservation and Future Chunking

V1 treats one source file as one retrieval unit. The complete normalized document is stored and supplied to the answer model after retrieval. V1 does not retrieve or embed chunks.

During ingestion, retain potential future chunk boundaries without using them for ranking:

- Markdown/HTML heading hierarchy;
- paragraph/section order;
- PDF page number; and
- DOCX heading hierarchy where extraction preserves it.

This preserves context for procedures, exceptions, tables, and code while allowing section-level retrieval to be introduced only if evaluation demonstrates a need.

### Search

`kt-agent search "QUERY"` must not call an LLM.

Search uses SQLite FTS5 against document title, path, full extracted text, generated or overridden summary, themes, tags, and content type. It returns ranked document results with:

- title;
- source path;
- summary;
- themes/tags;
- content type, status, and version when available; and
- a short matching-text excerpt.

Search ranking is deterministic and inspectable. The initial top-k default is five documents and may be configurable by a command option.

### Ask and Grounded Answers

`kt-agent ask "QUESTION"` must:

1. Retrieve the top-k full documents with the same scripted FTS5 retrieval used by `search`.
2. Include those complete documents, their source metadata, and bounded recent conversation context in one Bedrock Converse request.
3. Require a Pydantic-validated JSON response containing an answer, citations, confidence, next action when useful, and an explicit human-review/abstention decision.
4. Validate every cited document against the retrieved set before displaying the response.
5. Return a concise, human-readable answer with citations and a session ID.
6. Persist the answer turn, source documents, model usage, timing, and estimated cost.

The answer model must be instructed that retrieved documents are untrusted data, not instructions. It must answer only from available evidence and abstain when the corpus does not sufficiently support an answer.

Citations must identify the source path and include a heading and/or page number when preserved by extraction. Document-level citation is the fallback.

### Session Behavior

V1 maintains an active local session in SQLite. The first `ask` creates a session and prints its ID. Later `ask` commands reuse the active session unless `--new` is supplied.

For this initial policy, each follow-up Bedrock request includes:

- the new user question;
- the immediately preceding user question;
- the immediately preceding assistant answer; and
- newly retrieved full documents for the new question.

The complete session history is stored locally but is not sent automatically. `kt-agent ask --new "QUESTION"` starts a clean session without prior conversational context. This policy is intentionally provisional and must be easy to adjust after usage and metric review.

### Error Handling

- Unsupported, corrupt, or unreadable sources do not stop ingestion of other files.
- Failed files remain unchanged in the source directory and are listed in the final ingestion report.
- Metadata and answer calls retry once for transient API, schema, or structured-output failures.
- After the retry fails, preserve prior valid indexed state, record a detailed failure, and produce no fabricated metadata or answer.
- An answer with no sufficient retrieved evidence must return a structured abstention, not an unsupported claim.

## SQLite Data Model

The exact schema may evolve, but v1 must support these entities and relationships.

### `documents`

- `id`
- `source_path` (unique within a corpus)
- `source_hash`
- `file_type`
- `title`
- `normalized_content`
- `front_matter_json`
- `generated_metadata_json`
- `effective_metadata_json`
- `status`
- `version`
- `created_at`
- `updated_at`
- `last_ingested_at`
- `metadata_enrichment_version`

### `document_sections`

Preserves future section-level retrieval structure but is not queried for ranking in v1.

- `id`
- `document_id`
- `ordinal`
- `heading_path`
- `page_number` (nullable)
- `content`

### `ingestion_runs` and `ingestion_file_results`

Capture the run lifecycle, source outcome, timings, errors, Bedrock metrics, and repository commit hash.

### `sessions` and `answer_turns`

Store active/local session state, user questions, validated answers, retrieved document IDs, citations, abstention state, timing, Bedrock token usage, estimated cost, and repository commit hash.

### FTS5 Index

An FTS5 virtual table indexes each document's retrievable fields. The database must be queryable with standard SQLite tools and the README must include example inspection commands.

## Observability and Metrics

Every ingestion run and answer turn records metrics in SQLite and presents a readable terminal summary.

Required metrics:

- command duration;
- deterministic extraction duration;
- number of files discovered, added, updated, skipped, removed, and failed;
- metadata batch count and per-batch duration;
- answer retrieval duration and answer-model duration;
- Bedrock input and output token usage when returned by the API;
- estimated Bedrock cost using documented, versioned pricing assumptions;
- model ID and AWS region; and
- Git commit hash of the repository at execution time, or an explicit `unavailable` value outside a Git worktree.

Metrics are local derived data. The CLI must expose a human-readable command to inspect recent ingestion and answer runs. The underlying records must be easy to inspect with the standard `sqlite3` command-line tool.

## Testing and Evaluation

### Automated Component Tests

Tests must cover:

- extraction of each supported input format;
- Markdown front-matter precedence;
- source hashing and incremental skip/update behavior;
- deletion pruning;
- corrupt/unsupported file reporting without ingestion abort;
- metadata batch schema validation, ID coverage, and retry behavior;
- FTS5 indexing and deterministic ranking;
- structured answer validation and citation validation;
- abstention behavior when no supporting source is retrieved;
- session reuse and `--new` behavior; and
- persistence of metrics and Git commit hash.

Bedrock API calls must be mocked in unit tests. A separate opt-in integration test may call Bedrock and must require configured AWS credentials.

### Retrieval Evaluation

The repository includes an openly licensed FastAPI documentation corpus and versioned JSONL retrieval fixtures. Each fixture contains:

- question;
- expected document path(s);
- answerability;
- expected terms or facts where useful; and
- optional notes explaining the case.

`kt-agent eval retrieval` runs the fixture set without an LLM and reports at least:

- Recall@k: whether an expected document appears in the top-k results;
- per-case rank of the first expected document;
- query duration; and
- Git commit hash and index/enrichment version.

V1 acceptance target: expected source appears in the top five results for at least 80% of the initial curated fixture set. The initial fixture set contains at least 30 cases, including answerable, ambiguous, and unsupported questions.

### Answer Evaluation

Answer evaluation is an opt-in Bedrock command because it incurs cost. It uses the same JSONL fixture set and persists per-case model metrics.

V1 evaluates:

- response schema validity;
- citations reference only retrieved documents;
- expected source appears among citations when an answer is supported;
- abstention for designated unsupported cases; and
- latency, token use, and estimated cost.

The initial release does not require an LLM-as-judge. A manually reviewed, documented set of answer-quality observations may be included as supplementary evidence.

## CLI Contract

The final command names may change only for consistency, but v1 supports these behaviors.

```bash
kt-agent init
kt-agent ingest [PATH]
kt-agent ingest [PATH] --refresh-metadata
kt-agent ingest [PATH] --rebuild
kt-agent search "custom exception handlers"
kt-agent ask "How do I add custom exception handlers?"
kt-agent ask --new "How are dependencies declared?"
kt-agent status
kt-agent metrics
kt-agent eval retrieval
kt-agent eval answers
```

## Acceptance Criteria

### Ingestion

- A clean clone can initialize the knowledge-base directory and SQLite index with `uv` and valid boto3-resolved AWS credentials.
- A user can ingest a directory containing all five supported formats with a single command.
- The command uses deterministic extraction for all supported formats and one Bedrock metadata call per batch of no more than five documents.
- Ingestion skips unchanged files based on content hash.
- Changed files replace their prior indexed content and metadata.
- Deleted source files are removed from the local index on the next incremental ingest.
- Corrupt and unsupported files are reported while valid files continue to ingest.
- Valid Markdown front matter overrides generated metadata fields.
- `--refresh-metadata` re-enriches unchanged indexed documents.
- `--rebuild` recreates the derived index without modifying source documents.

### Search and Answers

- Search makes no Bedrock request and returns deterministic FTS5-ranked documents with useful metadata and excerpts.
- Ask retrieves full top-k documents and makes one normal Bedrock Converse request for the answer.
- Answers validate against the defined JSON schema before display.
- Every displayed citation maps to a retrieved source and identifies its path plus a heading/page where available.
- Insufficient evidence produces an explicit abstention.
- The first answer prints an active session ID.
- A normal follow-up uses the active session's immediately previous Q&A pair plus fresh retrieval.
- `--new` starts an answer request with no prior conversational context.

### Evidence and Maintainability

- Unit tests run without AWS credentials or network access.
- A documented opt-in integration test verifies the Bedrock path.
- The committed FastAPI corpus has at least 30 versioned retrieval fixtures.
- Retrieval evaluation achieves Recall@5 of at least 80% on the initial fixture set.
- Ingestion, answer, and evaluation metrics persist in SQLite and print a readable CLI summary.
- Every persisted run includes the current Git commit hash when available.
- README instructions enable a new contributor to ingest the demo corpus, inspect the index, search, ask a question, and run retrieval evaluation.

## Deferred Decisions

- Chunk-level indexing/retrieval will be considered only if document-level evaluation, cost, latency, or answer failures show a concrete need.
- Embeddings, vector search, reranking, and hybrid retrieval are deferred until FTS5 retrieval results justify them.
- The one-prior-Q&A session context policy will be reviewed after real usage and metrics are available.
- Claude Code skills or other wrappers may expose CLI functionality later; they are not part of v1 implementation scope.
- Interactive chat mode, FastAPI endpoints, and a web UI are deferred.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Generated metadata is inaccurate | Use it as a retrieval aid only; preserve/search full source text and permit front-matter overrides. |
| Large full documents increase answer cost or context use | Retrieve only top-k documents; retain section boundaries; add chunk retrieval only after measured need. |
| Document text attempts to manipulate the model | Clearly delimit sources as untrusted data and validate structured output/citations. |
| Batch metadata response is incomplete or mixed up | Use stable IDs, strict exact-coverage validation, one retry, and no partial writes. |
| Shared contributors get inconsistent indexes | Version source documents and rebuild derived local SQLite state deterministically through `ingest`. |
| Bedrock failures or unavailable credentials | Preserve valid local state, report actionable errors, and keep search available without LLM calls. |
| Pricing changes make estimates inaccurate | Version and document the pricing assumptions used for each estimate. |
