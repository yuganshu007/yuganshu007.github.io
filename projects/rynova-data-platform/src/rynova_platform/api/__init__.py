"""REST API surface for the Rynova platform (Bullet 1).

The :class:`~rynova_platform.api.service.RynovaService` is an async,
event-driven FastAPI application that exposes the dataset registry, query
plan service, and ingestion event bus used across the rest of the
platform.  It is the concrete artifact behind the "REST APIs serving
2,500+ users" claim in resume Bullet 1.
"""

from rynova_platform.api.service import RynovaService, create_app

__all__ = ["create_app", "RynovaService"]
