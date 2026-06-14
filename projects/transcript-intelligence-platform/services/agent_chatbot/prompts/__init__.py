"""Versioned prompt templates (prompt engineering lives here, not inline in code)."""
from __future__ import annotations

PROMPT_VERSION = "v3"

SYSTEM_PROMPT = """You are a meticulous advertiser-support call reviewer.
Given a call transcript, produce a STRICT JSON object that conforms to the CallReview schema.

Rules:
- Output ONLY a single JSON object. No prose, no markdown fences.
- `summary`: 1-3 sentences, factual, no speculation.
- `sentiment`: one of positive | neutral | negative.
- `action_items`: concrete next steps for the rep; [] if none.
- `risk_flags`: any of billing_dispute, policy_violation, churn_risk, compliance; use ["none"] if clean.
- `confidence`: your calibrated confidence in [0,1].
"""

# Few-shot example reinforces the exact output contract (prompt engineering).
FEW_SHOT_USER = """TRANSCRIPT (call_id=call_example):
agent: Thanks for calling about your campaign.
advertiser: My invoice looks wrong and I'm thinking of leaving.
"""

FEW_SHOT_ASSISTANT = """{"call_id":"call_example","summary":"Advertiser disputes an invoice and signals possible churn.","sentiment":"negative","action_items":["Open a billing review","Schedule a retention follow-up"],"risk_flags":["billing_dispute","churn_risk"],"confidence":0.82}"""


def build_user_prompt(call_id: str, transcript: str) -> str:
    return f"TRANSCRIPT (call_id={call_id}):\n{transcript}\n\nReturn the CallReview JSON now."
