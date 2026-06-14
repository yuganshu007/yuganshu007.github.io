from __future__ import annotations

import json

import pytest

from services.agent_chatbot.app.validation import (
    SchemaValidationError,
    coerce_json,
    parse_and_validate,
    validate,
)

VALID = {
    "call_id": "call_1",
    "summary": "Advertiser discussed campaign performance and next steps.",
    "sentiment": "neutral",
    "action_items": [],
    "risk_flags": ["none"],
    "confidence": 0.8,
}


def test_valid_passes():
    assert validate(VALID) == []
    assert parse_and_validate(json.dumps(VALID)) == VALID


def test_strips_markdown_fences():
    text = "```json\n" + json.dumps(VALID) + "\n```"
    assert coerce_json(text) == VALID


def test_extracts_object_from_prose():
    text = "Sure! Here is the review: " + json.dumps(VALID) + " Hope that helps."
    assert coerce_json(text) == VALID


def test_missing_required_field_fails():
    bad = {k: v for k, v in VALID.items() if k != "confidence"}
    with pytest.raises(SchemaValidationError) as e:
        parse_and_validate(json.dumps(bad))
    assert any("confidence" in err for err in e.value.errors)


def test_bad_enum_fails():
    bad = {**VALID, "sentiment": "angry"}
    errs = validate(bad)
    assert errs and "sentiment" in errs[0]


def test_confidence_out_of_range_fails():
    bad = {**VALID, "confidence": 1.5}
    assert validate(bad)
