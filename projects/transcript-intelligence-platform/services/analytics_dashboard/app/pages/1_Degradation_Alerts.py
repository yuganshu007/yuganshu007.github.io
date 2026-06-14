"""Degradation alerts page: shows the metric series and any automated regression alerts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from services.analytics_dashboard.app.degradation import DegradationDetector  # noqa: E402

st.set_page_config(page_title="Degradation Alerts", layout="wide")
st.title("Degradation Alerts")
st.caption(
    "Automated regression detection on pipeline metrics — accelerates incident response by "
    "catching drifts the moment they cross threshold instead of at the next manual review."
)

threshold = st.slider("Drop threshold (%)", 5, 50, 20)
detector = DegradationDetector(drop_threshold_pct=threshold)

# A demo series with a regression in the tail; in production this is a live metric query.
series = [100, 101, 99, 102, 100, 98, 101, 100, 99, 100, 90, 78, 76, 74, 72, 70]
df = pd.DataFrame({"day": range(len(series)), "n_calls": series})
st.plotly_chart(px.line(df, x="day", y="n_calls", markers=True), use_container_width=True)

alert = detector.check("n_calls", series)
if alert:
    st.error(
        f"ALERT [{alert.severity}] {alert.metric}: {alert.pct_change}% vs baseline "
        f"{alert.baseline} (current {alert.current})"
    )
else:
    st.success("No degradation detected.")
