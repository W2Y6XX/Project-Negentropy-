import asyncio
import contextlib
from pathlib import Path
import json
import os
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from urllib import error as urlerror
from urllib import request as urlrequest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, model_validator


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "negentropy.db"
FRONTEND_DIR = ROOT_DIR / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"
RULE_SET_VERSION = "v1.5.0"
SCHEDULER_ENABLED = os.getenv("ANALYTICS_SCHEDULER_ENABLED", "1") != "0"
try:
    APP_TZ = ZoneInfo("Asia/Shanghai")
except ZoneInfoNotFoundError:
    APP_TZ = timezone(timedelta(hours=8))

app = FastAPI(
    title="Negentropy Engine API",
    version="0.2.0-v1.5",
    description="V1 runtime plus V1.5 analytics layer for the Negentropy Engine MVP.",
)

SCHEDULER_STATE = {
    "enabled": SCHEDULER_ENABLED,
    "task_running": False,
    "last_check_at": None,
    "last_run_started_at": None,
    "last_run_type": None,
    "next_daily_local": None,
    "next_weekly_local": None,
}
_scheduler_task: asyncio.Task | None = None

app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


class EventCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    title: str | None = None
    description: str | None = None
    occurred_at: str | None = None
    body_delta: int | None = None
    mind_delta: int | None = None
    delta_body: int | None = None
    delta_mind: int | None = None
    event_type: str | None = None
    spirit_impact: str | None = None
    vocation_impact: str | None = None
    tags_json: str | None = None
    source: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def normalize(self):
        if self.body_delta is None and self.delta_body is not None:
            self.body_delta = self.delta_body
        if self.mind_delta is None and self.delta_mind is not None:
            self.mind_delta = self.delta_mind

        if self.description:
            self.description = self.description.strip()
        if self.title:
            self.title = self.title.strip()

        if not self.title and self.description:
            self.title = self.description[:80]

        if not self.title:
            raise ValueError("`title` is required, or provide `description` for starter compatibility.")

        if self.occurred_at is None:
            self.occurred_at = datetime.now(timezone.utc).isoformat()

        try:
            parsed = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("`occurred_at` must be a valid ISO 8601 datetime.") from exc

        self.occurred_at = parsed.astimezone(timezone.utc).isoformat()
        self.body_delta = 0 if self.body_delta is None else self.body_delta
        self.mind_delta = 0 if self.mind_delta is None else self.mind_delta
        return self


class KeyNodeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    progress: float | None = None
    status: str | None = None
    notes: str | None = None
    source_event_id: int | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if (
            self.progress is None
            and self.status is None
            and self.notes is None
            and self.source_event_id is None
            and self.reason is None
        ):
            raise ValueError("Provide at least one field to update.")

        if self.progress is not None and not 0 <= self.progress <= 1:
            raise ValueError("`progress` must be between 0 and 1.")

        allowed_statuses = {"pending", "active", "paused", "done", "archived"}
        if self.status is not None and self.status not in allowed_statuses:
            raise ValueError(f"`status` must be one of: {', '.join(sorted(allowed_statuses))}.")

        if self.source_event_id is not None and self.source_event_id <= 0:
            raise ValueError("`source_event_id` must be a positive integer.")

        if self.reason is not None:
            self.reason = self.reason.strip() or None

        return self


class NaturalLanguageEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    occurred_at_hint: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("`text` cannot be empty.")
        return self


class EventConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    structured_event: EventCreate
    original_text: str | None = None
    parser_backend: str | None = None


class WeeklyReviewGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: str | None = None
    week_end: str | None = None
    title: str | None = None


class SnapshotGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = None
    notes: str | None = None


class AnalyticsRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_start: str | None = None
    window_end: str | None = None


class AnalyticsSuggestionReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_status: str
    approved_payload_json: dict | None = None
    reviewer_note: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        allowed_statuses = {"approved", "rejected", "edited"}
        if self.approval_status not in allowed_statuses:
            raise ValueError(f"`approval_status` must be one of: {', '.join(sorted(allowed_statuses))}.")

        if self.approval_status in {"approved", "edited"} and self.approved_payload_json is None:
            raise ValueError("`approved_payload_json` is required for approved or edited suggestions.")

        return self


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database is not initialized. Run `python seed.py` first.",
        )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_all_dicts(query: str, params: tuple = ()) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc
    finally:
        conn.close()


def fetch_one_dict(query: str, params: tuple = ()):
    conn = get_conn()
    try:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc
    finally:
        conn.close()


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def parse_sqlite_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        if "T" in value or "+" in value or value.endswith("Z"):
            return parse_iso_datetime(value)
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return naive.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_request_boundary(value: str, is_end: bool) -> datetime:
    value = value.strip()
    try:
        return parse_iso_datetime(value)
    except ValueError:
        pass

    day_value = date.fromisoformat(value)
    local_time = time.max if is_end else time.min
    return datetime.combine(day_value, local_time, APP_TZ).astimezone(timezone.utc)


def compute_manual_window(window_start: str | None, window_end: str | None) -> tuple[datetime, datetime]:
    now_utc = datetime.now(timezone.utc)
    if window_start is None and window_end is None:
        return now_utc - timedelta(days=30), now_utc

    start_dt = parse_request_boundary(window_start, is_end=False) if window_start else now_utc - timedelta(days=30)
    end_dt = parse_request_boundary(window_end, is_end=True) if window_end else now_utc
    if end_dt < start_dt:
        raise HTTPException(status_code=400, detail="`window_end` must be on or after `window_start`.")
    return start_dt, end_dt


def compute_confidence(sample_count: int) -> str:
    if sample_count >= 10:
        return "high"
    if sample_count >= 3:
        return "medium"
    return "low"


