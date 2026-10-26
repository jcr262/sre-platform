"""
Reflex — reaction time game API.

Reads its database connection from environment variables. If they are missing
the app will fail on startup with a clear message: that is deliberate, your
docker-compose is what supplies them.

Endpoints:
    GET  /api/health      liveness probe
    GET  /api/ready       readiness probe (checks the database)
    GET  /api/scores      top 10 scores
    POST /api/scores      submit a score  {"player": "jorge", "ms": 243}
    GET  /api/stats       aggregate stats
    GET  /metrics         Prometheus metrics
"""

import os
import time
import logging
from contextlib import asynccontextmanager

import psycopg
from psycopg_pool import ConnectionPool
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("reflex")


# --- configuration -----------------------------------------------------------

def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Your compose file / manifest has to provide it."
        )
    return value


DB_HOST = env("DB_HOST")
DB_PORT = env("DB_PORT", "5432")
DB_NAME = env("DB_NAME")
DB_USER = env("DB_USER")
DB_PASSWORD = env("DB_PASSWORD")

CONNINFO = (
    f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} "
    f"user={DB_USER} password={DB_PASSWORD}"
)


# --- metrics -----------------------------------------------------------------

REQUESTS = Counter(
    "reflex_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "reflex_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)
SCORES_SUBMITTED = Counter(
    "reflex_scores_submitted_total",
    "Scores successfully submitted",
)


# --- app ---------------------------------------------------------------------

# The pool opens lazily so the container starts even if Postgres is not up yet.
pool = ConnectionPool(CONNINFO, min_size=1, max_size=10, open=False)


SCHEMA = """
CREATE TABLE IF NOT EXISTS scores (
    id      SERIAL PRIMARY KEY,
    player  TEXT NOT NULL,
    ms      INTEGER NOT NULL CHECK (ms > 0 AND ms < 10000),
    created TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS scores_ms_idx ON scores (ms ASC);
"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Open the pool and make sure the table exists.

    Retries for a while: on a cold `docker compose up` the API usually wins the
    race against Postgres, and that is normal.
    """
    deadline = time.time() + 60
    while True:
        try:
            pool.open(wait=True, timeout=5)
            with pool.connection() as conn:
                conn.execute(SCHEMA)
            log.info("database ready")
            break
        except Exception as exc:  # noqa: BLE001
            if time.time() > deadline:
                log.error("could not reach the database: %s", exc)
                raise
            log.warning("database not ready yet, retrying: %s", exc)
            time.sleep(2)
    yield
    pool.close()


app = FastAPI(title="Reflex API", lifespan=lifespan)


@app.middleware("http")
async def observe(request: Request, call_next):
    path = request.url.path
    start = time.perf_counter()
    response = await call_next(request)
    LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
    REQUESTS.labels(request.method, path, response.status_code).inc()
    return response


# --- models ------------------------------------------------------------------

class ScoreIn(BaseModel):
    player: str = Field(min_length=1, max_length=20)
    ms: int = Field(gt=0, lt=10000)


# --- routes ------------------------------------------------------------------

@app.get("/api/health")
def health():
    """Liveness: the process is up. Does not touch the database."""
    return {"status": "ok"}


@app.get("/api/ready")
def ready():
    """Readiness: the process can serve traffic, database included."""
    try:
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}")


@app.get("/api/scores")
def list_scores(limit: int = 10):
    limit = max(1, min(limit, 100))
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT player, ms, created FROM scores ORDER BY ms ASC LIMIT %s",
            (limit,),
        ).fetchall()
    return [
        {"player": r[0], "ms": r[1], "created": r[2].isoformat()}
        for r in rows
    ]


@app.post("/api/scores", status_code=201)
def add_score(score: ScoreIn):
    try:
        with pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO scores (player, ms) VALUES (%s, %s) RETURNING id",
                (score.player.strip(), score.ms),
            ).fetchone()
    except psycopg.Error as exc:
        log.error("insert failed: %s", exc)
        raise HTTPException(status_code=500, detail="could not save score")
    SCORES_SUBMITTED.inc()
    log.info("score saved player=%s ms=%s", score.player, score.ms)
    return {"id": row[0], "player": score.player, "ms": score.ms}


@app.get("/api/stats")
def stats():
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT count(*), coalesce(min(ms), 0), coalesce(round(avg(ms)), 0) "
            "FROM scores"
        ).fetchone()
    return {"plays": row[0], "best_ms": row[1], "avg_ms": int(row[2])}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
