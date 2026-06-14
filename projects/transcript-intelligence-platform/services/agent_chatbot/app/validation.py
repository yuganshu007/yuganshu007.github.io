"""JSON-schema validation with a bounded repair loop.

LLM output is validated against call_review.schema.json. If it fails, we attempt cheap
deterministic repairs (strip markdown fences, extract the first JSON object) and re-validate.
If still invalid, the caller can ask the model to fix it (one repair round-trip) or fall back.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import jsonschema

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "call_review.schema.json"


class SchemaValidationError(Exception):
    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


@lru_cache(maxsize=1)
def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


@lru_cache(maxsize=1)
def _validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(_schema())


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def coerce_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from raw model text."""
    text = text.strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _OBJ.search(text)
        if m:
            return json.loads(m.group(0))
        raise


def validate(obj: dict) -> list[str]:
    """Return a list of human-readable validation errors ([] if valid)."""
    errors = sorted(_validator().iter_errors(obj), key=lambda e: e.path)
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]


def parse_and_validate(text: str) -> dict:
    """Coerce + validate. Raises SchemaValidationError on failure."""
    try:
        obj = coerce_json(text)
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"not valid JSON: {exc}", ["<root>: invalid JSON"]) from exc
    errs = validate(obj)
    if errs:
        raise SchemaValidationError("schema validation failed", errs)
    return obj
