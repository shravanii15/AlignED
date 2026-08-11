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

CREATE TABLE IF NOT EXISTS gap_scores (
    gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    cluster_id INTEGER,
    period TEXT,
    gap_value REAL,
    p_value REAL,
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    FOREIGN KEY (cluster_id) REFERENCES role_clusters(cluster_id)
);
