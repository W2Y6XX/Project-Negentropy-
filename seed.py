from pathlib import Path
import json
import sqlite3


ROOT_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "negentropy.db"
SCHEMA_PATH = ROOT_DIR / "database" / "schema.sql"
INIT_PATH = ROOT_DIR / "seed" / "init_self_model.json"


def ensure_required_files() -> None:
    missing = [str(path) for path in (SCHEMA_PATH, INIT_PATH) if not path.exists()]
    if missing:
        joined = ", ".join(missing)
        raise FileNotFoundError(f"Missing required foundation files: {joined}")


def recreate_database() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Removed existing database: {DB_PATH.name}")

    conn = sqlite3.connect(DB_PATH)
    try:
        with SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
            conn.executescript(schema_file.read())
        conn.commit()
    finally:
        conn.close()


def load_seed_data() -> dict:
    with INIT_PATH.open("r", encoding="utf-8") as init_file:
        return json.load(init_file)


def insert_rows(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return

    columns = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    values = [tuple(row[column] for column in columns) for row in rows]
    conn.executemany(sql, values)


def fetch_id_map(conn: sqlite3.Connection, table: str) -> dict[str, int]:
    rows = conn.execute(f"SELECT id, code FROM {table}").fetchall()
    return {row[1]: row[0] for row in rows}


def seed_system_state(conn: sqlite3.Connection, data: dict) -> None:
    row = {
        "id": 1,
        "current_phase": data["current_phase"],
        "body_level": data["body_level"],
        "mind_level": data["mind_level"],
        "body_range_min": data.get("body_range_min"),
        "body_range_max": data.get("body_range_max"),
        "mind_range_min": data.get("mind_range_min"),
        "mind_range_max": data.get("mind_range_max"),
        "active_channel_codes_json": json.dumps(data.get("active_channel_codes", []), ensure_ascii=False),
        "active_key_node_codes_json": json.dumps(data.get("active_key_node_codes", []), ensure_ascii=False),
        "notes": data.get("notes"),
    }
    insert_rows(conn, "system_state", [row])


def seed_channels(conn: sqlite3.Connection, rows: list[dict]) -> None:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "code": row["code"],
                "name": row["name"],
                "description": row.get("description"),
                "priority": row["priority"],
                "is_active": 1 if row.get("is_active", False) else 0,
                "is_constraint": 1 if row.get("is_constraint", False) else 0,
                "constraint_level": row.get("constraint_level"),
                "direction_hint": row.get("direction_hint"),
                "notes": row.get("notes"),
            }
        )
    insert_rows(conn, "channels", normalized)


def seed_traits(conn: sqlite3.Connection, rows: list[dict]) -> None:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "code": row["code"],
                "name": row["name"],
                "description": row["description"],
                "category": row.get("category"),
                "priority": row["priority"],
                "confidence": row["confidence"],
                "stability": row["stability"],
                "is_manual": 1 if row.get("is_manual", False) else 0,
                "source": row.get("source"),
                "conflict_notes": row.get("conflict_notes"),
                "notes": row.get("notes"),
            }
        )
    insert_rows(conn, "traits", normalized)


def seed_skills(conn: sqlite3.Connection, rows: list[dict]) -> None:
    channel_ids = fetch_id_map(conn, "channels")
    pending = list(rows)
    inserted_codes: set[str] = set()

    while pending:
        progressed = False
        next_pending = []
        for row in pending:
            parent_code = row.get("parent_code")
            if parent_code and parent_code not in inserted_codes:
                next_pending.append(row)
                continue

            parent_id = None
            if parent_code:
                parent_id = conn.execute("SELECT id FROM skills WHERE code = ?", (parent_code,)).fetchone()[0]

            insert_rows(
                conn,
                "skills",
                [
                    {
                        "code": row["code"],
                        "name": row["name"],
                        "description": row.get("description"),
                        "parent_id": parent_id,
                        "domain": row.get("domain"),
                        "level": row.get("level"),
                        "related_dimension": row.get("related_dimension"),
                        "related_channel_id": channel_ids.get(row.get("related_channel_code")),
                        "target_definition": row.get("target_definition"),
                        "status": row.get("status", "seeded"),
                        "notes": row.get("notes"),
                    }
                ],
            )
            inserted_codes.add(row["code"])
            progressed = True

        if not progressed and next_pending:
            unresolved = ", ".join(row["code"] for row in next_pending)
            raise ValueError(f"Unable to resolve parent_code for skills: {unresolved}")
        pending = next_pending


