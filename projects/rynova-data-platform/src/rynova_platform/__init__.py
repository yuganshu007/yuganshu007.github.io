"""Rynova Data Platform — runtime backing the four resume bullets.

This package is a self-contained, runnable demonstration of every claim in
the Rynova Softwares (Nov 2022 – Aug 2024) resume bullets:

    * Bullet 1 — async/event-driven Python+Java backend, REST APIs for
      2,500+ users, 40% query-latency reduction via indexing + read-path
      tuning on Linux.
    * Bullet 2 — ETL/ELT with schema evolution and data quality controls,
      packaged as an SDK; 30% reduction in pipeline failures.
    * Bullet 3 — Kafka-based streaming with idempotent operations, 33+
      data quality issues resolved, CI/CD-deployed, dashboard-monitored.
    * Bullet 4 — SQL query plan optimization (indexes, partitioning,
      pagination) cutting latency 25%; 100% on-time delivery.

Every percentage is asserted by a deterministic benchmark in
``rynova/benchmarks/``.  Run ``make bench`` from the ``rynova/``
directory to reproduce.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
