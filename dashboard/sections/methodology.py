"""sections/methodology.py: the Methodology & Limitations page. Organized
into scannable cards (data, taxonomy, extraction, statistics, role
grouping) with detail in expanders, followed by the known limitations."""

import streamlit as st

from utils.layout import page_header


def render_methodology():
    page_header("", "Methodology & Limitations", "How each number is produced, and where it should not be over-read.")

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
    st.caption("Where did the data come from? How was a skill identified? Is the difference significant? What does it suggest investigating?")

    st.info(
        "**Read this first.** Coverage and demand are text-mention proxies, not direct measurements. "
        "Program coverage means a skill's name appears in a course's public description, not that it is taught "
        "in depth. Market demand means the name appears in the sampled job postings, not that every employer "
        "requires it. A gap score says a skill appears in posting text meaningfully more often than in a "
        "program's course text."
    )

    st.markdown('<p class="section-eyebrow">Methodology by Layer</p>', unsafe_allow_html=True)

    card_col1, card_col2, card_col3 = st.columns(3)
    with card_col1:
        with st.container(border=True):
            st.markdown("**Data sources**")
            st.caption("13 university catalogs, a daily job-posting pull, and a historical backfill.")
            with st.expander("Detail"):
                st.markdown(
                    """
                    - **Courses:** scraped from 13 university catalogs (Georgia Tech, ASU, UIUC,
                      Northeastern, BU, Wisconsin, UMD, Penn State, UW, Michigan).
                    - **Postings:** a daily Adzuna pull via GitHub Actions, plus a historical backfill of
                      about 124,000 postings (Kaggle LinkedIn dataset).

                    **The 1,660-posting sample is category-balanced.** It was drawn across a fixed set of
                    tech role categories (software engineering, data science, cybersecurity, DevOps and
                    others) for role clustering, not at random in proportion to the labor market. "Demand"
                    here means demand within this sample.

                    **Course data is not equally complete across programs.** Course counts range from 5
                    (ASU, a sample) to 295 (Georgia Tech's main CS catalog, close to the full public
                    list). Some programs are a full degree catalog, others an elective pool or a sample.
                    The Skill Gaps page flags programs with fewer than 30 courses, because a small corpus can
                    miss skills a larger one would catch.
                    """
                )
    with card_col2:
        with st.container(border=True):
            st.markdown("**Skill taxonomy**")
            st.caption("The US Department of Labor O\\*NET database.")
            with st.expander("Detail"):
                st.markdown(
                    "ESCO (the EU equivalent) was tried first and kept in the project history. "
                    "O\\*NET was chosen for better coverage of named tools and technologies."
                )
    with card_col3:
        with st.container(border=True):
            st.markdown("**Extraction method**")
            st.caption("Local LLM vs. keyword baseline. LLM F1 0.400, keyword 0.364.")
            with st.expander("Detail"):
                st.markdown(
                    """
                    A local model (Ollama) was compared with a keyword-matching baseline on a 104-item
                    hand-labeled set:

                    | Method | Precision | Recall | F1 |
                    |---|---|---|---|
                    | Keyword baseline | 0.518 | 0.280 | 0.364 |
                    | LLM + embeddings | 0.407 | 0.392 | **0.400** |

                    The LLM scored higher on F1, which balances precision and recall. Running it over all
                    1,378 courses and the postings would take hours on consumer hardware, so the keyword
                    method is used at full scale.

                    **Limits of the benchmark:** the 104 labels (52 courses, 52 postings) come from a single
                    annotator with no inter-annotator agreement score, and the similarity threshold was
                    tuned on the same set it was scored on. Treat it as an internal comparison of the two
                    methods, not an independent held-out evaluation.
                    """
                )

    card_col4, card_col5 = st.columns(2)
    with card_col4:
        with st.container(border=True):
            st.markdown("**Statistical analysis**")
            st.caption("Two-proportion z-test (Fisher's exact test for small counts) with Benjamini-Hochberg FDR correction. Cut 236 gaps to 170.")
            with st.expander("Detail"):
                st.markdown(
                    """
                    Each program is tested against about 70 skills at once, so some "significant" results
                    are expected by chance. A Benjamini-Hochberg false discovery rate correction is applied
                    across each program's tests before anything is called significant. Each
                    comparison uses a two-proportion z-test, except that Fisher's exact test is
                    used when any expected cell count is below 5, because the z-test's normal
                    approximation is unreliable for small samples (some programs have only 5 to 19
                    course descriptions). The correction reduced the
                    significant-gap count from 236 to 170 across the 13 programs.

                    **Trend detection uses the same correction.** The demand trends page tests about 67
                    skills at once. Applying FDR correction cut the count of significant trends from 9
                    (raw p-value) to 0 at q < 0.05, so the page presents them as exploratory signals.
                    """
                )
    with card_col5:
        with st.container(border=True):
            st.markdown("**Job families**")
            st.caption("Sentence embeddings and k-means. Silhouette score 0.08.")
            with st.expander("Detail"):
                st.markdown(
                    """
                    Role groups come from k-means clustering of sentence embeddings of posting text. The
                    silhouette score is modest (0.08), which is expected when postings for related roles
                    (a DevOps and a Cloud Engineer posting, for example) share much of their language. A
                    manual check of sampled postings found most groups coherent by role. Treat them as
                    broad role groups, not definitive occupations.
                    """
                )

    st.markdown('<p class="section-eyebrow">Known Limitations</p>', unsafe_allow_html=True)
    with st.expander("Keyword matching cannot disambiguate context"):
        st.markdown(
            "A few generic single-word skill names (such as \"Design\" and \"Science\") were excluded from "
            "gap and trend analysis because a keyword scanner cannot tell them apart from everyday text."
        )
    with st.expander("The historical postings have skewed timestamps"):
        st.markdown(
            "68% of the roughly 124,000 postings are dated to a single final week, most likely a "
            "data-collection artifact. Trend analysis uses only the 6 weeks with at least 100 postings."
        )
    with st.expander("The benchmark is not a held-out evaluation"):
        st.markdown(
            "The embedding similarity cutoff was tuned on the same 104 items used for final reporting. "
            "A separate held-out set would be the standard approach and is a planned improvement."
        )
    with st.expander("The analysis is a snapshot"):
        st.markdown(
            "The daily Adzuna pull adds raw postings, but gap scores and trends are not recomputed from "
            "them. Results reflect the sample and course data as of the last pipeline run."
        )
