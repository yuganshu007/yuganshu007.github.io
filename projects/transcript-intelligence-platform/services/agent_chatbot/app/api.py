"""FastAPI surface for the transcript agent (the chatbot endpoint)."""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from platform_common.config import settings
from platform_common.logging import get_logger
from services.agent_chatbot.app.agent import TranscriptAgent

log = get_logger("agent-api")
app = FastAPI(title="Transcript Intelligence Agent", version="0.1.0")
_agent = TranscriptAgent()


class ReviewRequest(BaseModel):
    call_id: str
    transcript: str = Field(min_length=1)
    advertiser_id: str = "adv_0000"
    tenant: str = "salesforce"


class ReviewResponse(BaseModel):
    review: dict
    latency_s: float
    tools_used: list[str]
    repaired: bool
    used_fallback: bool


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "backend": settings.llm_backend, "model": settings.bedrock_model_id}


@app.post("/review", response_model=ReviewResponse)
def review(req: ReviewRequest) -> ReviewResponse:
    result = _agent.review_call(req.call_id, req.transcript, req.advertiser_id, req.tenant)
    log.info(
        "review",
        call_id=req.call_id,
        latency_s=round(result.latency_s, 3),
        repaired=result.repaired,
        used_fallback=result.used_fallback,
    )
    return ReviewResponse(
        review=result.review,
        latency_s=result.latency_s,
        tools_used=result.tools_used,
        repaired=result.repaired,
        used_fallback=result.used_fallback,
    )