def insert_event(conn: sqlite3.Connection, event: EventCreate) -> dict:
    cur = conn.execute(
        """
        INSERT INTO events (
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
            notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.title,
            event.event_type,
            event.description,
            event.occurred_at,
            event.body_delta,
            event.mind_delta,
            event.spirit_impact,
            event.vocation_impact,
            event.tags_json,
            event.source,
            event.notes,
        ),
    )
    conn.commit()

    row = conn.execute(
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
        WHERE id = ?
        """,
        (cur.lastrowid,),
    ).fetchone()
    return dict(row)


def get_openai_compatible_config() -> dict | None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        return None

    return {
        "api_key": api_key,
        "model": model,
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    }


def heuristic_parse_event(payload: NaturalLanguageEventInput) -> tuple[EventCreate, list[str], str]:
    text = payload.text
    lowered = text.lower()

    body_delta = 0
    mind_delta = 0
    tags: list[str] = []
    event_type = "note"

    if any(token in text for token in ["跑步", "训练", "健身", "散步", "运动"]):
        event_type = "exercise"
        tags.append("exercise")
        body_delta += 1
    if any(token in text for token in ["学习", "刷题", "写作", "论文", "研究", "复习"]):
        event_type = "study"
        tags.append("study")
        mind_delta += 1
    if any(token in text for token in ["休息", "睡觉", "午睡", "恢复"]):
        event_type = "recovery"
        tags.append("recovery")
        body_delta += 1
        mind_delta += 1
    if any(token in text for token in ["累", "疲惫", "困", "透支"]):
        body_delta -= 1
        mind_delta -= 1
    if any(token in text for token in ["专注", "清晰", "高效", "推进"]):
        mind_delta += 1
    if any(token in text for token in ["焦虑", "烦", "崩", "冲突", "争吵"]):
        mind_delta -= 1
        tags.append("stress")
    if any(token in text for token in ["家庭", "父母"]):
        tags.append("family")
    if any(token in lowered for token in ["work", "teaching", "class"]):
        event_type = "work"
        tags.append("work")

    occurred_at = payload.occurred_at_hint or datetime.now(timezone.utc).isoformat()
    structured_event = EventCreate(
        title=text[:80],
        description=text,
        occurred_at=occurred_at,
        body_delta=max(-10, min(10, body_delta)),
        mind_delta=max(-10, min(10, mind_delta)),
        event_type=event_type,
        tags_json=json_dumps(sorted(set(tags))) if tags else None,
        source="natural_language_heuristic",
    )

    warnings = [
        "LLM 未配置，当前结果来自启发式解析。",
        "写入数据库前仍应由用户确认结构化字段。",
    ]
    return structured_event, warnings, "heuristic"


