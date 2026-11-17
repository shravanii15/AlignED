"""sections/model_eval.py: Model Evaluation. The held-out test of the keyword extractor against the LLM extractor,
with confidence intervals, error analysis, and a live try-it box."""

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.database import run_query
from services.evidence import ERROR_ANALYSIS, HELDOUT_RESULTS, load_json
from utils.charts import apply_chart_theme
from utils.layout import page_header
from utils.text import extract_user_skills
from utils.visuals import stat_tiles


def _pct(x):
    return f"{x:.3f}"


def _ci(ci):
    return f"{ci[0]:.2f} to {ci[1]:.2f}"


def _try_extractor():
    st.markdown('<p class="section-eyebrow">Try the extractor</p>', unsafe_allow_html=True)
    sample = st.text_area("Paste any course or job text (up to 3,000 characters)", height=120, max_chars=3000, key="eval_try_text",
                          placeholder="Build ETL pipelines in Python and SQL, orchestrated with Airflow on AWS...")
    if not sample.strip():
        return
    tracked = run_query("SELECT DISTINCT s.skill_id, s.canonical_name FROM extractions e JOIN skills s ON s.skill_id = e.skill_id WHERE e.method = 'baseline_keyword'")
    found = extract_user_skills(sample, tracked)
    names = sorted(str(n) for sid, n in zip(tracked["skill_id"], tracked["canonical_name"]) if sid in found)
    if names:
        st.markdown("".join(f'<span class="chip">{html.escape(n)}</span>' for n in names), unsafe_allow_html=True)
    else:
        st.info("No tracked skills found. This is the recall problem in the table above: the matcher only finds names in its vocabulary.")


def _reversal_chart(res):
    """Grouped bars: F1 on the data both methods were tuned on, and on 50 unseen items."""
    dev, b, m = res["development_set"], res["baseline"], res["llm"]
    fig = go.Figure()
    fig.add_bar(x=["Tuning data (104 items)", "Unseen data (50 items)"], y=[dev["baseline"]["f1"], b["f1"]], name="Keyword matcher",
                marker_color="#2F5BEA", text=[f"{dev['baseline']['f1']:.2f}", f"{b['f1']:.2f}"], textposition="outside")
    fig.add_bar(x=["Tuning data (104 items)", "Unseen data (50 items)"], y=[dev["llm"]["f1"], m["f1"]], name="LLM extractor",
                marker_color="#F59E0B", text=[f"{dev['llm']['f1']:.2f}", f"{m['f1']:.2f}"], textposition="outside")
    fig.update_layout(barmode="group", yaxis=dict(range=[0, 0.55], title="F1 score"), legend=dict(orientation="h", y=1.12))
    apply_chart_theme(fig, height=340)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_model_eval():
    page_header("", "Model Evaluation",
                "Two ways of finding skills in text were tested on 50 items neither had seen. The simpler one won, so it is the one the statistics use.",
                pills=("Held-out test", "95% intervals", "Error analysis"))
    res, err = load_json(HELDOUT_RESULTS), load_json(ERROR_ANALYSIS)
    if not res:
        st.warning("The evaluation results file is not available in this deployment.")
        return
    b, m, dev = res["baseline"], res["llm"], res["development_set"]
    stat_tiles([(_pct(b["f1"]), "keyword F1 (held-out)"), (_pct(m["f1"]), "LLM F1 (held-out)"),
                (f"{res['num_items']}", "unseen items"), (_pct(dev["llm"]["f1"] - dev["baseline"]["f1"]), "LLM edge on tuning data")])
    tab_result, tab_fail, tab_try = st.tabs(["The result", "Where each method fails", "Try the extractor"])
    with tab_result:
        _reversal_chart(res)
        st.markdown(
            f"On the data both methods were tuned on, the LLM looked better. On {res['num_items']} fresh items it was worse "
            f"(**{_pct(m['f1'])} vs {_pct(b['f1'])}**). The 95% bootstrap interval for the difference is {_ci(res['difference_ci95'])}, entirely below zero."
        )
        table = pd.DataFrame([
            {"Method": "Keyword matcher", "Precision": _pct(b["precision"]), "Recall": _pct(b["recall"]), "F1": _pct(b["f1"]), "F1 95% interval": _ci(res["baseline_f1_ci95"])},
            {"Method": "LLM extractor", "Precision": _pct(m["precision"]), "Recall": _pct(m["recall"]), "F1": _pct(m["f1"]), "F1 95% interval": _ci(res["llm_f1_ci95"])},
        ])
        st.dataframe(table, hide_index=True, use_container_width=True)
        st.caption("Labels are AI-drafted and human-verified, not independently hand-labeled. 50 items is small, which is why the intervals are wide. Held-out code and labels are hashed in the results file so they cannot be changed after the fact.")
    with tab_fail:
        _failure_tab(err)
    with tab_try:
        _try_extractor()


