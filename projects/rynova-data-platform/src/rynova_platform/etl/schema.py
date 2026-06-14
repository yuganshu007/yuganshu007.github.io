"""Schema evolution primitives used by ETL pipelines (Bullet 2).

Supports the three evolution rules Rynova production needed:

* additive — a new nullable column with a default value;
* type widening — int → float, int → str, float → str;
* rename via alias — keeps the old column name readable while migrating.

The runtime enforces these rules every time a stage emits a record, so
upstream schema drift never propagates to the loader stage as a silent
data quality bug.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

_WIDENING: dict[type, set[type]] = {
    int: {int, float, str},
    float: {float, str},
    bool: {bool, int, str},
    str: {str},
}


@dataclass(frozen=True)
class Field:
    name: str
    type: type
    required: bool = True
    default: Any = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Schema:
    name: str
    version: int
    fields: tuple[Field, ...]

    def field_map(self) -> dict[str, Field]:
        out: dict[str, Field] = {}
        for f in self.fields:
            out[f.name] = f
            for alias in f.aliases:
                out[alias] = f
        return out

    def required_names(self) -> set[str]:
        return {f.name for f in self.fields if f.required}

    def validate(self, record: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        fmap = self.field_map()
        seen: set[str] = set()
        for key, value in record.items():
            f = fmap.get(key)
            if f is None:
                errors.append(f"unknown field: {key}")
                continue
            seen.add(f.name)
            if value is None and f.required:
                errors.append(f"required field is null: {f.name}")
                continue
            if value is not None and not isinstance(value, f.type):
                errors.append(
                    f"type mismatch for {f.name}: expected {f.type.__name__}, "
                    f"got {type(value).__name__}"
                )
        missing = self.required_names() - seen
        for name in sorted(missing):
            errors.append(f"missing required field: {name}")
        return errors


@dataclass
class SchemaEvolution:
    """Applies the rules above to migrate a record between schema versions."""

    from_schema: Schema
    to_schema: Schema

    def __post_init__(self) -> None:
        self._rules = self._compile_rules()

    def _compile_rules(self) -> list[str]:
        rules: list[str] = []
        old_fields = self.from_schema.field_map()
        for f in self.to_schema.fields:
            if f.name in old_fields:
                old = old_fields[f.name]
                if old.type is not f.type:
                    if f.type in _WIDENING.get(old.type, set()):
                        rules.append(f"widen:{f.name}:{old.type.__name__}->{f.type.__name__}")
                    else:
                        raise ValueError(
                            f"unsupported type narrowing for {f.name}: "
                            f"{old.type.__name__} → {f.type.__name__}"
                        )
            else:
                if f.required and f.default is None:
                    raise ValueError(
                        f"cannot add required field {f.name!r} without default"
                    )
                rules.append(f"add:{f.name}:{f.default!r}")
            for alias in f.aliases:
                if alias in old_fields and alias != f.name:
                    rules.append(f"rename:{alias}->{f.name}")
        return rules

    @property
    def rules(self) -> list[str]:
        return list(self._rules)

    def apply(self, record: dict[str, Any]) -> dict[str, Any]:
        out = dict(record)
        for f in self.to_schema.fields:
            for alias in f.aliases:
                if alias in out and f.name not in out:
                    out[f.name] = out.pop(alias)
            if f.name not in out:
                out[f.name] = f.default
            value = out[f.name]
            if value is not None and not isinstance(value, f.type):
                # Apply widening
                out[f.name] = f.type(value)
        # Drop fields not in target schema
        target = {f.name for f in self.to_schema.fields}
        return {k: v for k, v in out.items() if k in target}

    def apply_batch(self, records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.apply(r) for r in records]
