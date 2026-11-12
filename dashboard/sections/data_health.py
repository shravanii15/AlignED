"""sections/data_health.py: Data Health. How the daily job-posting feed is validated, and how it has behaved."""

import pandas as pd
import streamlit as st

from services.evidence import HEALTH_REPORT, load_json
from utils.layout import page_header
from utils.visuals import stat_tiles

PIPELINE = ("Adzuna API", "Raw snapshot (JSON)", "Validate and dedupe", "SQLite", "Rebuild and dbt tests", "Dashboard and API")
CHECKS = (
    "Every record needs an id, title and description; records that fail are rejected and counted, with the reason.",
    "Repeat ids and repeat content are detected, so a posting seen on many days is stored once.",
    "A run where the feed returns far fewer records than usual is flagged as degraded and raises an alert.",
    "Fetch failures retry with backoff. Bad data is not retried, since fetching it again fixes nothing.",
    "dbt tests check the result tables (non-null keys, valid ranges, referential integrity) on every rebuild.",
    "The statistics use a fixed 1,660-posting sample, so a bad day of feed data cannot move a published number.",
)


def render_data_health():
    page_header("", "Data Health",
                "A daily job-posting feed is collected and validated. This page shows how it has behaved, from the stored daily snapshots.")
    rep = load_json(HEALTH_REPORT)
    if not rep:
        st.warning("The ingestion report is not available in this deployment.")
        return
    stat_tiles([(f"{rep['snapshots']}", "daily snapshots"), (f"{rep['fetched']:,}", "records fetched"),
                (f"{rep['unique_valid']:,}", "unique valid postings"), (f"{rep['rejected']}", "records rejected"),
                (f"{rep['degraded_runs']}", "degraded runs")])
    st.caption(f"Snapshots {rep['first_snapshot']} to {rep['last_snapshot']}. Report generated {rep['generated_at'][:10]}.")

    st.markdown('<p class="section-eyebrow">How the pipeline flows</p>', unsafe_allow_html=True)
    arrow = '<div class="howitworks-arrow">&rarr;</div>'
    st.markdown('<div class="howitworks-strip">' + arrow.join(
        f'<div class="howitworks-step">{s}</div>' for s in PIPELINE) + "</div>", unsafe_allow_html=True)

    df = pd.DataFrame(rep["per_snapshot"])
    if not df.empty:
        st.markdown('<p class="section-eyebrow">Fetched vs genuinely new, per day</p>', unsafe_allow_html=True)
        chart = df.set_index("snapshot")[["fetched", "new"]]
        st.bar_chart(chart, color=["#B8C4F0", "#2F5BEA"])
        st.caption(
            f"Most of each day's feed repeats earlier days: {rep['duplicate_ids']:,} repeated ids and {rep['duplicate_content']:,} repeated texts across {rep['fetched']:,} records. "
            "Counting every fetched record would overstate the market; only unique valid postings are kept."
        )
        with st.expander("Per-day table"):
            show = df[["snapshot", "fetched", "rejected", "duplicate_ids", "duplicate_content", "new", "status"]]
            st.dataframe(show, hide_index=True, use_container_width=True)
    if rep["reject_reasons"]:
        st.dataframe(pd.DataFrame(list(rep["reject_reasons"].items()), columns=["Reason", "Records"]), hide_index=True)
    else:
        st.success("No records have been rejected. That says the feed has been clean so far, not that the checks are untested: they are covered by automated tests.")

    st.markdown('<p class="section-eyebrow">What is checked</p>', unsafe_allow_html=True)
    for c in CHECKS:
        st.markdown(f"- {c}")
