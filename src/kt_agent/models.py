from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

METADATA_PROMPT_VERSION = "v1"
ANSWER_PROMPT_VERSION = "v1"


class FileType(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"


class FileOutcome(StrEnum):
    ADDED = "added"
    UPDATED = "updated"
    SKIPPED = "skipped"
    REMOVED = "removed"
    FAILED = "failed"


def normalize_source_path(source_path: str) -> str:
    path = PurePosixPath(source_path.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or str(path) == ".":
        raise ValueError("source_path must be a corpus-relative path")
    return str(path)


def document_id_for(source_path: str) -> str:
    normalized_path = normalize_source_path(source_path)
    digest = sha256(normalized_path.encode("utf-8")).hexdigest()
    return f"doc_{digest}"


def validate_normalized_source_path(source_path: str) -> str:
    normalized_path = normalize_source_path(source_path)
    if source_path != normalized_path:
        raise ValueError("source_path must be normalized")
    return source_path


SourcePath = Annotated[
    str,
    Field(min_length=1),
    AfterValidator(validate_normalized_source_path),
]
MetadataTerm = Annotated[str, Field(min_length=1, max_length=100)]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentSection(DomainModel):
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1)
    heading_path: list[str] = Field(default_factory=list)
    page_number: int | None = Field(default=None, ge=1)


class FrontMatter(DomainModel):
    """User-authored fields allowed in Markdown front matter."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    themes: list[MetadataTerm] | None = Field(default=None, max_length=12)
    tags: list[MetadataTerm] | None = Field(default=None, max_length=20)
    content_type: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = Field(default=None, min_length=1, max_length=100)
    summary: str | None = Field(default=None, min_length=1, max_length=2_000)
    version: str | None = Field(default=None, min_length=1, max_length=100)


class GeneratedMetadata(DomainModel):
    """Bedrock-produced metadata, retained even when user fields override it."""

    document_id: str = Field(pattern=r"^doc_[0-9a-f]{64}$")
    summary: str = Field(min_length=1, max_length=2_000)
    themes: list[MetadataTerm] = Field(min_length=1, max_length=12)
    tags: list[MetadataTerm] = Field(min_length=1, max_length=20)
    content_type: str = Field(min_length=1, max_length=100)
    suggested_title: str | None = Field(default=None, min_length=1, max_length=300)


class MetadataBatchResponse(DomainModel):
    documents: list[GeneratedMetadata] = Field(min_length=1, max_length=5)

    def require_exact_document_ids(self, expected_ids: set[str]) -> None:
        actual_ids = [document.document_id for document in self.documents]
        if len(actual_ids) != len(set(actual_ids)):
            raise ValueError("metadata response contains duplicate document IDs")
        if set(actual_ids) != expected_ids:
            raise ValueError("metadata response document IDs do not match request IDs")


class EffectiveMetadata(DomainModel):
    """Resolved metadata used for retrieval, separate from generated metadata."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    summary: str | None = Field(default=None, min_length=1, max_length=2_000)
    themes: list[MetadataTerm] = Field(default_factory=list, max_length=12)
    tags: list[MetadataTerm] = Field(default_factory=list, max_length=20)
    content_type: str | None = Field(default=None, min_length=1, max_length=100)
    status: str | None = Field(default=None, min_length=1, max_length=100)
    version: str | None = Field(default=None, min_length=1, max_length=100)


def effective_metadata(
    deterministic_title: str | None,
    generated: GeneratedMetadata | None,
    front_matter: FrontMatter,
) -> EffectiveMetadata:
    generated_values = (
        {
            "summary": generated.summary,
            "themes": generated.themes,
            "tags": generated.tags,
            "content_type": generated.content_type,
        }
        if generated
        else {}
    )
    title = deterministic_title
    if title is None and generated is not None:
        title = generated.suggested_title
    values = {"title": title, **generated_values}
    values.update(
        {
            field_name: value
            for field_name, value in front_matter.model_dump().items()
            if value is not None
        }
    )
    return EffectiveMetadata.model_validate(values)


class ExtractedDocument(DomainModel):
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{64}$")
    source_path: SourcePath
    file_type: FileType
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_mtime_ns: int = Field(ge=0)
    normalized_content: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    front_matter: FrontMatter = Field(default_factory=FrontMatter)
    sections: list[DocumentSection] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity_and_sections(self) -> Self:
        if self.document_id != document_id_for(self.source_path):
            raise ValueError("document_id does not match source_path")
        if [section.ordinal for section in self.sections] != list(
            range(len(self.sections))
        ):
            raise ValueError("section ordinals must be consecutive and ordered")
        return self


class FileResult(DomainModel):
    source_path: SourcePath
    outcome: FileOutcome
    document_id: str | None = Field(default=None, pattern=r"^doc_[0-9a-f]{64}$")
    error: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_failure_shape(self) -> Self:
        if self.outcome == FileOutcome.FAILED and self.error is None:
            raise ValueError("failed file results require an error")
        if self.outcome != FileOutcome.FAILED and self.error is not None:
            raise ValueError("only failed file results may contain an error")
        return self


class RetrievalResult(DomainModel):
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{64}$")
    source_path: SourcePath
    title: str | None = None
    summary: str | None = None
    themes: list[MetadataTerm] = Field(default_factory=list, max_length=12)
    tags: list[MetadataTerm] = Field(default_factory=list, max_length=20)
    content_type: str | None = None
    status: str | None = None
    version: str | None = None
    excerpt: str = Field(min_length=1)
    score: float
    rank: int = Field(ge=1)


class Citation(DomainModel):
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{64}$")
    source_path: SourcePath
    heading_path: list[str] = Field(default_factory=list)
    page_number: int | None = Field(default=None, ge=1)


class AnswerResponse(DomainModel):
    answer: str = Field(min_length=1, max_length=20_000)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    next_action: str | None = Field(default=None, min_length=1, max_length=1_000)
    abstained: bool
    requires_human_review: bool

    @model_validator(mode="after")
    def validate_supported_answer_citations(self) -> Self:
        if not self.abstained and not self.citations:
            raise ValueError("non-abstained answers require at least one citation")
        return self
