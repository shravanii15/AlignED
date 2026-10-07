"""Settings, read from environment variables so no secret or path is hard-coded."""

import os
from dataclasses import dataclass, field

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Settings:
    db_path: str = field(default_factory=lambda: os.environ.get("ALIGNED_DB_PATH") or os.path.join(BASE_DIR, "database", "aligned.db"))
    # Comma-separated list of accepted API keys. If empty, every protected route is refused (fail closed).
    api_keys: tuple = field(default_factory=lambda: tuple(k.strip() for k in os.environ.get("ALIGNED_API_KEYS", "").split(",") if k.strip()))
    rate_limit_per_minute: int = field(default_factory=lambda: int(os.environ.get("ALIGNED_RATE_LIMIT_PER_MINUTE", "60")))
    max_text_chars: int = 20_000
