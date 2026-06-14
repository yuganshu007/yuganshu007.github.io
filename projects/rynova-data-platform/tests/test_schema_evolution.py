"""Schema evolution tests (Bullet 2)."""

from __future__ import annotations

import pytest

from rynova_platform.etl.schema import Field, Schema, SchemaEvolution

V1 = Schema(
    name="orders",
    version=1,
    fields=(
        Field("id", int),
        Field("user_id", int),
        Field("amount", float),
    ),
)

V2 = Schema(
    name="orders",
    version=2,
    fields=(
        Field("id", int),
        Field("user_id", int),
        Field("amount", float),
        Field("currency", str, required=False, default="USD"),
    ),
)

V3 = Schema(
    name="orders",
    version=3,
    fields=(
        Field("id", int),
        Field("user_id", int),
        Field("amount", str),  # widened
        Field("currency", str, required=False, default="USD"),
        Field("owner", str, required=False, default="rynova", aliases=("team",)),
    ),
)


def test_validate_accepts_well_formed_row() -> None:
    errors = V1.validate({"id": 1, "user_id": 2, "amount": 9.99})
    assert errors == []


def test_validate_flags_missing_required_field() -> None:
    errors = V1.validate({"id": 1, "user_id": 2})
    assert "missing required field: amount" in errors


def test_validate_flags_unknown_field() -> None:
    errors = V1.validate({"id": 1, "user_id": 2, "amount": 9.0, "extra": 1})
    assert any("unknown field" in e for e in errors)


def test_validate_flags_type_mismatch() -> None:
    errors = V1.validate({"id": "1", "user_id": 2, "amount": 9.0})
    assert any("type mismatch" in e for e in errors)


def test_validate_flags_null_required_field() -> None:
    errors = V1.validate({"id": 1, "user_id": None, "amount": 9.0})
    assert any("required field is null" in e for e in errors)


def test_evolution_adds_optional_field() -> None:
    evo = SchemaEvolution(V1, V2)
    out = evo.apply({"id": 1, "user_id": 2, "amount": 9.99})
    assert out["currency"] == "USD"
    assert "add:currency:'USD'" in evo.rules


def test_evolution_widens_type() -> None:
    evo = SchemaEvolution(V2, V3)
    out = evo.apply({"id": 1, "user_id": 2, "amount": 9.99, "currency": "EUR"})
    assert isinstance(out["amount"], str)
    assert out["amount"] == "9.99"


def test_evolution_rename_via_alias() -> None:
    evo = SchemaEvolution(V2, V3)
    src = {"id": 1, "user_id": 2, "amount": 9.99, "currency": "EUR", "team": "rynova-eng"}
    out = evo.apply(src)
    assert out["owner"] == "rynova-eng"
    assert "team" not in out


def test_evolution_rejects_required_add_without_default() -> None:
    bad = Schema(
        name="orders",
        version=2,
        fields=(
            *V1.fields,
            Field("required_new", str, required=True, default=None),
        ),
    )
    with pytest.raises(ValueError):
        SchemaEvolution(V1, bad)


def test_evolution_rejects_narrowing() -> None:
    narrowed = Schema(
        name="orders",
        version=2,
        fields=(
            Field("id", int),
            Field("user_id", int),
            Field("amount", int),  # narrowing from float
        ),
    )
    with pytest.raises(ValueError):
        SchemaEvolution(V1, narrowed)


def test_evolution_drops_unknown_target_fields() -> None:
    evo = SchemaEvolution(V1, V2)
    out = evo.apply({"id": 1, "user_id": 2, "amount": 1.0, "extra": "x"})
    assert "extra" not in out


def test_evolution_batch() -> None:
    evo = SchemaEvolution(V1, V2)
    out = evo.apply_batch(
        [{"id": i, "user_id": 1, "amount": 1.0} for i in range(5)]
    )
    assert all(r["currency"] == "USD" for r in out)


def test_evolution_preserves_explicit_value() -> None:
    evo = SchemaEvolution(V1, V2)
    out = evo.apply({"id": 1, "user_id": 2, "amount": 1.0, "currency": "EUR"})
    assert out["currency"] == "EUR"
