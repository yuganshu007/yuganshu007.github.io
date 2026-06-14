"""SQL optimization primitives (Bullets 1 & 4).

* :class:`~rynova_platform.sql.query_planner.QueryPlanner` is the async
  facade used by the REST API to execute SQL against a tuned SQLite
  engine on Linux (covering indexes, page-cache friendly reads).
* :mod:`rynova_platform.sql.partitioning` provides date-shard
  partitioning used by Bullet 4.
* :mod:`rynova_platform.sql.pagination` implements keyset pagination
  used by Bullet 4.
"""

from rynova_platform.sql.pagination import Page, PageRequest, keyset_paginate, offset_paginate
from rynova_platform.sql.partitioning import DateShardedTable, ShardKey
from rynova_platform.sql.query_planner import QueryPlanner, QueryResult

__all__ = [
    "QueryPlanner",
    "QueryResult",
    "DateShardedTable",
    "ShardKey",
    "keyset_paginate",
    "offset_paginate",
    "PageRequest",
    "Page",
]