def _failure_tab(err):
    if not err:
        st.info("The error analysis file is not available in this deployment.")
        return
    rows = []
    for key, label in (("course", "Course descriptions"), ("posting", "Job postings")):
        s = err["per_source"][key]
        rows.append({"Source": f"{label} ({s['items']})", "Keyword F1": _pct(s["baseline"]["f1"]), "LLM F1": _pct(s["llm"]["f1"]),
                     "Keyword recall": _pct(s["baseline"]["recall"]), "LLM recall": _pct(s["llm"]["recall"])})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    rk = err["recall_by_kind"]
    broad, tools = rk["broad skill or knowledge area"], rk["named tool or technology"]
    fig = go.Figure()
    kinds = [f"Named tools and technologies ({tools['gold_skills']})", f"Broad skill areas ({broad['gold_skills']})"]
    fig.add_bar(x=kinds, y=[tools["baseline"] / tools["gold_skills"], broad["baseline"] / broad["gold_skills"]], name="Keyword matcher", marker_color="#2F5BEA")
    fig.add_bar(x=kinds, y=[tools["llm"] / tools["gold_skills"], broad["llm"] / broad["gold_skills"]], name="LLM extractor", marker_color="#F59E0B")
    fig.update_layout(barmode="group", yaxis=dict(tickformat=".0%", title="Share of gold skills found"), legend=dict(orientation="h", y=1.12))
    apply_chart_theme(fig, height=320)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown(
        "Both methods find named tools about equally, and both miss most broad skill areas such as *computers and electronics* because the vocabulary is O*NET's "
        "and courses rarely use those exact words. This is the main known limit, and the reason the gap statistics are most reliable for named tools."
    )
    with st.expander("Most common errors"):
        for key, label in (("baseline", "Keyword matcher"), ("llm", "LLM extractor")):
            t = err["themes"][key]
            st.markdown(f"**{label}** false positives: " + ", ".join(f"{n} ({c})" for n, c in t["most_common_false_positives"][:5]))
            st.markdown(f"**{label}** misses: " + ", ".join(f"{n} ({c})" for n, c in t["most_common_misses"][:5]))
        st.caption("Generic words such as science, design and monitoring are excluded from the gap statistics, so those keyword false positives do not reach the findings.")
    with st.expander("Browse the 50 items"):
        items = err["items"]
        pick = st.selectbox("Item", range(len(items)), format_func=lambda i: f"{items[i]['id']}: {items[i]['title'][:70]}", key="eval_item")
        it = items[pick]
        st.caption(it["context"])
        st.write(it["text"])
        c1, c2, c3 = st.columns(3)
        c1.markdown("**Gold labels**\n\n" + (", ".join(it["gold"]) or "none"))
        c2.markdown("**Keyword found**\n\n" + (", ".join(it["baseline"]["true_positives"]) or "none"))
        c3.markdown("**LLM found**\n\n" + (", ".join(it["llm"]["true_positives"]) or "none"))
