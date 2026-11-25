"""
services/open_skills.py: measure ANY skill a visitor types.

The main analysis tracks a fixed vocabulary of 235 specific tools. People
list far more than that (SQL, AWS, "machine learning", "stakeholder
management", niche tools). Instead of rejecting what is not in a list, this
module measures any typed skill directly against the raw text already in
the database: how many job postings mention it, and how many course
descriptions name it.

Pure Python (no Streamlit) so it is easy to test and runs in CI.
"""

import re
from dataclasses import dataclass

# Everyday names -> every spelling that should count as the same skill.
# Keys are lowercase; variants keep their natural capitalization.
ALIASES = {
    "sql": ["SQL"],
    "aws": ["AWS", "Amazon Web Services"],
    "amazon web services": ["AWS", "Amazon Web Services"],
    "gcp": ["GCP", "Google Cloud"],
    "google cloud": ["GCP", "Google Cloud"],
    "azure": ["Azure"],
    "ml": ["ML", "machine learning"],
    "machine learning": ["machine learning", "ML"],
    "dl": ["deep learning"],
    "deep learning": ["deep learning"],
    "nlp": ["NLP", "natural language processing"],
    "natural language processing": ["NLP", "natural language processing"],
    "llm": ["LLM", "large language model"],
    "llms": ["LLM", "large language model"],
    "genai": ["GenAI", "generative AI"],
    "generative ai": ["generative AI", "GenAI"],
    "etl": ["ETL"],
    "ci/cd": ["CI/CD", "continuous integration"],
    "rest api": ["REST API", "RESTful"],
    "rest apis": ["REST API", "RESTful"],
    "powerbi": ["Power BI", "PowerBI"],
    "power bi": ["Power BI", "PowerBI"],
    "js": ["JavaScript", "JS"],
    "ts": ["TypeScript"],
    "k8s": ["Kubernetes", "k8s"],
    "postgres": ["PostgreSQL", "Postgres"],
    "nodejs": ["Node.js", "NodeJS"],
    "node": ["Node.js", "NodeJS"],
    "stats": ["statistics", "statistical"],
    "statistics": ["statistics", "statistical"],
    "data viz": ["data visualization", "data visualisation"],
    "data visualisation": ["data visualization", "data visualisation"],
    "sklearn": ["scikit-learn", "sklearn"],
    "scikit learn": ["scikit-learn", "sklearn"],
    "mlops": ["MLOps"],
    "communication skills": ["communication"],
    "teamwork": ["teamwork", "team player", "collaboration"],
}

SHORT_TERM_MAX_LEN = 2   # "R", "Go", "C": matched case-sensitively
MAX_ITEMS = 40
MAX_WORDS = 4

_LEAD_IN = re.compile(
    r"^(?:(?:i\s+(?:have|know|use|used|am|can))\s+|experience\s+(?:with|in)\s+|knowledge\s+of\s+|"
    r"proficient\s+in\s+|proficiency\s+in\s+|familiar\s+with\s+|skilled\s+in\s+|working\s+knowledge\s+of\s+|"
    r"worked\s+with\s+|expertise\s+in\s+|my\s+skills\s+(?:are|include)\s*:?\s*|skills\s*:\s*|"
    r"also\s+|some\s+|basic\s+|strong\s+)+",
    re.IGNORECASE,
)
_SPLIT = re.compile(r"[,;\n\r\t•·|]+|\s+(?:and|&|plus)\s+|\s+/\s+", re.IGNORECASE)
_FILLER = {"etc", "etc.", "more", "others", "other", "and more", "n/a", "none", "skills"}
_HEADINGS = {
    "education", "experience", "work experience", "summary", "projects", "objective", "references",
    "certifications", "contact", "profile", "languages", "technical skills", "professional summary",
}
_KEEP_TOGETHER = ("research and development", "data and analytics", "q and a")


def _looks_like_a_list(text):
    """A short entry, or one with plenty of separators, is a skills list.
    A long run of prose (a resume paragraph) is not."""
    words = len(text.split())
    if words <= 40:
        return True
    separators = len(re.findall(r"[,;\n•·|]", text))
    return separators >= 3 and separators >= words / 6


def _known_terms_in(text):
    """For prose: pick out the skills we have everyday names for."""
    found = []
    for key in ALIASES:
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(key) + r"(?![A-Za-z0-9_])", text, re.IGNORECASE):
            found.append(key)
    return found