def llm_parse_event(payload: NaturalLanguageEventInput, config: dict) -> tuple[EventCreate, list[str], str]:
    prompt = f"""
你是一个事件结构化助手。请将用户的自然语言事件解析为严格 JSON。

返回 JSON 对象，字段只允许：
title, description, occurred_at, body_delta, mind_delta, event_type,
spirit_impact, vocation_impact, tags_json, source, notes

要求：
1. title 简短明确，不超过 80 字。
2. description 保留原始事件语义。
3. occurred_at 使用 ISO 8601 时间；如果文本中没有明确时间，优先使用 hint，没有 hint 再使用当前时间。
4. body_delta 和 mind_delta 必须是 -10 到 10 的整数。
5. tags_json 必须是 JSON 字符串数组，或者 null。
6. source 固定写 natural_language_llm。
7. 不要输出 markdown，不要输出解释，只输出 JSON。

当前 UTC 时间：{datetime.now(timezone.utc).isoformat()}
时间 hint：{payload.occurred_at_hint or "null"}
用户原始输入：{payload.text}
""".strip()

    body = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "You convert natural language events into strict JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(body).encode("utf-8")
    req = urlrequest.Request(
        f"{config['base_url'].rstrip('/')}/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=30) as resp:
            payload_json = json.loads(resp.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"LLM request failed: {detail}") from exc
    except urlerror.URLError as exc:
        raise HTTPException(status_code=502, detail=f"LLM connection failed: {exc}") from exc

    try:
        content = payload_json["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="LLM returned invalid event JSON.") from exc

    if isinstance(parsed.get("tags_json"), list):
        parsed["tags_json"] = json_dumps(parsed["tags_json"])

    structured_event = EventCreate(**parsed)
    warnings = ["结果来自 LLM 解析，写入数据库前仍应由用户确认。"]
    return structured_event, warnings, "llm"


def parse_natural_language_event(payload: NaturalLanguageEventInput) -> tuple[EventCreate, list[str], str]:
    config = get_openai_compatible_config()
    if config is None:
        return heuristic_parse_event(payload)
    return llm_parse_event(payload, config)


def parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=APP_TZ)
    return parsed.astimezone(timezone.utc)


def compute_week_range(week_start: str | None, week_end: str | None) -> tuple[datetime, datetime]:
    if week_start and week_end:
        start_date = date.fromisoformat(week_start)
        end_date = date.fromisoformat(week_end)
    else:
        now_local = datetime.now(APP_TZ)
        start_date = (now_local - timedelta(days=now_local.weekday())).date()
        end_date = start_date + timedelta(days=6)

    if end_date < start_date:
        raise HTTPException(status_code=400, detail="`week_end` must be on or after `week_start`.")

    start_dt = datetime.combine(start_date, time.min, APP_TZ)
    end_dt = datetime.combine(end_date, time.max, APP_TZ)
    return start_dt, end_dt


def classify_trend(total_delta: int) -> str:
    if total_delta > 0:
        return "up"
    if total_delta < 0:
        return "down"
    return "stable"


def build_weekly_review(conn: sqlite3.Connection, start_dt: datetime, end_dt: datetime, title: str | None) -> dict:
    event_rows = conn.execute(
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
        ORDER BY datetime(occurred_at) ASC, id ASC
        """
    ).fetchall()

    start_utc = start_dt.astimezone(timezone.utc)
    end_utc = end_dt.astimezone(timezone.utc)
    events = []
    for row in event_rows:
        occurred_at = parse_iso_datetime(row["occurred_at"])
        if start_utc <= occurred_at <= end_utc:
            item = dict(row)
            item["occurred_at"] = occurred_at
            events.append(item)

    key_nodes = [dict(row) for row in conn.execute(
        """
        SELECT code, name, node_type, priority, status, progress, notes
        FROM key_nodes
        ORDER BY priority DESC, id ASC
        """
    ).fetchall()]

    system_state = conn.execute(
        """
        SELECT current_phase, body_level, mind_level, notes
        FROM system_state
        WHERE id = 1
        """
    ).fetchone()

    body_total = sum(event["body_delta"] for event in events)
    mind_total = sum(event["mind_delta"] for event in events)
    body_trend = classify_trend(body_total)
    mind_trend = classify_trend(mind_total)

    active_nodes = [node for node in key_nodes if node["status"] in {"active", "pending", "paused"}]
    active_nodes = active_nodes[:5]

    event_lines = []
    for event in events:
        local_time = event["occurred_at"].astimezone(APP_TZ).strftime("%Y-%m-%d %H:%M")
        delta_text = f"body {event['body_delta']:+d}, mind {event['mind_delta']:+d}"
        desc = event["description"] or event["title"]
        event_lines.append(f"- {local_time} | {event['title']} | {delta_text} | {desc}")

    if not event_lines:
        event_lines.append("- 本周暂无事件记录。")

    key_node_lines = []
    for node in active_nodes:
        progress_pct = round(float(node["progress"] or 0) * 100, 1)
        key_node_lines.append(f"- {node['name']} | status={node['status']} | progress={progress_pct}%")
    if not key_node_lines:
        key_node_lines.append("- 当前没有可汇总的关键节点。")

    review_title = title or f"Weekly Review {start_dt.date().isoformat()} ~ {end_dt.date().isoformat()}"
    summary = (
        f"本周共记录 {len(events)} 条事件，body_delta 合计 {body_total:+d}，"
        f"mind_delta 合计 {mind_total:+d}，当前 phase={system_state['current_phase']}。"
    )
    key_node_progress_summary = "；".join(
        f"{node['name']}({round(float(node['progress'] or 0) * 100, 1)}%)" for node in active_nodes
    ) or "无关键节点摘要"

    markdown_content = "\n".join(
        [
            f"# {review_title}",
            "",
            f"- 周期：{start_dt.date().isoformat()} ~ {end_dt.date().isoformat()}",
            f"- Phase：{system_state['current_phase']}",
            f"- Body level：{system_state['body_level']}",
            f"- Mind level：{system_state['mind_level']}",
            f"- Body trend：{body_trend} ({body_total:+d})",
            f"- Mind trend：{mind_trend} ({mind_total:+d})",
            "",
            "## 事件摘要",
            *event_lines,
            "",
            "## 关键节点摘要",
            *key_node_lines,
            "",
            "## 总结",
            summary,
        ]
    )

    return {
        "week_start": start_dt.date().isoformat(),
        "week_end": end_dt.date().isoformat(),
        "title": review_title,
        "markdown_content": markdown_content,
        "summary": summary,
        "body_trend": body_trend,
        "mind_trend": mind_trend,
        "key_node_progress_summary": key_node_progress_summary,
    }


def upsert_weekly_review(conn: sqlite3.Connection, review: dict) -> dict:
    existing = conn.execute(
        "SELECT id FROM weekly_reviews WHERE week_start = ? AND week_end = ?",
        (review["week_start"], review["week_end"]),
    ).fetchone()

    fields = (
        review["title"],
        review["markdown_content"],
        review["summary"],
        review["body_trend"],
        review["mind_trend"],
        review["key_node_progress_summary"],
        review["week_start"],
        review["week_end"],
    )

    if existing:
        conn.execute(
            """
            UPDATE weekly_reviews
            SET
                title = ?,
                markdown_content = ?,
                summary = ?,
                body_trend = ?,
                mind_trend = ?,
                key_node_progress_summary = ?,
                generated_by = 'system'
            WHERE week_start = ? AND week_end = ?
            """,
            fields,
        )
    else:
        conn.execute(
            """
            INSERT INTO weekly_reviews (
                title,
                markdown_content,
                summary,
                body_trend,
                mind_trend,
                key_node_progress_summary,
                generated_by,
                week_start,
                week_end
            ) VALUES (?, ?, ?, ?, ?, ?, 'system', ?, ?)
            """,
            fields,
        )

    conn.commit()
    row = conn.execute(
        """
        SELECT
            id,
            week_start,
            week_end,
            title,
            markdown_content,
            summary,
            body_trend,
            mind_trend,
            key_node_progress_summary,
            generated_by,
            created_at
        FROM weekly_reviews
        WHERE week_start = ? AND week_end = ?
        """,
        (review["week_start"], review["week_end"]),
    ).fetchone()
    return dict(row)


def build_snapshot(conn: sqlite3.Connection, payload: SnapshotGenerateRequest | None) -> dict:
    system_state = conn.execute(
        """
        SELECT current_phase, body_level, mind_level, notes
        FROM system_state
        WHERE id = 1
        """
    ).fetchone()
    if system_state is None:
        raise HTTPException(status_code=400, detail="System state is missing. Run `python seed.py` first.")

    active_channels = [
        row["code"] for row in conn.execute(
            """
            SELECT code
            FROM channels
            WHERE is_active = 1
            ORDER BY priority DESC, id ASC
            """
        ).fetchall()
    ]
    active_key_nodes = [
        row["code"] for row in conn.execute(
            """
            SELECT code
            FROM key_nodes
            WHERE status IN ('active', 'pending', 'paused')
            ORDER BY priority DESC, id ASC
            """
        ).fetchall()
    ]
    event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    latest_review = conn.execute(
        """
        SELECT title
        FROM weekly_reviews
        ORDER BY week_start DESC, id DESC
        LIMIT 1
        """
    ).fetchone()

    summary = None
    if payload and payload.summary:
        summary = payload.summary
    else:
        review_hint = latest_review["title"] if latest_review else "暂无周复盘"
        summary = (
            f"Snapshot generated with phase={system_state['current_phase']}, "
            f"body={system_state['body_level']}, mind={system_state['mind_level']}, "
            f"events={event_count}, latest_review={review_hint}."
        )

    return {
        "snapshot_time": datetime.now(timezone.utc).isoformat(),
        "phase": system_state["current_phase"],
        "body_level": system_state["body_level"],
        "mind_level": system_state["mind_level"],
        "active_channels_json": json_dumps(active_channels),
        "active_key_nodes_json": json_dumps(active_key_nodes),
        "summary": summary,
        "notes": payload.notes if payload else None,
    }


def insert_snapshot(conn: sqlite3.Connection, snapshot: dict) -> dict:
    cur = conn.execute(
        """
        INSERT INTO snapshots (
            snapshot_time,
            phase,
            body_level,
            mind_level,
            active_channels_json,
            active_key_nodes_json,
            summary,
            notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot["snapshot_time"],
            snapshot["phase"],
            snapshot["body_level"],
            snapshot["mind_level"],
            snapshot["active_channels_json"],
            snapshot["active_key_nodes_json"],
            snapshot["summary"],
            snapshot["notes"],
        ),
    )
    conn.commit()
    row = conn.execute(
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
        WHERE id = ?
        """,
        (cur.lastrowid,),
    ).fetchone()
    return dict(row)


def get_latest_completed_run_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        """
        SELECT id
        FROM analytics_runs
        WHERE status = 'completed'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    return row["id"] if row else None


def get_run_detail(conn: sqlite3.Connection, run_id: int) -> dict | None:
    run_row = conn.execute(
        """
        SELECT
            id,
            run_type,
            window_start,
            window_end,
            status,
            rule_set_version,
            summary,
            started_at,
            completed_at
        FROM analytics_runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if run_row is None:
        return None

    energy_rules = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                event_type,
                sample_count,
                expected_body_delta,
                expected_mind_delta,
                confidence,
                evidence_notes,
                created_at
            FROM energy_rules
            WHERE analytics_run_id = ?
            ORDER BY event_type ASC
            """,
            (run_id,),
        ).fetchall()
    ]
    progress_rules = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                event_type,
                node_type,
                sample_count,
                expected_progress_delta,
                confidence,
                evidence_notes,
                created_at
            FROM progress_rules
            WHERE analytics_run_id = ?
            ORDER BY event_type ASC, node_type ASC
            """,
            (run_id,),
        ).fetchall()
    ]
    suggestions = [
        dict(row)
        for row in conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                rule_type,
                target_key,
                suggested_payload_json,
                status,
                created_at
            FROM analytics_suggestions
            WHERE analytics_run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()
    ]
    return {
        "run": dict(run_row),
        "energy_rules": energy_rules,
        "progress_rules": progress_rules,
        "suggestions": suggestions,
    }


def create_analytics_run(conn: sqlite3.Connection, run_type: str, window_start: datetime, window_end: datetime) -> int:
    cur = conn.execute(
        """
        INSERT INTO analytics_runs (
            run_type,
            window_start,
            window_end,
            status,
            rule_set_version,
            summary,
            started_at
        ) VALUES (?, ?, ?, 'running', ?, ?, ?)
        """,
        (
            run_type,
            window_start.isoformat(),
            window_end.isoformat(),
            RULE_SET_VERSION,
            "Analytics run started.",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def finalize_analytics_run(conn: sqlite3.Connection, run_id: int, status: str, summary: str) -> None:
    conn.execute(
        """
        UPDATE analytics_runs
        SET status = ?, summary = ?, completed_at = ?
        WHERE id = ?
        """,
        (status, summary, datetime.now(timezone.utc).isoformat(), run_id),
    )
    conn.commit()


def fetch_feedback_rows(conn: sqlite3.Connection, rule_type: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            s.target_key,
            f.approved_payload_json
        FROM analytics_feedback f
        JOIN analytics_suggestions s ON s.id = f.suggestion_id
        WHERE s.rule_type = ? AND f.approval_status IN ('approved', 'edited')
        """,
        (rule_type,),
    ).fetchall()