def seed_key_nodes(conn: sqlite3.Connection, rows: list[dict]) -> None:
    channel_ids = fetch_id_map(conn, "channels")
    normalized = []
    for row in rows:
        normalized.append(
            {
                "code": row["code"],
                "name": row["name"],
                "node_type": row["node_type"],
                "description": row["description"],
                "priority": row["priority"],
                "status": row.get("status", "pending"),
                "progress": row.get("progress", 0),
                "phase_hint": row.get("phase_hint"),
                "is_gatekeeper": 1 if row.get("is_gatekeeper", False) else 0,
                "is_sprint_node": 1 if row.get("is_sprint_node", False) else 0,
                "linked_channel_id": channel_ids.get(row.get("linked_channel_code")),
                "notes": row.get("notes"),
            }
        )
    insert_rows(conn, "key_nodes", normalized)


def seed_goals(conn: sqlite3.Connection, rows: list[dict]) -> None:
    key_node_ids = fetch_id_map(conn, "key_nodes")
    skill_ids = fetch_id_map(conn, "skills")
    normalized = []
    for row in rows:
        normalized.append(
            {
                "code": row["code"],
                "name": row["name"],
                "description": row.get("description"),
                "goal_type": row.get("goal_type"),
                "status": row.get("status", "pending"),
                "priority": row.get("priority"),
                "progress": row.get("progress", 0),
                "linked_key_node_id": key_node_ids.get(row.get("linked_key_node_code")),
                "linked_skill_id": skill_ids.get(row.get("linked_skill_code")),
                "due_date": row.get("due_date"),
                "notes": row.get("notes"),
            }
        )
    insert_rows(conn, "goals", normalized)


def seed_energy_pools(conn: sqlite3.Connection, rows: list[dict]) -> None:
    insert_rows(conn, "energy_pools", rows)


def seed_snapshots(conn: sqlite3.Connection, rows: list[dict]) -> None:
    normalized = []
    for row in rows:
        normalized.append(
            {
                "snapshot_time": row["snapshot_time"],
                "phase": row["phase"],
                "body_level": row["body_level"],
                "mind_level": row["mind_level"],
                "active_channels_json": json.dumps(row.get("active_channel_codes", []), ensure_ascii=False),
                "active_key_nodes_json": json.dumps(row.get("active_key_node_codes", []), ensure_ascii=False),
                "summary": row.get("summary"),
                "notes": row.get("notes"),
            }
        )
    insert_rows(conn, "snapshots", normalized)


def seed_database() -> None:
    data = load_seed_data()
    conn = sqlite3.connect(DB_PATH)
    try:
        seed_system_state(conn, data["system_state"])
        seed_channels(conn, data.get("channels", []))
        seed_traits(conn, data.get("traits", []))
        seed_skills(conn, data.get("skills", []))
        seed_key_nodes(conn, data.get("key_nodes", []))
        seed_goals(conn, data.get("goals", []))
        seed_energy_pools(conn, data.get("energy_pools", []))
        seed_snapshots(conn, data.get("snapshots", []))
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    ensure_required_files()
    recreate_database()
    seed_database()
    print("Database schema initialized successfully.")
    print("D0 seed data imported successfully.")
    print(f"Schema source: {SCHEMA_PATH}")
    print(f"Seed source: {INIT_PATH}")


if __name__ == "__main__":
    main()
