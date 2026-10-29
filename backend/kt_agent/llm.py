"""Stateless LLM layer: the only module that knows about boto3 / Bedrock.

Callers supply the full list of messages on every call. Conversation memory,
prompt building and output validation belong to callers (future ``core/``).
This module must not import fastapi or typer.
"""

import time
from typing import Any, Literal

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    CredentialRetrievalError,
    NoCredentialsError,
    PartialCredentialsError,
    ProfileNotFound,
    ReadTimeoutError,
    TokenRetrievalError,
)
from botocore.exceptions import (
    ConnectionError as BotoConnectionError,
)
from pydantic import Field

from kt_agent.config import Settings
from kt_agent.models import DomainModel


class Message(DomainModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1)


class Reply(DomainModel):
    text: str
    model_id: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    latency_ms: int


class LLMError(Exception):
    """Base class for all errors raised by this layer."""


class LLMConfigError(LLMError):
    """Missing/unknown profile, or missing/expired credentials."""


class LLMAccessDeniedError(LLMError):
    """The profile may not invoke the configured model."""


class LLMThrottledError(LLMError):
    """Bedrock throttled the request (after retries)."""


class LLMUnavailableError(LLMError):
    """Timeout or Bedrock unreachable."""


class LLMResponseError(LLMError):
    """Bedrock rejected the request or returned an unusable response."""


_CREDENTIAL_ERROR_CODES = {
    "ExpiredTokenException",
    "UnrecognizedClientException",
    "InvalidSignatureException",
    "InvalidClientTokenId",
}
_THROTTLE_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceQuotaExceededException",
}


class LLM:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._settings = settings
        self._client = client

    def send(self, messages: list[Message]) -> Reply:
        if not messages:
            raise ValueError("messages must not be empty")

        client = self._get_client()
        start = time.perf_counter()
        try:
            raw = client.converse(**self._to_converse(messages))
        except LLMError:
            raise
        except Exception as exc:
            raise _translate(exc) from exc
        latency_ms = round((time.perf_counter() - start) * 1000)
        return self._from_converse(raw, latency_ms)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._settings.profile:
            raise LLMConfigError(
                "No AWS profile configured. Set KT_LLM_PROFILE "
                "(e.g. in backend/.env)."
            )
        try:
            session = boto3.Session(profile_name=self._settings.profile)
            self._client = session.client(
                "bedrock-runtime",
                region_name=self._settings.region,
                config=Config(
                    retries={
                        "max_attempts": self._settings.max_retries,
                        "mode": "adaptive",
                    },
                    read_timeout=self._settings.read_timeout,
                ),
            )
        except Exception as exc:
            raise _translate(exc) from exc
        return self._client

    def _to_converse(self, messages: list[Message]) -> dict[str, Any]:
        return {
            "modelId": self._settings.model_id,
            "messages": [
                {"role": m.role, "content": [{"text": m.text}]} for m in messages
            ],
            "inferenceConfig": {"maxTokens": self._settings.max_tokens},
        }

    def _from_converse(self, raw: dict[str, Any], latency_ms: int) -> Reply:
        try:
            blocks = raw["output"]["message"]["content"]
            text = "".join(b["text"] for b in blocks if "text" in b)
            usage = raw["usage"]
            reply = Reply(
                text=text,
                model_id=self._settings.model_id,
                input_tokens=usage["inputTokens"],
                output_tokens=usage["outputTokens"],
                stop_reason=raw["stopReason"],
                latency_ms=latency_ms,
            )
        except (KeyError, TypeError) as exc:
            raise LLMResponseError(
                f"Unexpected response shape from Bedrock: {exc!r}"
            ) from exc
        if not reply.text.strip():
            raise LLMResponseError("Bedrock returned an empty response.")
        return reply


def _translate(exc: Exception) -> LLMError:
    """Map boto3/botocore exceptions to our own error types."""
    if isinstance(exc, ProfileNotFound):
        return LLMConfigError(f"AWS profile not found: {exc}")
    if isinstance(
        exc,
        (
            NoCredentialsError,
            PartialCredentialsError,
            CredentialRetrievalError,
            TokenRetrievalError,
        ),
    ):
        return LLMConfigError(
            "AWS credentials unavailable or expired. If using SSO, run "
            f"`aws sso login --profile <profile>`. ({exc})"
        )
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        message = exc.response.get("Error", {}).get("Message", str(exc))
        if code in _CREDENTIAL_ERROR_CODES:
            return LLMConfigError(
                f"AWS credentials rejected or expired ({code}). If using SSO, "
                "run `aws sso login --profile <profile>`."
            )
        if code == "AccessDeniedException":
            return LLMAccessDeniedError(
                f"Access denied invoking the model: {message}"
            )
        if code in _THROTTLE_ERROR_CODES:
            return LLMThrottledError(f"Bedrock throttled the request: {message}")
        if code == "ModelTimeoutException":
            return LLMUnavailableError(f"Model timed out: {message}")
        return LLMResponseError(f"Bedrock error ({code}): {message}")
    if isinstance(exc, (ReadTimeoutError, BotoConnectionError)):
        return LLMUnavailableError(f"Could not get a response from Bedrock: {exc}")
    if isinstance(exc, BotoCoreError):
        return LLMResponseError(f"AWS client error: {exc}")
    return LLMResponseError(f"Unexpected error calling Bedrock: {exc!r}")