def parse_items(text, max_items=MAX_ITEMS):
    """Skill-like items from a typed list or a short sentence.

    "SQL, AWS and basic machine learning" -> ["SQL", "AWS", "machine learning"].
    Long prose (a resume paragraph) yields nothing here; the caller falls
    back to the tracked-skill matcher for that."""
    text = text or ""
    if not _looks_like_a_list(text):
        return _known_terms_in(text)[:max_items]
    for phrase in _KEEP_TOGETHER:
        text = re.sub(re.escape(phrase), phrase.replace(" ", "_"), text, flags=re.IGNORECASE)
    items, seen = [], set()
    for chunk in _SPLIT.split(text):
        chunk = chunk.replace("_", " ") if any(p.replace(" ", "_") in chunk.lower() for p in _KEEP_TOGETHER) else chunk
        item = re.sub(r"\(.*?\)", "", chunk or "")
        item = _LEAD_IN.sub("", item.strip())
        item = item.strip(" \t:-•*\"'").rstrip(".").strip()
        if not item or item.lower() in _FILLER or item.lower() in _HEADINGS:
            continue
        if len(item.split()) > MAX_WORDS or len(item) > 40:
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            items.append(item)
        if len(items) >= max_items:
            break
    return items


def variants_for(term):
    """Every spelling that counts as this skill (the typed one plus aliases)."""
    term = " ".join(str(term).split())
    variants = [term]
    for alias in ALIASES.get(term.lower(), []):
        if alias not in variants:
            variants.append(alias)
    return variants


def build_pattern(variants):
    """One compiled regex for all spellings. Very short names are
    case-sensitive ("R" must not match every "r"); longer ones are not.
    Plain words also match a plural ("dashboard" -> "dashboards")."""
    case_sensitive, insensitive = [], []
    for v in variants:
        piece = re.escape(v)
        if v[-1].isalpha() and len(v) > 3:
            piece += r"(?:s|es)?"
        (case_sensitive if len(v) <= SHORT_TERM_MAX_LEN else insensitive).append(piece)
    parts = []
    if insensitive:
        parts.append("(?i:" + "|".join(insensitive) + ")")
    if case_sensitive:
        parts.append("|".join(case_sensitive))
    return re.compile(r"(?<![A-Za-z0-9_+#])(?:" + "|".join(parts) + r")(?![A-Za-z0-9_+#])")


def mentions(term, text):
    """True if one piece of text mentions the skill."""
    return bool(build_pattern(variants_for(term)).search(text or ""))


class Corpus:
    """A list of texts, pre-lowercased once so a quick substring check can
    skip the regex for most documents."""

    def __init__(self, texts):
        self.texts = [t or "" for t in texts]
        self.lower = [t.lower() for t in self.texts]

    def __len__(self):
        return len(self.texts)

    def count(self, variants, pattern):
        needles = [v.lower() for v in variants]
        return sum(
            1 for text, low in zip(self.texts, self.lower)
            if any(n in low for n in needles) and pattern.search(text)
        )


@dataclass(frozen=True)
class SkillSignal:
    term: str
    posting_n: int
    posting_total: int
    course_n: int
    course_total: int

    @property
    def posting_share(self):
        return self.posting_n / self.posting_total if self.posting_total else 0.0

    @property
    def course_share(self):
        return self.course_n / self.course_total if self.course_total else 0.0

    @property
    def reading(self):
        """Plain-language read of the two numbers. It talks about what
        course descriptions NAME, never about what a program teaches."""
        p, c = self.posting_share, self.course_share
        if self.posting_n == 0 and self.course_n == 0:
            return "Not found in this data. It may be niche or phrased differently."
        if p >= 0.05:
            if c < p / 3:
                return "Employers ask for it much more often than course descriptions name it."
            if c < 0.67 * p:
                return "Employers ask for it somewhat more often than course descriptions name it."
            return "Named in course descriptions about as often as employers ask for it."
        if p >= 0.02:
            return "Some employer demand in this data."
        if self.posting_n > 0:
            return "Rarely asked for in these postings."
        return "Named in course descriptions but not seen in these postings."


def measure(term, postings, courses):
    variants = variants_for(term)
    pattern = build_pattern(variants)
    return SkillSignal(
        term=term,
        posting_n=postings.count(variants, pattern),
        posting_total=len(postings),
        course_n=courses.count(variants, pattern),
        course_total=len(courses),
    )


def measure_items(text, postings, courses):
    """A signal for every skill-like item in the text, most-demanded first."""
    signals = [measure(item, postings, courses) for item in parse_items(text)]
    return sorted(signals, key=lambda s: (-s.posting_n, s.term.lower()))
