"""services/stats.py: the same significance tests the pipeline uses, in pure Python.

The pipeline (scripts/gap_analysis/compute_gap_scores.py) uses SciPy. The dashboard is deployed with a small
dependency list, so the "Analyze Your Program" page needs the same tests without SciPy. tests/test_dashboard_stats.py
checks these functions against SciPy on many random tables, so the two cannot drift apart.
"""

import math

MIN_EXPECTED_CELL_COUNT = 5  # below this the normal approximation is unreliable, so Fisher's exact test is used


def _norm_sf_two_sided(z):
    return math.erfc(abs(z) / math.sqrt(2))


def two_proportion_z_p(x1, n1, x2, n2):
    p_pool = (x1 + x2) / (n1 + n2)
    var = p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)
    if var <= 0:
        return 1.0
    return _norm_sf_two_sided((x2 / n2 - x1 / n1) / math.sqrt(var))


def _log_choose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_exact_p(x1, n1, x2, n2):
    """Two-sided Fisher's exact test on [[x1, n1-x1], [x2, n2-x2]] (sum of tables no more likely than the observed one)."""
    row1, successes, total = n1, x1 + x2, n1 + n2
    log_denom = _log_choose(total, successes)

    def pmf(k):
        return math.exp(_log_choose(row1, k) + _log_choose(total - row1, successes - k) - log_denom)

    observed = pmf(x1)
    lo, hi = max(0, successes - (total - row1)), min(row1, successes)
    return min(1.0, sum(p for p in (pmf(k) for k in range(lo, hi + 1)) if p <= observed * (1 + 1e-7)))


def compare_proportions(x1, n1, x2, n2):
    """(p_value, method) with method 'none', 'fisher_exact' or 'z_test' - the same rule as the pipeline."""
    if n1 <= 0 or n2 <= 0:
        return 1.0, "none"
    successes = x1 + x2
    if successes == 0 or successes == n1 + n2:
        return 1.0, "none"
    total, failures = n1 + n2, n1 + n2 - successes
    expected = [n1 * successes / total, n1 * failures / total, n2 * successes / total, n2 * failures / total]
    if min(expected) < MIN_EXPECTED_CELL_COUNT:
        return fisher_exact_p(x1, n1, x2, n2), "fisher_exact"
    return two_proportion_z_p(x1, n1, x2, n2), "z_test"


def benjamini_hochberg(p_values):
    """Benjamini-Hochberg adjusted p-values (q-values), in the input order."""
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, p_values[i] * m / rank)
        q[i] = running
    return q
