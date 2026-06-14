"""Self-serve analytics dashboard (Streamlit + Plotly) over S3/Athena/Glue.

Locally it builds a gold table from the synthetic corpus and queries it via DuckDB; in production
the same SQL runs on Athena over the Glue catalog. Launch with `make dashboard`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from platform_common.config import settings  # noqa: E402
from services.analytics_dashboard.app.gold import build_gold  # noqa: E402
from services.analytics_dashboard.app.query_engine import QueryEngine  # noqa: E402

st.set_page_config(page_title="Transcript Intelligence Analytics", layout="wide")


@st.cache_resource
def _engine() -> QueryEngine:
    data_dir = os.getenv("DATA_DIR", settings.data_dir)
    if settings.athena_backend == "duckdb":
        build_gold(data_dir)  # ensure the gold table exists locally
    return QueryEngine(data_dir=data_dir, backend=settings.athena_backend)


def _df(query: str) -> pd.DataFrame:
    return pd.DataFrame(_engine().sql(query).rows)


def main() -> None:
    st.title("Transcript Intelligence — Self-Serve Analytics")
    st.caption(
        f"Backend: {settings.athena_backend} • Gold table: daily_tenant_metrics • "
        "Same SQL runs on Athena/Glue in production."
    )
    gold = _engine().gold_path

    totals = _df(
        f"SELECT sum(n_calls) calls, count(DISTINCT tenant) tenants, "
        f"sum(negative_calls) neg FROM read_parquet('{gold}')"
    )
    if not totals.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total calls", f"{int(totals.calls[0]):,}")
        c2.metric("Tenants", int(totals.tenants[0]))
        neg_rate = totals.neg[0] / max(totals.calls[0], 1) * 100
        c3.metric("Negative-call rate", f"{neg_rate:.1f}%")

    st.subheader("Calls by tenant (top 15)")
    top = _df(
        f"SELECT tenant, sum(n_calls) calls FROM read_parquet('{gold}') "
        f"GROUP BY tenant ORDER BY calls DESC LIMIT 15"
    )
    if not top.empty:
        st.plotly_chart(px.bar(top, x="tenant", y="calls"), use_container_width=True)

    st.subheader("Daily call trend")
    trend = _df(
        f"SELECT dt, sum(n_calls) calls FROM read_parquet('{gold}') GROUP BY dt ORDER BY dt"
    )
    if not trend.empty:
        st.plotly_chart(px.line(trend, x="dt", y="calls", markers=True), use_container_width=True)

    st.subheader("Average duration by language")
    lang = _df(
        f"SELECT language, sum(total_duration)/sum(n_calls) avg_duration "
        f"FROM read_parquet('{gold}') GROUP BY language ORDER BY avg_duration DESC"
    )
    if not lang.empty:
        st.plotly_chart(px.bar(lang, x="language", y="avg_duration"), use_container_width=True)


main()