def build_energy_rule_rows(conn: sqlite3.Connection, window_start: datetime, window_end: datetime) -> list[dict]:
    aggregates: dict[str, dict] = {}
    rows = conn.execute(
        """
        SELECT event_type, occurred_at, body_delta, mind_delta
        FROM events
        ORDER BY id ASC
        """
    ).fetchall()

    for row in rows:
        occurred_at = parse_iso_datetime(row["occurred_at"])
        if not (window_start <= occurred_at <= window_end):
            continue
        event_type = row["event_type"] or "unknown"
        bucket = aggregates.setdefault(
            event_type,
            {"sample_count": 0, "body_total": 0.0, "mind_total": 0.0, "feedback_count": 0},
        )
        bucket["sample_count"] += 1
        bucket["body_total"] += row["body_delta"]
        bucket["mind_total"] += row["mind_delta"]

    for row in fetch_feedback_rows(conn, "energy"):
        try:
            payload = json.loads(row["approved_payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        event_type = row["target_key"]
        bucket = aggregates.setdefault(
            event_type,
            {"sample_count": 0, "body_total": 0.0, "mind_total": 0.0, "feedback_count": 0},
        )
        bucket["sample_count"] += 2
        bucket["body_total"] += float(payload.get("expected_body_delta", 0)) * 2
        bucket["mind_total"] += float(payload.get("expected_mind_delta", 0)) * 2
        bucket["feedback_count"] += 1

    result = []
    for event_type in sorted(aggregates):
        bucket = aggregates[event_type]
        sample_count = int(bucket["sample_count"])
        if sample_count <= 0:
            continue
        result.append(
            {
                "event_type": event_type,
                "sample_count": sample_count,
                "expected_body_delta": round(bucket["body_total"] / sample_count, 4),
                "expected_mind_delta": round(bucket["mind_total"] / sample_count, 4),
                "confidence": compute_confidence(sample_count),
                "evidence_notes": (
                    f"window_samples={sample_count - bucket['feedback_count'] * 2}, "
                    f"feedback_samples={bucket['feedback_count']}"
                ),
            }
        )
    return result


def build_progress_rule_rows(conn: sqlite3.Connection, window_start: datetime, window_end: datetime) -> list[dict]:
    aggregates: dict[str, dict] = {}
    rows = conn.execute(
        """
        SELECT
            l.source_event_id,
            l.progress_delta,
            e.event_type,
            e.occurred_at,
            k.node_type
        FROM key_node_progress_logs l
        JOIN key_nodes k ON k.id = l.key_node_id
        LEFT JOIN events e ON e.id = l.source_event_id
        ORDER BY l.id ASC
        """
    ).fetchall()

    for row in rows:
        if row["source_event_id"] is None or row["occurred_at"] is None:
            continue
        occurred_at = parse_iso_datetime(row["occurred_at"])
        if not (window_start <= occurred_at <= window_end):
            continue
        event_type = row["event_type"] or "unknown"
        node_type = row["node_type"]
        key = f"{event_type}::{node_type}"
        bucket = aggregates.setdefault(
            key,
            {
                "event_type": event_type,
                "node_type": node_type,
                "sample_count": 0,
                "progress_total": 0.0,
                "feedback_count": 0,
            },
        )
        bucket["sample_count"] += 1
        bucket["progress_total"] += float(row["progress_delta"])

    for row in fetch_feedback_rows(conn, "progress"):
        try:
            payload = json.loads(row["approved_payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        target_key = row["target_key"]
        if "::" not in target_key:
            continue
        event_type, node_type = target_key.split("::", 1)
        bucket = aggregates.setdefault(
            target_key,
            {
                "event_type": event_type,
                "node_type": node_type,
                "sample_count": 0,
                "progress_total": 0.0,
                "feedback_count": 0,
            },
        )
        bucket["sample_count"] += 2
        bucket["progress_total"] += float(payload.get("expected_progress_delta", 0)) * 2
        bucket["feedback_count"] += 1

    result = []
    for key in sorted(aggregates):
        bucket = aggregates[key]
        sample_count = int(bucket["sample_count"])
        if sample_count <= 0:
            continue
        result.append(
            {
                "event_type": bucket["event_type"],
                "node_type": bucket["node_type"],
                "sample_count": sample_count,
                "expected_progress_delta": round(bucket["progress_total"] / sample_count, 6),
                "confidence": compute_confidence(sample_count),
                "evidence_notes": (
                    f"window_samples={sample_count - bucket['feedback_count'] * 2}, "
                    f"feedback_samples={bucket['feedback_count']}"
                ),
            }
        )
    return result


def insert_energy_rules(conn: sqlite3.Connection, run_id: int, rows: list[dict]) -> list[dict]:
    stored = []
    for row in rows:
        cur = conn.execute(
            """
            INSERT INTO energy_rules (
                analytics_run_id,
                event_type,
                sample_count,
                expected_body_delta,
                expected_mind_delta,
                confidence,
                evidence_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row["event_type"],
                row["sample_count"],
                row["expected_body_delta"],
                row["expected_mind_delta"],
                row["confidence"],
                row["evidence_notes"],
            ),
        )
        inserted = conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                event_type,
                sample_count,
                expected_body_delta,
                expected_mind_delta,
                confidence,
                evidence_notes,
                created_at
            FROM energy_rules
            WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
        stored.append(dict(inserted))
    return stored


def insert_progress_rules(conn: sqlite3.Connection, run_id: int, rows: list[dict]) -> list[dict]:
    stored = []
    for row in rows:
        cur = conn.execute(
            """
            INSERT INTO progress_rules (
                analytics_run_id,
                event_type,
                node_type,
                sample_count,
                expected_progress_delta,
                confidence,
                evidence_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row["event_type"],
                row["node_type"],
                row["sample_count"],
                row["expected_progress_delta"],
                row["confidence"],
                row["evidence_notes"],
            ),
        )
        inserted = conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                event_type,
                node_type,
                sample_count,
                expected_progress_delta,
                confidence,
                evidence_notes,
                created_at
            FROM progress_rules
            WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
        stored.append(dict(inserted))
    return stored


def insert_analytics_suggestions(
    conn: sqlite3.Connection,
    run_id: int,
    energy_rows: list[dict],
    progress_rows: list[dict],
) -> list[dict]:
    stored = []
    for row in energy_rows:
        if row["sample_count"] < 3:
            continue
        payload = {
            "event_type": row["event_type"],
            "expected_body_delta": row["expected_body_delta"],
            "expected_mind_delta": row["expected_mind_delta"],
            "confidence": row["confidence"],
        }
        cur = conn.execute(
            """
            INSERT INTO analytics_suggestions (
                analytics_run_id,
                rule_type,
                target_key,
                suggested_payload_json,
                status
            ) VALUES (?, 'energy', ?, ?, 'pending')
            """,
            (run_id, row["event_type"], json_dumps(payload)),
        )
        inserted = conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                rule_type,
                target_key,
                suggested_payload_json,
                status,
                created_at
            FROM analytics_suggestions
            WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
        stored.append(dict(inserted))

    for row in progress_rows:
        if row["sample_count"] < 2:
            continue
        target_key = f"{row['event_type']}::{row['node_type']}"
        payload = {
            "event_type": row["event_type"],
            "node_type": row["node_type"],
            "expected_progress_delta": row["expected_progress_delta"],
            "confidence": row["confidence"],
        }
        cur = conn.execute(
            """
            INSERT INTO analytics_suggestions (
                analytics_run_id,
                rule_type,
                target_key,
                suggested_payload_json,
                status
            ) VALUES (?, 'progress', ?, ?, 'pending')
            """,
            (run_id, target_key, json_dumps(payload)),
        )
        inserted = conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                rule_type,
                target_key,
                suggested_payload_json,
                status,
                created_at
            FROM analytics_suggestions
            WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
        stored.append(dict(inserted))

    return stored


def run_analytics_batch(run_type: str, window_start: datetime, window_end: datetime) -> dict:
    conn = get_conn()
    run_id = create_analytics_run(conn, run_type, window_start, window_end)
    try:
        energy_rows = build_energy_rule_rows(conn, window_start, window_end)
        progress_rows = build_progress_rule_rows(conn, window_start, window_end)
        energy_rules = insert_energy_rules(conn, run_id, energy_rows)
        progress_rules = insert_progress_rules(conn, run_id, progress_rows)
        suggestions = insert_analytics_suggestions(conn, run_id, energy_rules, progress_rules)
        summary = (
            f"Generated {len(energy_rules)} energy rules, "
            f"{len(progress_rules)} progress rules, "
            f"{len(suggestions)} suggestions."
        )
        finalize_analytics_run(conn, run_id, "completed", summary)
        detail = get_run_detail(conn, run_id)
        return detail
    except Exception as exc:
        conn.rollback()
        finalize_analytics_run(conn, run_id, "failed", f"Analytics run failed: {exc}")
        raise
    finally:
        conn.close()


def get_daily_due_time(reference: datetime) -> datetime:
    return reference.replace(hour=2, minute=0, second=0, microsecond=0)


def get_weekly_due_time(reference: datetime) -> datetime:
    monday = reference - timedelta(days=reference.weekday())
    return monday.replace(hour=3, minute=0, second=0, microsecond=0)


def has_completed_scheduled_run(conn: sqlite3.Connection, run_type: str, local_reference: datetime) -> bool:
    rows = conn.execute(
        """
        SELECT started_at
        FROM analytics_runs
        WHERE run_type = ? AND status = 'completed'
        ORDER BY id DESC
        """,
        (run_type,),
    ).fetchall()

    for row in rows:
        started_at = parse_sqlite_timestamp(row["started_at"])
        if started_at is None:
            continue
        local_started = started_at.astimezone(APP_TZ)
        if run_type == "scheduled_daily" and local_started.date() == local_reference.date():
            return True
        if run_type == "scheduled_weekly":
            ref_year, ref_week, _ = local_reference.isocalendar()
            run_year, run_week, _ = local_started.isocalendar()
            if (run_year, run_week) == (ref_year, ref_week):
                return True
    return False


def compute_scheduled_window(run_type: str, now_local: datetime) -> tuple[datetime, datetime]:
    if run_type == "scheduled_daily":
        start_local = now_local - timedelta(days=7)
    else:
        start_local = now_local - timedelta(days=30)
    return start_local.astimezone(timezone.utc), now_local.astimezone(timezone.utc)


def maybe_run_scheduled_batch(run_type: str, now_local: datetime) -> bool:
    conn = get_conn()
    try:
        if has_completed_scheduled_run(conn, run_type, now_local):
            return False
    finally:
        conn.close()

    window_start, window_end = compute_scheduled_window(run_type, now_local)
    SCHEDULER_STATE["last_run_started_at"] = datetime.now(timezone.utc).isoformat()
    SCHEDULER_STATE["last_run_type"] = run_type
    run_analytics_batch(run_type, window_start, window_end)
    return True


async def analytics_scheduler_loop():
    SCHEDULER_STATE["task_running"] = True
    try:
        while True:
            now_local = datetime.now(APP_TZ)
            SCHEDULER_STATE["last_check_at"] = datetime.now(timezone.utc).isoformat()
            SCHEDULER_STATE["next_daily_local"] = get_daily_due_time(now_local).isoformat()
            SCHEDULER_STATE["next_weekly_local"] = get_weekly_due_time(now_local).isoformat()

            if now_local >= get_daily_due_time(now_local):
                await asyncio.to_thread(maybe_run_scheduled_batch, "scheduled_daily", now_local)
            if now_local.weekday() == 0 and now_local >= get_weekly_due_time(now_local):
                await asyncio.to_thread(maybe_run_scheduled_batch, "scheduled_weekly", now_local)

            await asyncio.sleep(300)
    except asyncio.CancelledError:
        raise
    finally:
        SCHEDULER_STATE["task_running"] = False


@app.on_event("startup")
async def startup_event():
    global _scheduler_task
    if SCHEDULER_ENABLED and _scheduler_task is None:
        _scheduler_task = asyncio.create_task(analytics_scheduler_loop())


@app.on_event("shutdown")
async def shutdown_event():
    global _scheduler_task
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _scheduler_task
        _scheduler_task = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "build_stage": "v1.5-analytics",
        "database_exists": DB_PATH.exists(),
        "llm_configured": get_openai_compatible_config() is not None,
        "analytics_scheduler_enabled": SCHEDULER_ENABLED,
    }


@app.get("/")
def frontend_index():
    return FileResponse(FRONTEND_DIR / "index.html")


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
        ORDER BY datetime(occurred_at) DESC, id DESC
        """
    )


@app.post("/events", status_code=201)
def create_event(event: EventCreate):
    conn = get_conn()
    try:
        return insert_event(conn, event)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail=f"Event validation failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database write failed: {exc}") from exc
    finally:
        conn.close()


@app.post("/events/parse")
def parse_event(payload: NaturalLanguageEventInput):
    structured_event, warnings, parser_backend = parse_natural_language_event(payload)
    return {
        "original_text": payload.text,
        "structured_event": structured_event.model_dump(),
        "requires_confirmation": True,
        "parser_backend": parser_backend,
        "parser_warnings": warnings,
    }


@app.post("/events/confirm", status_code=201)
def confirm_event(payload: EventConfirmRequest):
    conn = get_conn()
    try:
        inserted = insert_event(conn, payload.structured_event)
        return {
            "status": "confirmed",
            "parser_backend": payload.parser_backend,
            "original_text": payload.original_text,
            "event": inserted,
        }
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail=f"Event validation failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database write failed: {exc}") from exc
    finally:
        conn.close()


@app.get("/key-nodes")
def list_key_nodes():
    return fetch_all_dicts(
        """
        SELECT
            id,
            code,
            name,
            node_type,
            description,
            priority,
            status,
            progress,
            phase_hint,
            is_gatekeeper,
            is_sprint_node,
            linked_channel_id,
            notes,
            created_at,
            updated_at
        FROM key_nodes
        ORDER BY priority DESC, id ASC
        """
    )


@app.patch("/key-nodes/{key_node_id}")
def update_key_node(key_node_id: int, payload: KeyNodeUpdate):
    conn = get_conn()
    try:
        current = conn.execute(
            """
            SELECT
                id,
                code,
                name,
                node_type,
                description,
                priority,
                status,
                progress,
                phase_hint,
                is_gatekeeper,
                is_sprint_node,
                linked_channel_id,
                notes,
                created_at,
                updated_at
            FROM key_nodes
            WHERE id = ?
            """,
            (key_node_id,),
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="Key node not found.")

        if payload.source_event_id is not None:
            source_event = conn.execute("SELECT id FROM events WHERE id = ?", (payload.source_event_id,)).fetchone()
            if source_event is None:
                raise HTTPException(status_code=400, detail="`source_event_id` does not exist.")

        fields = []
        values = []
        progress_before = float(current["progress"] or 0)
        progress_after = progress_before
        if payload.progress is not None:
            fields.append("progress = ?")
            values.append(payload.progress)
            progress_after = payload.progress
        if payload.status is not None:
            fields.append("status = ?")
            values.append(payload.status)
        if payload.notes is not None:
            fields.append("notes = ?")
            values.append(payload.notes)

        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(key_node_id)

        conn.execute(
            f"UPDATE key_nodes SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )

        if payload.progress is not None and progress_after != progress_before:
            conn.execute(
                """
                INSERT INTO key_node_progress_logs (
                    key_node_id,
                    source_event_id,
                    progress_before,
                    progress_after,
                    progress_delta,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key_node_id,
                    payload.source_event_id,
                    progress_before,
                    progress_after,
                    progress_after - progress_before,
                    payload.reason,
                ),
            )

        conn.commit()

        row = conn.execute(
            """
            SELECT
                id,
                code,
                name,
                node_type,
                description,
                priority,
                status,
                progress,
                phase_hint,
                is_gatekeeper,
                is_sprint_node,
                linked_channel_id,
                notes,
                created_at,
                updated_at
            FROM key_nodes
            WHERE id = ?
            """,
            (key_node_id,),
        ).fetchone()
        return dict(row)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail=f"Key node update failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Database write failed: {exc}") from exc
    finally:
        conn.close()


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
        ORDER BY id DESC
        LIMIT 1
        """
    )


@app.post("/snapshot/generate", status_code=201)
def generate_snapshot(payload: SnapshotGenerateRequest | None = None):
    conn = get_conn()
    try:
        snapshot = build_snapshot(conn, payload)
        return insert_snapshot(conn, snapshot)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail=f"Snapshot generation failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Snapshot generation failed: {exc}") from exc
    finally:
        conn.close()


@app.get("/weekly-review")
def weekly_review(week_start: str | None = None, week_end: str | None = None):
    if week_start and week_end:
        conn = get_conn()
        try:
            row = conn.execute(
                """
                SELECT
                    id,
                    week_start,
                    week_end,
                    title,
                    markdown_content,
                    summary,
                    body_trend,
                    mind_trend,
                    key_node_progress_summary,
                    generated_by,
                    created_at
                FROM weekly_reviews
                WHERE week_start = ? AND week_end = ?
                """,
                (week_start, week_end),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    return fetch_one_dict(
        """
        SELECT
            id,
            week_start,
            week_end,
            title,
            markdown_content,
            summary,
            body_trend,
            mind_trend,
            key_node_progress_summary,
            generated_by,
            created_at
        FROM weekly_reviews
        ORDER BY week_start DESC, id DESC
        LIMIT 1
        """
    )


@app.post("/weekly-review/generate", status_code=201)
def generate_weekly_review(payload: WeeklyReviewGenerateRequest):
    start_dt, end_dt = compute_week_range(payload.week_start, payload.week_end)
    conn = get_conn()
    try:
        review = build_weekly_review(conn, start_dt, end_dt, payload.title)
        return upsert_weekly_review(conn, review)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Weekly review generation failed: {exc}") from exc
    finally:
        conn.close()


@app.post("/analytics/run", status_code=201)
def run_analytics(payload: AnalyticsRunRequest):
    window_start, window_end = compute_manual_window(payload.window_start, payload.window_end)
    try:
        return run_analytics_batch("manual", window_start, window_end)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Analytics run failed: {exc}") from exc


@app.get("/analytics/runs")
def list_analytics_runs():
    return fetch_all_dicts(
        """
        SELECT
            id,
            run_type,
            window_start,
            window_end,
            status,
            rule_set_version,
            summary,
            started_at,
            completed_at
        FROM analytics_runs
        ORDER BY id DESC
        """
    )


@app.get("/analytics/runs/{run_id}")
def analytics_run_detail(run_id: int):
    conn = get_conn()
    try:
        detail = get_run_detail(conn, run_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Analytics run not found.")
        return detail
    finally:
        conn.close()


@app.get("/analytics/rules/energy")
def list_energy_rules(run_id: int | None = None):
    conn = get_conn()
    try:
        target_run_id = run_id or get_latest_completed_run_id(conn)
        if target_run_id is None:
            return []
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    id,
                    analytics_run_id,
                    event_type,
                    sample_count,
                    expected_body_delta,
                    expected_mind_delta,
                    confidence,
                    evidence_notes,
                    created_at
                FROM energy_rules
                WHERE analytics_run_id = ?
                ORDER BY event_type ASC
                """,
                (target_run_id,),
            ).fetchall()
        ]
    finally:
        conn.close()


