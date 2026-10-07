"""API-key authentication and a per-key rate limiter."""

import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class RateLimiter:
    """Sliding-window limiter held in memory.

    Fine for one process. With several workers or servers each would keep its own counts,
    so a shared store such as Redis would replace this class (same interface).
    """

    def __init__(self, limit, window_seconds=60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window_seconds, clock
        self._hits = defaultdict(deque)

    def check(self, key):
        """Return (allowed, seconds_until_next_slot)."""
        now = self.clock()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False, max(self.window - (now - hits[0]), 0.0)
        hits.append(now)
        return True, 0.0


def key_is_valid(candidate, valid_keys):
    """Constant-time comparison against every configured key (no early exit on a prefix match)."""
    if not candidate:
        return False
    ok = False
    for key in valid_keys:
        ok |= hmac.compare_digest(candidate.encode(), key.encode())
    return ok


def require_api_key(request: Request, provided: str = Security(api_key_header)):
    """Dependency: authenticate, then rate-limit by key. Returns the key's short id for logging.
    Declaring the header through Security() is what adds the Authorize button to /docs."""
    settings = request.app.state.settings
    if not settings.api_keys:
        raise HTTPException(status_code=503, detail="API keys are not configured on the server.")
    if not key_is_valid(provided, settings.api_keys):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.", headers={"WWW-Authenticate": "ApiKey"})
    allowed, retry_after = request.app.state.limiter.check(provided)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.", headers={"Retry-After": str(int(retry_after) + 1)})
    return provided[:4] + "..."
