"""services/skill_picture.py: the "full picture" for one program.

The significance-tested gap list can be very short (a few programs have a
single clear gap), which makes a report or chart built only from it nearly
empty. This builds the broader, descriptive view that is always useful: the
skills employers ask for most, and how often the program's course
descriptions name each one. It is plain counting, with no significance test,
and it marks which skills also appear in the tested gap list.
"""

import pandas as pd

from services.database import run_query
from utils.constants import AMBIGUOUS_GENERIC_TERMS
from utils.formatting import NAMED_WELL_AT, status_for

def market_picture(program_id, cluster_id, course_count, scope_total_postings, top_n=15):
    """Top `top_n` skills by job-posting demand within the scope, with the
    program's course coverage for each. Columns: skill_id, canonical_name,
    demand, coverage, gap, status."""
    if cluster_id is None:
        demand = run_query(
            """
            SELECT e.skill_id, COUNT(DISTINCT e.source_id) AS n
            FROM extractions e JOIN postings p ON p.posting_id = e.source_id
            WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword' AND p.source = 'kaggle_sample'
            GROUP BY e.skill_id
            """
        )
    else:
        demand = run_query(
            """
            SELECT e.skill_id, COUNT(DISTINCT e.source_id) AS n
            FROM extractions e JOIN posting_cluster_map m ON m.posting_id = e.source_id
            WHERE e.source_type = 'posting' AND e.method = 'baseline_keyword' AND m.cluster_id = ?
            GROUP BY e.skill_id
            """,
            (int(cluster_id),),
        )
    coverage = run_query(
        """
        SELECT e.skill_id, COUNT(DISTINCT e.source_id) AS n
        FROM extractions e JOIN courses c ON c.course_id = CAST(e.source_id AS INTEGER)
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword' AND c.program_id = ?
        GROUP BY e.skill_id
        """,
        (int(program_id),),
    )
    names = run_query("SELECT skill_id, canonical_name FROM skills")
    df = demand.rename(columns={"n": "n_postings"}).merge(
        coverage.rename(columns={"n": "n_courses"}), on="skill_id", how="left"
    ).merge(names, on="skill_id", how="left")
    df["n_courses"] = df["n_courses"].fillna(0)
    df = df[~df["canonical_name"].str.strip().str.lower().isin(AMBIGUOUS_GENERIC_TERMS)]
    df["demand"] = df["n_postings"] / max(float(scope_total_postings), 1.0)
    df["coverage"] = df["n_courses"] / max(float(course_count), 1.0)
    df["gap"] = df["demand"] - df["coverage"]
    df["status"] = df["coverage"].map(status_for)
    df = df.sort_values(["demand", "canonical_name"], ascending=[False, True]).head(top_n)
    return df[["skill_id", "canonical_name", "demand", "coverage", "gap", "status"]].reset_index(drop=True)


def program_matrix(skill_ids):
    """Course coverage of the given skills in every program. Returns
    (matrix, courses): `matrix` has one row per skill_id and one column per
    program label (values 0..1); `courses` maps program label to course count."""
    from utils.formatting import program_label

    programs = run_query(
        "SELECT p.program_id, p.university, p.program_name, "
        "(SELECT COUNT(*) FROM courses c WHERE c.program_id = p.program_id) AS n_courses "
        "FROM programs p ORDER BY p.university, p.program_name"
    )
    programs["label"] = [program_label(u, n) for u, n in zip(programs["university"], programs["program_name"])]
    ids = ",".join(str(int(i)) for i in skill_ids) or "NULL"
    counts = run_query(
        f"""
        SELECT c.program_id, e.skill_id, COUNT(DISTINCT e.source_id) AS n
        FROM extractions e JOIN courses c ON c.course_id = CAST(e.source_id AS INTEGER)
        WHERE e.source_type = 'course' AND e.method = 'baseline_keyword' AND e.skill_id IN ({ids})
        GROUP BY c.program_id, e.skill_id
        """
    )
    matrix = pd.DataFrame(0.0, index=list(skill_ids), columns=list(programs["label"]))
    label_by_id = dict(zip(programs["program_id"], programs["label"]))
    n_by_id = dict(zip(programs["program_id"], programs["n_courses"]))
    for _, r in counts.iterrows():
        label = label_by_id.get(r["program_id"])
        if label is not None and n_by_id[r["program_id"]] > 0:
            matrix.loc[r["skill_id"], label] = r["n"] / n_by_id[r["program_id"]]
    return matrix, dict(zip(programs["label"], programs["n_courses"]))


def summarize(picture, top_n=10):
    """Counts for the headline sentence: how many of the top skills the
    program names at all, and how many it names well."""
    head = picture.head(top_n)
    return {
        "n": len(head),
        "named_at_all": int((head["coverage"] > 0).sum()),
        "named_well": int((head["coverage"] >= NAMED_WELL_AT).sum()),
    }
