import json

import pytest
from pydantic import ValidationError

from kt_agent.models import (
    AnswerResponse,
    Citation,
    DocumentSection,
    DomainModel,
    EffectiveMetadata,
    ExtractedDocument,
    FileOutcome,
    FileResult,
    FileType,
    FrontMatter,
    GeneratedMetadata,
    MetadataBatchResponse,
    RetrievalResult,
    document_id_for,
    effective_metadata,
)


def generated_metadata(source_path: str = "guides/intro.md") -> GeneratedMetadata:
    return GeneratedMetadata(
        document_id=document_id_for(source_path),
        summary="An introduction to the service.",
        themes=["architecture"],
        tags=["intro"],
        content_type="guide",
        suggested_title="Generated introduction",
    )


def test_extracted_document_round_trips_through_json() -> None:
    source_path = "guides/intro.md"
    document = ExtractedDocument(
        document_id=document_id_for(source_path),
        source_path=source_path,
        file_type=FileType.MARKDOWN,
        source_hash="a" * 64,
        source_mtime_ns=1_726_000_000_000_000_000,
        normalized_content="# Introduction\n\nWelcome.",
        title="Introduction",
        sections=[DocumentSection(ordinal=0, content="Welcome.")],
    )

    restored = ExtractedDocument.model_validate_json(document.model_dump_json())

    assert restored == document


@pytest.mark.parametrize(
    "source_path", ["/absolute.md", "../outside.md", "guide\\intro.md"]
)
def test_extracted_document_rejects_non_normalized_paths(source_path: str) -> None:
    with pytest.raises(ValidationError):
        ExtractedDocument(
            document_id=document_id_for("guide/intro.md"),
            source_path=source_path,
            file_type=FileType.MARKDOWN,
            source_hash="a" * 64,
            source_mtime_ns=0,
            normalized_content="content",
        )


def test_extracted_document_requires_path_derived_id_and_ordered_sections() -> None:
    with pytest.raises(ValidationError, match="document_id does not match"):
        ExtractedDocument(
            document_id=document_id_for("other.md"),
            source_path="guide/intro.md",
            file_type=FileType.MARKDOWN,
            source_hash="a" * 64,
            source_mtime_ns=0,
            normalized_content="content",
        )

    with pytest.raises(ValidationError, match="section ordinals"):
        ExtractedDocument(
            document_id=document_id_for("guide/intro.md"),
            source_path="guide/intro.md",
            file_type=FileType.MARKDOWN,
            source_hash="a" * 64,
            source_mtime_ns=0,
            normalized_content="content",
            sections=[DocumentSection(ordinal=1, content="content")],
        )


def test_effective_metadata_keeps_generated_data_and_applies_front_matter() -> None:
    generated = generated_metadata()

    effective = effective_metadata(
        "Deterministic title",
        generated,
        FrontMatter(title="User title", themes=["operations"], status="current"),
    )

    assert effective == EffectiveMetadata(
        title="User title",
        summary=generated.summary,
        themes=["operations"],
        tags=generated.tags,
        content_type=generated.content_type,
        status="current",
    )
    assert generated.suggested_title == "Generated introduction"


def test_effective_metadata_keeps_deterministic_title_over_suggestion() -> None:
    effective = effective_metadata(
        "Deterministic title", generated_metadata(), FrontMatter()
    )

    assert effective.title == "Deterministic title"


def test_metadata_batch_requires_exact_document_id_coverage() -> None:
    metadata = generated_metadata()
    response = MetadataBatchResponse(documents=[metadata])

    response.require_exact_document_ids({metadata.document_id})

    with pytest.raises(ValueError, match="do not match"):
        response.require_exact_document_ids({document_id_for("other.md")})

    duplicate = MetadataBatchResponse(documents=[metadata, metadata])
    with pytest.raises(ValueError, match="duplicate"):
        duplicate.require_exact_document_ids({metadata.document_id})


