-- AlignED database schema
-- Plain-language note: each CREATE TABLE below defines one "type" of
-- information we store, and what fields it has. Think of each table
-- like a spreadsheet tab with consistent columns.

CREATE TABLE IF NOT EXISTS programs (
    program_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university TEXT NOT NULL,
    program_name TEXT NOT NULL,
    tier TEXT,                 -- e.g. 'top-ranked', 'mid-tier', 'online'
    url TEXT
);

CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    course_code TEXT,
    course_name TEXT NOT NULL,
    description TEXT,
    is_elective INTEGER DEFAULT 0,   -- 0 = core/required, 1 = elective
    FOREIGN KEY (program_id) REFERENCES programs(program_id)
);

CREATE TABLE IF NOT EXISTS postings (
    posting_id TEXT PRIMARY KEY,     -- Adzuna's own job ID
    source TEXT NOT NULL,            -- e.g. 'adzuna'
    title TEXT,
    company TEXT,
    location TEXT,
    description TEXT,
    salary_min REAL,
    salary_max REAL,
    posted_date TEXT
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    taxonomy_source TEXT,            -- e.g. 'ONET', 'ESCO'
    category TEXT
);

CREATE TABLE IF NOT EXISTS extractions (
    extraction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,       -- 'course' or 'posting'
    source_id TEXT NOT NULL,
    skill_id INTEGER,
    confidence REAL,
    method TEXT,                     -- 'llm' or 'baseline_keyword'
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id)
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
    FOREIGN KEY (posting_id) REFERENCES postings(posting_id),
    FOREIGN KEY (cluster_id) REFERENCES role_clusters(cluster_id)
);

CREATE TABLE IF NOT EXISTS skill_trends (
    trend_id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id INTEGER NOT NULL,
    weeks_covered INTEGER,           -- how many weekly data points went into this trend
    slope REAL,                      -- change in demand rate per week (linear regression)
    p_value REAL,                    -- is the slope statistically real, or could it be noise?
    r_squared REAL,                  -- how well a straight line fits the weekly data
    trend_label TEXT,                -- 'rising', 'falling', or 'no clear trend'
    first_half_rate REAL,            -- simple baseline: avg demand rate, first half of weeks
    second_half_rate REAL,           -- simple baseline: avg demand rate, second half of weeks
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id)
);

CREATE TABLE IF NOT EXISTS gap_scores (
    gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,       -- which specific skill this gap row is about
    cluster_id INTEGER,              -- NULL = compared against overall market demand (all role clusters)
    period TEXT,                     -- e.g. '2023-2024' (the date range of the postings used for demand)
    program_coverage_rate REAL,      -- fraction of this program's courses that mention the skill
    market_demand_rate REAL,         -- fraction of postings that mention the skill
    gap_value REAL,                  -- market_demand_rate - program_coverage_rate (positive = real gap)
    p_value REAL,                    -- two-proportion z-test p-value (is the gap statistically real, not noise?)
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id),
    FOREIGN KEY (cluster_id) REFERENCES role_clusters(cluster_id)
);
