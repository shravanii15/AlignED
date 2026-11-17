-- AlignED database schema (version 2)
-- Plain-language note: each CREATE TABLE defines one "type" of information we store and what fields it has.
-- Version 2 adds the rules the pipeline already followed so the database itself enforces them: natural-key
-- uniqueness, value ranges, allowed labels, and indexes for the queries the app runs. See docs/DATABASE.md.
-- Upgrade an existing database file with: python scripts/migrate_schema.py

CREATE TABLE IF NOT EXISTS programs (
    program_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university TEXT NOT NULL,
    program_name TEXT NOT NULL,
    tier TEXT,                 -- e.g. 'top-ranked', 'mid-tier', 'online'
    url TEXT,
    UNIQUE (university, program_name)
);

CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    course_code TEXT,
    course_name TEXT NOT NULL,
    description TEXT,
    is_elective INTEGER DEFAULT 0 CHECK (is_elective IN (0, 1)),   -- 0 = core/required, 1 = elective
    FOREIGN KEY (program_id) REFERENCES programs(program_id)
);

CREATE TABLE IF NOT EXISTS postings (
    posting_id TEXT PRIMARY KEY,     -- Adzuna's own job ID
    source TEXT NOT NULL CHECK (source IN ('kaggle_sample', 'adzuna')),  -- kaggle_sample = the 1,660 used in statistics
    title TEXT,
    company TEXT,
    location TEXT,
    description TEXT,
    salary_min REAL CHECK (salary_min IS NULL OR salary_min >= 0),
    salary_max REAL CHECK (salary_max IS NULL OR salary_max >= 0),
    posted_date TEXT,
    content_hash TEXT,               -- fingerprint of title+company+description, catches reposts under new ids
    ingested_at TEXT                 -- when the ingestion job loaded it (NULL for the historical backfill)
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    taxonomy_source TEXT,            -- e.g. 'ONET', 'ESCO'
    category TEXT
);

-- One row per (text, skill, method) match. source_id holds a course_id or a posting_id depending on source_type,
-- so it cannot carry a foreign key; the migration tests check that every source_id resolves instead.
CREATE TABLE IF NOT EXISTS extractions (
    extraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL CHECK (source_type IN ('course', 'posting')),
    source_id TEXT NOT NULL,
    skill_id INTEGER NOT NULL,
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    method TEXT NOT NULL CHECK (method IN ('llm', 'baseline_keyword')),
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id),
    UNIQUE (source_type, source_id, skill_id, method)
);

CREATE TABLE IF NOT EXISTS role_clusters (
    cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_label TEXT,
    method TEXT,
    silhouette_score REAL
);

CREATE TABLE IF NOT EXISTS posting_cluster_map (
    posting_id TEXT NOT NULL,
    cluster_id INTEGER NOT NULL,
    PRIMARY KEY (posting_id, cluster_id),
    FOREIGN KEY (posting_id) REFERENCES postings(posting_id),
    FOREIGN KEY (cluster_id) REFERENCES role_clusters(cluster_id)
);

CREATE TABLE IF NOT EXISTS skill_trends (
    trend_id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL UNIQUE,
    weeks_covered INTEGER CHECK (weeks_covered IS NULL OR weeks_covered >= 0),  -- weekly data points in the trend
    slope REAL,                      -- change in demand rate per week (linear regression)
    p_value REAL CHECK (p_value IS NULL OR (p_value >= 0 AND p_value <= 1)),
    q_value REAL CHECK (q_value IS NULL OR (q_value >= 0 AND q_value <= 1)),   -- Benjamini-Hochberg corrected; decides trend_label
    r_squared REAL,                  -- how well a straight line fits the weekly data
    trend_label TEXT CHECK (trend_label IS NULL OR trend_label IN ('rising', 'falling', 'no clear trend')),
    first_half_rate REAL,            -- simple baseline: avg demand rate, first half of weeks
    second_half_rate REAL,           -- simple baseline: avg demand rate, second half of weeks
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    cluster_id INTEGER,               -- NULL = program vs. overall market; set = vs. that role cluster's postings only
    gap_value REAL,                  -- from gap_scores: market_demand_rate - program_coverage_rate
    trend_label TEXT,                -- from skill_trends, or 'no trend data' if not tracked
    priority_score REAL,             -- gap_value adjusted up/down based on trend direction
    priority_tier TEXT CHECK (priority_tier IS NULL OR priority_tier IN ('high', 'medium', 'low')),
    rationale TEXT,                  -- plain-English explanation, ready to display
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id),
    FOREIGN KEY (cluster_id) REFERENCES role_clusters(cluster_id)
);