def test_metadata_rejects_missing_fields_and_invalid_boundaries() -> None:
    payload = generated_metadata().model_dump()

    del payload["summary"]
    with pytest.raises(ValidationError):
        GeneratedMetadata.model_validate(payload)

    with pytest.raises(ValidationError):
        GeneratedMetadata.model_validate(
            {**generated_metadata().model_dump(), "themes": ["theme"] * 13}
        )

    with pytest.raises(ValidationError):
        GeneratedMetadata.model_validate(
            {**generated_metadata().model_dump(), "tags": ["x" * 101]}
        )

    with pytest.raises(ValidationError):
        MetadataBatchResponse(documents=[generated_metadata()] * 6)


def test_models_reject_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        FrontMatter.model_validate({"title": "Guide", "unknown": "value"})


def test_file_results_require_errors_only_for_failures() -> None:
    assert FileResult(
        source_path="bad.pdf", outcome=FileOutcome.FAILED, error="corrupt"
    )

    with pytest.raises(ValidationError, match="require an error"):
        FileResult(source_path="bad.pdf", outcome=FileOutcome.FAILED)

    with pytest.raises(ValidationError, match="only failed"):
        FileResult(source_path="good.md", outcome=FileOutcome.ADDED, error="unexpected")


@pytest.mark.parametrize("model", [FileResult, RetrievalResult, Citation])
def test_source_referencing_models_require_normalized_paths(
    model: type[DomainModel],
) -> None:
    source_path = "guide\\intro.md"
    document_id = document_id_for("guide/intro.md")
    kwargs: dict[str, object] = {
        "document_id": document_id,
        "source_path": source_path,
    }
    if model is FileResult:
        kwargs.update(outcome=FileOutcome.ADDED)
    elif model is RetrievalResult:
        kwargs.update(excerpt="Matching text", score=0.5, rank=1)

    with pytest.raises(ValidationError, match="source_path must be normalized"):
        model.model_validate(kwargs)


def test_retrieval_result_round_trips_through_json() -> None:
    result = RetrievalResult(
        document_id=document_id_for("guides/intro.md"),
        source_path="guides/intro.md",
        title="Introduction",
        summary="An introduction to the service.",
        themes=["architecture"],
        tags=["intro"],
        content_type="guide",
        status="current",
        version="1.0",
        excerpt="The service begins here.",
        score=-3.5,
        rank=1,
    )

    assert RetrievalResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    ("field", "value"),
    [("rank", 0), ("excerpt", ""), ("themes", ["x" * 101])],
)
def test_retrieval_result_rejects_invalid_boundaries(field: str, value: object) -> None:
    payload: dict[str, object] = {
        "document_id": document_id_for("guides/intro.md"),
        "source_path": "guides/intro.md",
        "excerpt": "Matching text",
        "score": 0.5,
        "rank": 1,
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        RetrievalResult.model_validate(payload)


def test_answer_response_rejects_invalid_citation_shapes() -> None:
    with pytest.raises(ValidationError, match="non-abstained"):
        AnswerResponse(
            answer="Supported answer.",
            confidence=0.8,
            abstained=False,
            requires_human_review=False,
        )

    with pytest.raises(ValidationError):
        Citation(
            document_id=document_id_for("guide/intro.md"),
            source_path="guide/intro.md",
            page_number=0,
        )


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_answer_response_rejects_out_of_range_confidence(confidence: float) -> None:
    with pytest.raises(ValidationError):
        AnswerResponse(
            answer="Insufficient evidence.",
            confidence=confidence,
            abstained=True,
            requires_human_review=True,
        )


def test_answer_response_serializes_to_json() -> None:
    response = AnswerResponse(
        answer="The guide introduces the service.",
        citations=[
            Citation(
                document_id=document_id_for("guides/intro.md"),
                source_path="guides/intro.md",
                heading_path=["Introduction"],
            )
        ],
        confidence=0.9,
        abstained=False,
        requires_human_review=False,
    )

    payload = json.loads(response.model_dump_json())

    assert payload["citations"][0]["source_path"] == "guides/intro.md"