@app.get("/analytics/rules/progress")
def list_progress_rules(run_id: int | None = None):
    conn = get_conn()
    try:
        target_run_id = run_id or get_latest_completed_run_id(conn)
        if target_run_id is None:
            return []
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    id,
                    analytics_run_id,
                    event_type,
                    node_type,
                    sample_count,
                    expected_progress_delta,
                    confidence,
                    evidence_notes,
                    created_at
                FROM progress_rules
                WHERE analytics_run_id = ?
                ORDER BY event_type ASC, node_type ASC
                """,
                (target_run_id,),
            ).fetchall()
        ]
    finally:
        conn.close()


@app.get("/analytics/suggestions")
def list_analytics_suggestions(run_id: int | None = None, status: str | None = None):
    conn = get_conn()
    try:
        query = """
            SELECT
                id,
                analytics_run_id,
                rule_type,
                target_key,
                suggested_payload_json,
                status,
                created_at
            FROM analytics_suggestions
            WHERE 1 = 1
        """
        params = []
        if run_id is not None:
            query += " AND analytics_run_id = ?"
            params.append(run_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY id DESC"
        return [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]
    finally:
        conn.close()


@app.post("/analytics/suggestions/{suggestion_id}/review", status_code=201)
def review_analytics_suggestion(suggestion_id: int, payload: AnalyticsSuggestionReviewRequest):
    conn = get_conn()
    try:
        suggestion = conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                rule_type,
                target_key,
                suggested_payload_json,
                status,
                created_at
            FROM analytics_suggestions
            WHERE id = ?
            """,
            (suggestion_id,),
        ).fetchone()
        if suggestion is None:
            raise HTTPException(status_code=404, detail="Analytics suggestion not found.")

        cur = conn.execute(
            """
            INSERT INTO analytics_feedback (
                suggestion_id,
                original_payload_json,
                approved_payload_json,
                approval_status,
                reviewer_note
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                suggestion_id,
                suggestion["suggested_payload_json"],
                json_dumps(payload.approved_payload_json) if payload.approved_payload_json is not None else None,
                payload.approval_status,
                payload.reviewer_note,
            ),
        )
        conn.execute(
            "UPDATE analytics_suggestions SET status = ? WHERE id = ?",
            (payload.approval_status, suggestion_id),
        )
        conn.commit()

        feedback = conn.execute(
            """
            SELECT
                id,
                suggestion_id,
                original_payload_json,
                approved_payload_json,
                approval_status,
                reviewer_note,
                created_at
            FROM analytics_feedback
            WHERE id = ?
            """,
            (cur.lastrowid,),
        ).fetchone()
        updated_suggestion = conn.execute(
            """
            SELECT
                id,
                analytics_run_id,
                rule_type,
                target_key,
                suggested_payload_json,
                status,
                created_at
            FROM analytics_suggestions
            WHERE id = ?
            """,
            (suggestion_id,),
        ).fetchone()
        return {
            "suggestion": dict(updated_suggestion),
            "feedback": dict(feedback),
        }
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=400, detail=f"Suggestion review failed: {exc}") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Suggestion review failed: {exc}") from exc
    finally:
        conn.close()


@app.get("/analytics/insights/latest")
def get_latest_analytics_insights():
    conn = get_conn()
    try:
        run_id = get_latest_completed_run_id(conn)
        if run_id is None:
            return {
                "run": None,
                "energy_rules": [],
                "progress_rules": [],
                "pending_suggestions": [],
            }
        detail = get_run_detail(conn, run_id)
        pending = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    id,
                    analytics_run_id,
                    rule_type,
                    target_key,
                    suggested_payload_json,
                    status,
                    created_at
                FROM analytics_suggestions
                WHERE analytics_run_id = ? AND status = 'pending'
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        ]
        return {
            "run": detail["run"],
            "energy_rules": detail["energy_rules"],
            "progress_rules": detail["progress_rules"],
            "pending_suggestions": pending,
        }
    finally:
        conn.close()


@app.get("/analytics/scheduler/status")
def analytics_scheduler_status():
    return dict(SCHEDULER_STATE)
