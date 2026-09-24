"""sections/methodology.py -- the Methodology & Honest Limitations page.
Every real trade-off and limitation stated openly, the kind of thing an
interviewer would ask about directly.

Redesigned in Sprint 6: the original version was accurate but a single
long wall of markdown text. Same content, now organized into scannable
cards (Data / Taxonomy / Extraction / Statistics / Role grouping), with
deep-dive detail tucked into expanders rather than forcing every visitor
to read the full technical justification just to see the section titles."""

import streamlit as st

from utils.layout import page_header


def render_methodology():
    page_header("🔍", "Methodology & Honest Limitations", "Every real trade-off stated openly -- the kind of thing an interviewer would ask about directly.")

    st.markdown(
        "This page exists on purpose: a portfolio project is only as trustworthy as its documented "
        "limitations. Every simplification below was a deliberate, explained trade-off -- not an oversight."
    )

    # The four-layer trust chain every result on this dashboard passes
    # through -- stated up front so a visitor knows what kind of claim
    # they're looking at before diving into any one page's evidence.
    st.markdown(
        """
        <div class="howitworks-strip">
            <div class="howitworks-step">1. Source</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">2. Extraction</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">3. Statistical test</div><div class="howitworks-arrow">&rarr;</div>
            <div class="howitworks-step">4. Recommendation</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Where did the data come from? How was a skill identified? Is the difference statistically significant? What does the evidence suggest investigating?")

    st.markdown("---")
    st.info(
        "**What \"coverage\" and \"demand\" actually mean, read this first:** both are text-mention "
        "**proxies**, not direct measurements. \"Program coverage\" means a skill's name appears "
        "somewhere in a course's public description -- not that it's taught in depth or assessed. "
        "\"Market demand\" means a skill's name appears in this project's sampled job postings -- not "
        "that every employer strictly requires it. So every gap score should be read as: *this skill "
        "shows up in job-posting text meaningfully more often than in this program's course-description "
        "text.* Real and statistically tested, but a text-coverage signal, not a certified measurement "
        "of what students learn or what every employer requires."
    )

    st.markdown('<p class="section-eyebrow">THE METHODOLOGY, BY LAYER</p>', unsafe_allow_html=True)

    card_col1, card_col2, card_col3 = st.columns(3)
    with card_col1:
        with st.container(border=True):
            st.markdown("**📚 Data sources**")
            st.caption("13 real university catalogs + a live daily job-posting pipeline plus historical backfill.")
            with st.expander("Full detail"):
                st.markdown(
                    """
                    - **Course data:** scraped directly from 13 real university course catalogs
                      (Georgia Tech, ASU, UIUC, Northeastern, BU, Wisconsin, UMD, Penn State, UW, Michigan).
                    - **Job posting data:** a live daily pipeline (Adzuna API, via GitHub Actions) plus a
                      historical backfill of ~124,000 real postings (Kaggle LinkedIn dataset).
                    """
                )
    with card_col2:
        with st.container(border=True):
            st.markdown("**🏷️ Skill taxonomy**")
            st.caption("The official US Department of Labor O\\*NET database -- not an invented list.")
            with st.expander("Full detail"):
                st.markdown(
                    "ESCO (the EU equivalent) was used first and is kept in the project history, but "
                    "O\\*NET was chosen for better coverage of named tools and technologies."
                )
    with card_col3:
        with st.container(border=True):
            st.markdown("**🔎 Extraction method**")
            st.caption("AI (Ollama) benchmarked against a keyword baseline -- AI won, F1 0.400 vs. 0.364.")
            with st.expander("Full detail"):
                st.markdown(
                    """
                    A local, free AI model (Ollama) was compared against a classical keyword-matching
                    baseline on a 104-item hand-labeled test set:

                    | Method | Precision | Recall | F1 |
                    |---|---|---|---|
                    | Baseline (keyword) | 0.518 | 0.280 | 0.364 |
                    | AI (local LLM + embeddings) | 0.407 | 0.392 | **0.400** |

                    The AI method won on F1, the accuracy metric that matters most here. But running it
                    across the *full* 1,378 courses and thousands of postings would take hours on consumer
                    hardware, so the fast keyword method was used deliberately for full-scale analysis -- a
                    real "best model for evaluation, faster model for production scale" trade-off.

                    **On the gold set itself:** the 104 labels (52 courses, 52 postings) were created by a
                    single annotator (the project author) against the O\\*NET vocabulary, without a second
                    reviewer or a measured inter-annotator agreement score. Read this evaluation as an
                    internal benchmark comparing the two extraction methods against each other -- which is
                    exactly what it's used for here -- rather than an independently validated,
                    publication-grade ground truth.
                    """
                )

    card_col4, card_col5 = st.columns(2)
    with card_col4:
        with st.container(border=True):
            st.markdown("**📐 Statistical analysis**")
            st.caption("Two-proportion z-test + Benjamini-Hochberg FDR correction -- dropped 231 gaps to 159.")
            with st.expander("Full detail"):
                st.markdown(
                    """
                    Every program is tested against ~70 skills at once, not just one. Running that many
                    significance tests together means a few "significant" results are expected to be
                    false positives from chance alone, even if every individual test is done correctly --
                    the classic multiple-comparisons problem. To account for this, a Benjamini-Hochberg
                    false discovery rate (FDR) correction is applied across each program's full set of
                    tests before anything is called significant. This is a stricter, more defensible bar
                    than raw p-values alone, and it visibly changed the results: applying it dropped the
                    count of "significant" gaps from 231 to 159 across all 13 programs -- exactly the kind
                    of honest tightening a real statistical review should produce.
                    """
                )
    with card_col5:
        with st.container(border=True):
            st.markdown("**🧩 Role grouping**")
            st.caption("Sentence embeddings + k-means. Silhouette score: 0.08 -- disclosed, not hidden.")
            with st.expander("Full detail"):
                st.markdown(
                    """
                    Role groups come from clustering sentence embeddings of job-posting text with k-means.
                    The resulting silhouette score is modest (0.08) -- normal and expected for real,
                    overlapping job-posting text (a "DevOps Engineer" and "Cloud Engineer" posting
                    legitimately share a lot of language). A hand sanity-check of sampled postings per
                    cluster confirmed most clusters are genuinely coherent by role. Interpret these as
                    **broad role groups**, not definitive occupations.
                    """
                )

    st.markdown("---")
    st.markdown('<p class="section-eyebrow">KNOWN, DOCUMENTED LIMITATIONS</p>', unsafe_allow_html=True)
    st.caption("A master's-level project isn't one with no limitations -- it's one that knows exactly what its limitations are.")
    with st.expander("Keyword matching can't disambiguate context"):
        st.markdown(
            "A handful of generic single-word skill names (e.g. \"Design\", \"Science\") were excluded "
            "from gap/trend analysis because a keyword scanner can't tell them apart from unrelated "
            "everyday text."
        )
    with st.expander("The historical posting dataset's timestamps are skewed"):
        st.markdown(
            "68% of the ~124,000 postings are dated in a single final week -- almost certainly a "
            "data-collection artifact, not real hiring activity. Trend analysis was restricted to the 6 "
            "weeks with real volume (>=100 postings) rather than reporting a misleading result across "
            "mostly-empty weeks."
        )
    with st.expander("The AI evaluation's threshold was tuned on the same set it was scored on"):
        st.markdown(
            "The embedding similarity cutoff used in the AI evaluation was tuned against the same "
            "104-item set used for final reporting -- a known, deliberate simplification for a project "
            "of this scope (the more textbook-correct approach would use a separate held-out set)."
        )
