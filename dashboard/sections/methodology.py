"""sections/methodology.py -- the Methodology & Honest Limitations page.
Every real trade-off and limitation stated openly, the kind of thing an
interviewer would ask about directly."""

import streamlit as st


def render_methodology():
    st.title("🔍 Methodology & Honest Limitations")
    st.markdown(
        """
        This page exists on purpose: a portfolio project is only as
        trustworthy as its documented limitations. Every simplification
        below was a deliberate, explained trade-off -- not an oversight.

        ### What "coverage" and "demand" actually mean (read this first)
        Two terms are used constantly across this dashboard, and both are
        **proxies**, not direct measurements:

        - **"Program coverage"** means *a skill's name appears somewhere in
          a course's public description*. It does **not** mean students
          are taught that skill in depth, assessed on it, or come out able
          to use it professionally. A one-line mention in an elective
          course description counts the same as a semester-long required
          sequence -- that's a real limitation of text-based coverage, not
          a claim about learning outcomes.
        - **"Market demand"** means *a skill's name appears in this
          project's sampled job postings*. It does **not** mean every
          employer strictly requires it -- postings often list aspirational
          or boilerplate requirements, and this project's posting sample
          (Adzuna + a historical Kaggle corpus) is not a random, unbiased
          sample of the entire labor market. It reflects what's observed in
          *this* corpus.

        So every gap score on this dashboard should be read as: *"This
        skill shows up in job posting text meaningfully more often than it
        shows up in this program's course-description text."* That is a
        real, statistically tested signal worth paying attention to -- but
        it is a text-coverage signal, not a certified measurement of what
        students actually learn or what every employer actually requires.

        ### Data sources
        - **Course data:** scraped directly from 13 real university course
          catalogs (Georgia Tech, ASU, UIUC, Northeastern, BU, Wisconsin,
          UMD, Penn State, UW, Michigan).
        - **Job posting data:** a live daily pipeline (Adzuna API, via
          GitHub Actions) plus a historical backfill of ~124,000 real
          postings (Kaggle LinkedIn dataset).
        - **Skills taxonomy:** the official US Department of Labor O\\*NET
          database -- not an invented list. ESCO (the EU equivalent) was
          used first and is kept in the project history, but O\\*NET was
          chosen for better coverage of named tools.

        ### AI vs. classical extraction -- an actual, measured comparison
        A local, free AI model (Ollama) was compared against a classical
        keyword-matching baseline on a 104-item hand-labeled test set:

        | Method | Precision | Recall | F1 |
        |---|---|---|---|
        | Baseline (keyword) | 0.518 | 0.280 | 0.364 |
        | AI (local LLM + embeddings) | 0.407 | 0.392 | **0.400** |

        The AI method won on the accuracy metric that matters most here
        (F1). But running it across the *full* 1,378 courses and
        thousands of postings would take hours on consumer hardware, so
        the fast keyword method was used deliberately for full-scale
        analysis -- a real "best model for evaluation, faster model for
        production scale" engineering trade-off.

        **On the gold set itself:** the 104 labels (52 courses, 52
        postings) were created by a single annotator (the project author)
        against the O\\*NET vocabulary, without a second reviewer or a
        measured inter-annotator agreement score. That means this
        evaluation should be read as an internal benchmark for comparing
        the two extraction methods against each other -- which is exactly
        what it's used for here -- rather than as an independently
        validated, publication-grade ground truth. A larger, multi-reviewer
        gold set is a natural next step if this evaluation needs to support
        a stronger claim later.

        ### Correcting for running many statistical tests at once
        Every program is tested against ~70 skills at once, not just one.
        Running that many significance tests together means a few
        "significant" results are expected to be false positives from
        chance alone, even if every individual test is done correctly --
        the classic multiple-comparisons problem. To account for this, a
        Benjamini-Hochberg false discovery rate (FDR) correction is
        applied across each program's full set of tests before anything
        is called significant. This is a stricter, more defensible bar
        than using raw p-values alone, and it visibly changes the results:
        applying it dropped the count of "significant" gaps from 231 to
        159 across all 13 programs -- exactly the kind of honest
        tightening a real statistical review should produce.

        ### Known, documented limitations
        - **Keyword matching can't disambiguate context.** A handful of
          generic single-word skill names (e.g. "Design", "Science") were
          excluded from gap/trend analysis because a keyword scanner can't
          tell them apart from unrelated everyday text.
        - **The historical posting dataset's timestamps are skewed.** 68%
          of the ~124,000 postings are dated in a single final week --
          almost certainly a data-collection artifact, not real hiring
          activity. Trend analysis was restricted to the 6 weeks with real
          volume (>=100 postings) rather than reporting a misleading
          result across mostly-empty weeks.
        - **Role clustering's silhouette score is modest (0.08).** This is
          normal and expected for real, overlapping job-posting text (a
          "DevOps Engineer" and "Cloud Engineer" posting legitimately
          share a lot of language) -- a hand sanity-check of sampled
          postings per cluster confirmed most clusters are genuinely
          coherent by role.
        - **The gap-score threshold-tuning note:** the embedding
          similarity cutoff used in the AI evaluation was tuned against
          the same 104-item set used for final reporting, a known,
          deliberate simplification for a project of this scope (the more
          textbook-correct approach would use a separate held-out set).
        """
    )
