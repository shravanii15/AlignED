"""Tests for the company-clustered sensitivity analysis (scripts/gap_analysis/robustness_check.py).

It matters because the headline claim (170 significant gaps) rests on treating postings as independent;
this analysis checks how much of it survives when they are not."""

import json
import os

import pytest

import robustness_check as rc

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cluster_variance_equals_simple_variance_when_every_cluster_is_one_posting():
    clusters = {i: [f"p{i}"] for i in range(100)}
    positives = {f"p{i}" for i in range(30)}
    var = rc.cluster_robust_variance(clusters, positives, 100)
    simple = 0.3 * 0.7 / 100
    assert var == pytest.approx(simple, rel=0.05)


def test_clustered_postings_increase_variance():
    # 10 companies of 10 postings; skill appears in whole companies, so postings are highly alike.
    clusters = {c: [f"{c}-{i}" for i in range(10)] for c in range(10)}
    positives = {m for c in range(3) for m in clusters[c]}
    var = rc.cluster_robust_variance(clusters, positives, 100)
    assert rc.design_effect(var, len(positives), 100) > 5


def test_design_effect_never_below_one():
    assert rc.design_effect(1e-9, 30, 100) == 1.0
    assert rc.design_effect(0.0, 0, 100) == 1.0


def test_newcombe_interval_contains_the_difference_and_is_ordered():
    lo, hi = rc.newcombe_diff_ci(2, 40, 120, 300)
    assert lo < 120 / 300 - 2 / 40 < hi


def test_robust_test_is_less_significant_than_naive_when_deff_is_large():
    _, p_naive, _ = rc.robust_test(0, 40, 80, 1000, 1.0)
    _, p_adj, _ = rc.robust_test(0, 40, 80, 1000, 4.0)
    assert p_adj >= p_naive


@pytest.fixture(scope="module")
def real_run():
    return rc.run(bootstrap_rounds=100)  # fewer rounds: the test checks structure, the committed file holds the full run


def test_real_run_published_gaps_are_partitioned_and_nothing_new_appears(real_run):
    summary, rows = real_run
    assert summary["published_gaps"] == 170
    assert summary["still_significant"] + summary["lost"] == 170
    assert summary["still_significant"] >= 150
    assert summary["newly_significant"] == 0
    for r in rows:
        if r["published_significant"]:
            assert r["gap_ci_low"] <= r["gap"] <= r["gap_ci_high"]


def test_committed_json_matches_a_fresh_run(real_run):
    summary, _ = real_run
    with open(os.path.join(BASE, "data", "robustness", "cluster_robust_gaps.json"), encoding="utf-8") as f:
        saved = json.load(f)["summary"]
    assert saved["still_significant"] == summary["still_significant"]
    assert saved["published_gaps"] == summary["published_gaps"]


def test_bootstrap_intervals_are_ordered_and_cover_the_observed_gap_for_a_strong_signal():
    clusters = {c: [f"{c}-{i}" for i in range(5)] for c in range(200)}
    by_skill = {1: {m for c in range(100) for m in clusters[c]}}  # skill in half of all postings
    out = rc.cluster_bootstrap_intervals(clusters, by_skill, [(1, 1)], {1: 50}, {(1, 1): 0}, rounds=300, seed=3)
    lo, hi = out[(1, 1)]
    assert lo < hi and lo > 0.3 and hi < 0.7  # demand ~0.5, coverage 0


def test_bootstrap_summary_is_in_the_committed_json():
    with open(os.path.join(BASE, "data", "robustness", "cluster_robust_gaps.json"), encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["summary"]["bootstrap_rounds"] == rc.BOOTSTRAP_ROUNDS
    assert all("bootstrap_ci_low" in g for g in saved["gaps"])