CREATE TABLE IF NOT EXISTS gap_scores (
    gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,       -- which specific skill this gap row is about
    cluster_id INTEGER,              -- NULL = compared against overall market demand (all role clusters)
    period TEXT,                     -- e.g. '2023-2024' (the date range of the postings used for demand)
    program_coverage_rate REAL CHECK (program_coverage_rate IS NULL OR (program_coverage_rate >= 0 AND program_coverage_rate <= 1)),
    market_demand_rate REAL CHECK (market_demand_rate IS NULL OR (market_demand_rate >= 0 AND market_demand_rate <= 1)),
    gap_value REAL,                  -- market_demand_rate - program_coverage_rate (positive = real gap)
    p_value REAL CHECK (p_value IS NULL OR (p_value >= 0 AND p_value <= 1)),    -- raw p-value, before correction
    test_method TEXT CHECK (test_method IS NULL OR test_method IN ('z_test', 'fisher_exact')),  -- exact test when expected counts < 5
    q_value REAL CHECK (q_value IS NULL OR (q_value >= 0 AND q_value <= 1)),    -- Benjamini-Hochberg FDR-corrected; decides significance
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id),
    FOREIGN KEY (cluster_id) REFERENCES role_clusters(cluster_id)
);

-- Ingestion audit trail: one row per ingestion run, plus every rejected posting with its reason.
CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    snapshot_path TEXT,
    fetched INTEGER CHECK (fetched IS NULL OR fetched >= 0),
    rejected INTEGER CHECK (rejected IS NULL OR rejected >= 0),
    duplicate_ids INTEGER CHECK (duplicate_ids IS NULL OR duplicate_ids >= 0),
    duplicate_content INTEGER CHECK (duplicate_content IS NULL OR duplicate_content >= 0),
    inserted INTEGER CHECK (inserted IS NULL OR inserted >= 0),
    warnings INTEGER,
    status TEXT
);
CREATE TABLE IF NOT EXISTS rejected_postings (
    rejection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    posting_id TEXT,
    title TEXT,
    reason TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES ingest_runs(run_id)
);

-- Indexes. Each one serves a query the app or pipeline actually runs (see docs/DATABASE.md).
CREATE INDEX IF NOT EXISTS idx_postings_source_hash ON postings(source, content_hash);
CREATE INDEX IF NOT EXISTS idx_courses_program ON courses(program_id);
CREATE INDEX IF NOT EXISTS idx_extractions_lookup ON extractions(source_type, method, skill_id, source_id);
CREATE INDEX IF NOT EXISTS idx_gap_scores_program_cluster ON gap_scores(program_id, cluster_id);
CREATE INDEX IF NOT EXISTS idx_gap_scores_skill ON gap_scores(skill_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_program_cluster ON recommendations(program_id, cluster_id);
CREATE INDEX IF NOT EXISTS idx_cluster_map_cluster ON posting_cluster_map(cluster_id);
CREATE INDEX IF NOT EXISTS idx_rejected_run ON rejected_postings(run_id);
-- NULL cluster_id means "overall market", and SQL treats NULLs as distinct, so a plain UNIQUE would allow
-- duplicates there. Indexing COALESCE(cluster_id, -1) makes the natural key unique for both cases.
CREATE UNIQUE INDEX IF NOT EXISTS uq_gap_scores_key ON gap_scores(program_id, skill_id, COALESCE(cluster_id, -1));
CREATE UNIQUE INDEX IF NOT EXISTS uq_recommendations_key ON recommendations(program_id, skill_id, COALESCE(cluster_id, -1));

PRAGMA user_version = 2;
