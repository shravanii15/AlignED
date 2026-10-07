"""Read-only data access. All SQL lives here, always parameterised (no string-built queries from user input)."""

import os
import sqlite3
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The dashboard's text matcher is pure Python with no Streamlit import, so the API reuses it
# instead of keeping a second copy that could drift.
sys.path.insert(0, os.path.join(BASE_DIR, "dashboard"))
from utils.constants import AMBIGUOUS_GENERIC_TERMS  # noqa: E402
from utils.text import extract_user_skills  # noqa: E402

TIER_ORDER = {"high": 0, "medium": 1, "low": 2}


class Repository:
    def __init__(self, db_path):
        # mode=ro makes the API incapable of writing to the database.
        self.db_path = db_path
        self._tracked = None
        self._demand = None

    def _connect(self):
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _all(self, sql, params=()):
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def ping(self):
        self._all("SELECT 1")
        return True

    # ---- programs ----
    def programs(self, university=None, limit=20, offset=0):
        where, params = "", []
        if university:
            where, params = "WHERE LOWER(p.university) LIKE ?", [f"%{university.lower()}%"]
        total = self._all(f"SELECT COUNT(*) AS n FROM programs p {where}", params)[0]["n"]
        rows = self._all(
            f"""SELECT p.program_id, p.university, p.program_name, p.tier,
                       (SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) AS course_count
                FROM programs p {where} ORDER BY p.university, p.program_name LIMIT ? OFFSET ?""",
            params + [limit, offset],
        )
        return total, rows

    def program(self, program_id):
        rows = self._all(
            """SELECT p.program_id, p.university, p.program_name, p.tier,
                      (SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) AS course_count
               FROM programs p WHERE p.program_id = ?""",
            (program_id,),
        )
        return rows[0] if rows else None

    def clusters(self):
        return self._all("SELECT cluster_id, role_label FROM role_clusters ORDER BY cluster_id")

    # ---- gaps ----
    def gaps(self, program_id, cluster_id=None, tier=None, limit=20, offset=0):
        scope = "g.cluster_id IS NULL" if cluster_id is None else "g.cluster_id = ?"
        params = [program_id] + ([] if cluster_id is None else [cluster_id])
        tier_clause = ""
        if tier:
            tier_clause, params = "AND r.priority_tier = ?", params + [tier]
        base = f"""
            FROM gap_scores g
            JOIN skills s ON s.skill_id = g.skill_id
            LEFT JOIN recommendations r ON r.program_id = g.program_id AND r.skill_id = g.skill_id AND r.cluster_id IS g.cluster_id
            WHERE g.program_id = ? AND {scope} {tier_clause}"""
        total = self._all(f"SELECT COUNT(*) AS n {base}", params)[0]["n"]
        rows = self._all(
            f"""SELECT s.canonical_name AS skill, g.market_demand_rate, g.program_coverage_rate, g.gap_value,
                       g.q_value, g.test_method, r.priority_tier, r.priority_score, r.trend_label, r.rationale
                {base}
                ORDER BY CASE r.priority_tier WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
                         r.priority_score DESC, g.gap_value DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        )
        return total, rows

    # ---- matching ----
    def _vocabulary(self):
        if self._tracked is None:
            df = pd.DataFrame(self._all(
                """SELECT DISTINCT s.skill_id, s.canonical_name
                   FROM extractions e JOIN skills s ON s.skill_id = e.skill_id
                   WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword'"""))
            self._tracked = df[~df["canonical_name"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)]
        return self._tracked

    def _market_demand(self):
        if self._demand is None:
            total = self._all("SELECT COUNT(*) AS n FROM postings WHERE source = 'kaggle_sample'")[0]["n"]
            rows = self._all(
                """SELECT skill_id, COUNT(DISTINCT source_id) AS n FROM extractions
                   WHERE source_type = 'posting' AND method = 'baseline_keyword' GROUP BY skill_id""")
            self._demand = {r["skill_id"]: r["n"] / max(total, 1) for r in rows}
        return self._demand

    def match(self, job_text, my_text):
        vocab = self._vocabulary()
        names = dict(zip(vocab["skill_id"], vocab["canonical_name"]))
        demand = self._market_demand()
        job_ids = extract_user_skills(job_text, vocab)
        my_ids = extract_user_skills(my_text, vocab) if my_text.strip() else set()

        def entry(i):
            return {"skill": names[i], "market_demand_rate": round(demand.get(i, 0.0), 4)}

        order = lambda ids: sorted(ids, key=lambda i: (-demand.get(i, 0.0), names[i]))  # noqa: E731
        return ([entry(i) for i in order(job_ids & my_ids)], [entry(i) for i in order(job_ids - my_ids)], len(job_ids))
