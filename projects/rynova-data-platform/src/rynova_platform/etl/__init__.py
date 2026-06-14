"""ETL/ELT pipeline runtime (Bullet 2).

The pipeline runtime is intentionally tiny: each pipeline is a list of
:class:`Stage`s that operate on dicts, glued together by a
:class:`Pipeline` runner that enforces schema evolution and data quality
checks at the boundary between stages.

The accompanying SDK in :mod:`rynova_platform.validation` packages the
data quality controls so other teams can drop them into their own
pipelines — the "packaged SDK-style data validation modules" claim from
Bullet 2.
"""

from rynova_platform.etl.pipeline import (
    Pipeline,
    PipelineResult,
    Stage,
    StageFailure,
    StageOutcome,
)
from rynova_platform.etl.schema import Field, Schema, SchemaEvolution

__all__ = [
    "Pipeline",
    "PipelineResult",
    "Stage",
    "StageOutcome",
    "StageFailure",
    "Field",
    "Schema",
    "SchemaEvolution",
]
