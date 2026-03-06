from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "negentropy.db"

app = FastAPI(
    title="Negentropy Engine API",
    version="0.1.0-foundation",
    description="T1-T2 foundation build for the Negentropy Engine MVP.",
)


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database is not initialized. Run `python seed.py` first.",
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_all_dicts(query: str) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc
    finally:
        conn.close()


def fetch_one_dict(query: str):
    conn = get_conn()
    try:
        row = conn.execute(query).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc
    finally:
        conn.close()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "build_stage": "t1-t2-foundation",
        "database_exists": DB_PATH.exists(),
    }


@app.get("/events")
def list_events():
    return fetch_all_dicts(
        """
        SELECT
            id,
            title,
            event_type,
            description,
            occurred_at,
            body_delta,
            mind_delta,
            spirit_impact,
            vocation_impact,
            tags_json,
            source,
            notes,
            created_at
        FROM events
        ORDER BY occurred_at DESC, id DESC
        """
    )


@app.get("/snapshot")
def get_latest_snapshot():
    return fetch_one_dict(
        """
        SELECT
            id,
            snapshot_time,
            phase,
            body_level,
            mind_level,
            active_channels_json,
            active_key_nodes_json,
            summary,
            notes,
            created_at
        FROM snapshots
        ORDER BY snapshot_time DESC, id DESC
        LIMIT 1
        """
    )


@app.get("/weekly-review")
def weekly_review():
    return JSONResponse(
        status_code=501,
        content={
            "status": "not_implemented",
            "message": "Weekly review generation is deferred to the next implementation round.",
        },
    )
