from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from kt_agent.api.deps import get_llm
from kt_agent.llm import LLM, LLMError, LLMResponseError, Message

app = FastAPI(title="KT Agent API", description="API for the KT Agent application")


class CompleteRequest(BaseModel):
    prompt: str = Field(min_length=1)


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int


class CompleteResponse(BaseModel):
    response: str
    model_id: str
    usage: UsageOut
    latency_ms: int


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


# Sync (not async) on purpose: boto3 blocks, so FastAPI runs this in its threadpool.
@app.post("/api/llm/complete", response_model=CompleteResponse)
def llm_complete(body: CompleteRequest, llm: Annotated[LLM, Depends(get_llm)]):
    try:
        reply = llm.send([Message(role="user", text=body.prompt)])
    except LLMError as exc:
        status = 502 if isinstance(exc, LLMResponseError) else 503
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return CompleteResponse(
        response=reply.text,
        model_id=reply.model_id,
        usage=UsageOut(
            input_tokens=reply.input_tokens, output_tokens=reply.output_tokens
        ),
        latency_ms=reply.latency_ms,
    )
