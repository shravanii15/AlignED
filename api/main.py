"""
AlignED REST API.

    ALIGNED_API_KEYS=my-secret-key uvicorn api.main:app --reload
    open http://127.0.0.1:8000/docs

Design notes:
  - Versioned under /v1 so the response shape can change later without breaking callers.
  - Read-only: the database is opened in read-only mode.
  - Auth: X-API-Key header, compared in constant time. With no keys configured, protected routes refuse (fail closed).
  - Rate limit: per key, sliding window, 429 with Retry-After.
  - Every response carries an X-Request-ID, and every request is logged as one JSON line.
"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from api.config import Settings
from api.repository import Repository
from api.schemas import GapPage, Health, MatchRequest, MatchResponse, Program, ProgramPage
from api.security import RateLimiter, require_api_key

VERSION = "1.0.0"
log = logging.getLogger("aligned.api")

v1 = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])


def repo(request: Request) -> Repository:
    return request.app.state.repo


@v1.get("/programs", response_model=ProgramPage, summary="List graduate programs")
def list_programs(university: str = Query(None, max_length=100, description="Filter by university name (substring)"),
                  limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), r: Repository = Depends(repo)):
    total, rows = r.programs(university, limit, offset)
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@v1.get("/programs/{program_id}/gaps", response_model=GapPage, summary="Skills employers want that a program does not cover")
def program_gaps(program_id: int, cluster_id: int = Query(None, description="Role cluster id from /v1/clusters. Omit for the overall market."),
                 tier: str = Query(None, pattern="^(high|medium|low)$"), limit: int = Query(20, ge=1, le=100),
                 offset: int = Query(0, ge=0), r: Repository = Depends(repo)):
    prog = r.program(program_id)
    if not prog:
        raise HTTPException(status_code=404, detail=f"No program with id {program_id}.")
    scope = "overall market"
    if cluster_id is not None:
        match = [c for c in r.clusters() if c["cluster_id"] == cluster_id]
        if not match:
            raise HTTPException(status_code=404, detail=f"No role cluster with id {cluster_id}.")
        scope = match[0]["role_label"]
    total, rows = r.gaps(program_id, cluster_id, tier, limit, offset)
    return {"program": prog, "scope": scope, "total": total, "limit": limit, "offset": offset, "items": rows}


@v1.get("/clusters", summary="List job families (role clusters)")
def list_clusters(r: Repository = Depends(repo)):
    return r.clusters()


@v1.post("/match", response_model=MatchResponse, summary="Compare your skills with a job posting")
def match_job(body: MatchRequest, r: Repository = Depends(repo)):
    have, missing, n = r.match(body.job_text, body.my_skills)
    if n == 0:
        raise HTTPException(status_code=422, detail="No known skills were found in that posting. Paste the full description.")
    fraction = round(len(have) / n, 4) if body.my_skills.strip() else None
    return {"skills_in_posting": n, "have": have, "missing": missing, "match_fraction": fraction}


def create_app(settings: Settings = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="AlignED API", version=VERSION,
                  description="Which skills do employers ask for that a graduate program does not teach?")
    app.state.settings = settings
    app.state.repo = Repository(settings.db_path)
    app.state.limiter = RateLimiter(settings.rate_limit_per_minute)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception(json.dumps({"request_id": request_id, "path": request.url.path, "event": "unhandled_error"}))
            return JSONResponse({"detail": "Internal server error."}, status_code=500, headers={"X-Request-ID": request_id})
        response.headers["X-Request-ID"] = request_id
        log.info(json.dumps({"request_id": request_id, "method": request.method, "path": request.url.path,
                             "status": response.status_code, "ms": round((time.perf_counter() - started) * 1000, 1)}))
        return response

    @app.get("/health", response_model=Health, tags=["ops"], summary="Liveness and database check (no key needed)")
    def health():
        try:
            app.state.repo.ping()
            db = "ok"
        except Exception:
            db = "unavailable"
        return {"status": "ok" if db == "ok" else "degraded", "database": db, "version": VERSION}

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/docs")

    app.include_router(v1)
    return app


app = create_app()
