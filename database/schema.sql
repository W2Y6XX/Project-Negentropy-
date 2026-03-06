PRAGMA foreign_keys = ON;

-- =========================================================
-- Negentropy Engine D0 / MVP schema
-- Target DB: SQLite
-- Version: 0.2.0
--
-- Design principles:
-- 1) Keep the MVP local, explicit, and debuggable.
-- 2) Keep schema extensible, but avoid premature complexity.
-- 3) Preserve frozen business semantics from the D0 package.
-- 4) Support one event linking to multiple channels / key nodes / skills.
-- =========================================================

BEGIN;

-- -----------------------------
-- 0. Current system state
-- -----------------------------
CREATE TABLE IF NOT EXISTS system_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_phase TEXT NOT NULL CHECK (
        current_phase IN (
            'reconstruction',
            'stabilizing',
            'exploration',
            'expansion',
            'overload',
            'recovery'
        )
    ),
    body_level INTEGER NOT NULL CHECK (body_level BETWEEN 0 AND 5),
    mind_level INTEGER NOT NULL CHECK (mind_level BETWEEN 0 AND 5),
    body_range_min REAL CHECK (body_range_min BETWEEN 0 AND 5),
    body_range_max REAL CHECK (body_range_max BETWEEN 0 AND 5),
    mind_range_min REAL CHECK (mind_range_min BETWEEN 0 AND 5),
    mind_range_max REAL CHECK (mind_range_max BETWEEN 0 AND 5),
    active_channel_codes_json TEXT,
    active_key_node_codes_json TEXT,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (body_range_min IS NULL OR body_range_max IS NULL OR body_range_min <= body_range_max),
    CHECK (mind_range_min IS NULL OR mind_range_max IS NULL OR mind_range_min <= mind_range_max)
);

-- -----------------------------
-- 1. Channels
-- -----------------------------
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_constraint INTEGER NOT NULL DEFAULT 0 CHECK (is_constraint IN (0, 1)),
    constraint_level INTEGER CHECK (constraint_level BETWEEN 0 AND 5),
    direction_hint TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_channels_priority
    ON channels(priority DESC, is_active DESC);

-- -----------------------------
-- 2. Traits
-- -----------------------------
CREATE TABLE IF NOT EXISTS traits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT,
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    stability TEXT NOT NULL CHECK (stability IN ('fixed', 'evolving')),
    is_manual INTEGER NOT NULL DEFAULT 1 CHECK (is_manual IN (0, 1)),
    source TEXT,
    conflict_notes TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_traits_priority
    ON traits(priority DESC, confidence DESC);

-- -----------------------------
-- 3. Skills
-- -----------------------------
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES skills(id) ON DELETE SET NULL,
    domain TEXT,
    level INTEGER CHECK (level BETWEEN 0 AND 5),
    related_dimension TEXT CHECK (related_dimension IN ('body', 'mind', 'mixed')),
    related_channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
    target_definition TEXT,
    status TEXT DEFAULT 'seeded' CHECK (status IN ('seeded', 'active', 'paused', 'archived')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_skills_parent_id
    ON skills(parent_id);

CREATE INDEX IF NOT EXISTS idx_skills_related_channel_id
    ON skills(related_channel_id);

-- -----------------------------
-- 4. Key nodes
-- -----------------------------
CREATE TABLE IF NOT EXISTS key_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (node_type IN ('spirit', 'vocation')),
    description TEXT NOT NULL,
    priority INTEGER NOT NULL CHECK (priority BETWEEN 1 AND 5),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'active', 'paused', 'done', 'archived')
    ),
    progress REAL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    phase_hint TEXT CHECK (
        phase_hint IS NULL OR phase_hint IN (
            'reconstruction',
            'stabilizing',
            'exploration',
            'expansion',
            'overload',
            'recovery'
        )
    ),
    is_gatekeeper INTEGER NOT NULL DEFAULT 0 CHECK (is_gatekeeper IN (0, 1)),
    is_sprint_node INTEGER NOT NULL DEFAULT 0 CHECK (is_sprint_node IN (0, 1)),
    linked_channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_key_nodes_type_priority
    ON key_nodes(node_type, priority DESC, status);

-- -----------------------------
-- 5. Goals
-- -----------------------------
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    goal_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'active', 'paused', 'done', 'archived')
    ),
    priority INTEGER CHECK (priority BETWEEN 1 AND 5),
    progress REAL DEFAULT 0 CHECK (progress BETWEEN 0 AND 1),
    linked_key_node_id INTEGER REFERENCES key_nodes(id) ON DELETE SET NULL,
    linked_skill_id INTEGER REFERENCES skills(id) ON DELETE SET NULL,
    due_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_goals_status_priority
    ON goals(status, priority DESC);

-- -----------------------------
-- 6. Events
-- -----------------------------
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    event_type TEXT,
    description TEXT,
    occurred_at TEXT NOT NULL,
    body_delta INTEGER NOT NULL DEFAULT 0 CHECK (body_delta BETWEEN -10 AND 10),
    mind_delta INTEGER NOT NULL DEFAULT 0 CHECK (mind_delta BETWEEN -10 AND 10),
    spirit_impact TEXT,
    vocation_impact TEXT,
    tags_json TEXT,
    source TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_occurred_at
    ON events(occurred_at DESC);

-- Support one event linking to multiple channels / key nodes / skills.
CREATE TABLE IF NOT EXISTS event_channels (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    relation_type TEXT DEFAULT 'secondary' CHECK (
        relation_type IN ('primary', 'secondary', 'constraint', 'context')
    ),
    weight REAL DEFAULT 1 CHECK (weight >= 0),
    notes TEXT,
    PRIMARY KEY (event_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_event_channels_channel_id
    ON event_channels(channel_id);

CREATE TABLE IF NOT EXISTS event_key_nodes (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    key_node_id INTEGER NOT NULL REFERENCES key_nodes(id) ON DELETE CASCADE,
    impact_type TEXT DEFAULT 'signal' CHECK (
        impact_type IN ('progress', 'blocker', 'signal', 'context')
    ),
    progress_delta REAL DEFAULT 0 CHECK (progress_delta BETWEEN -1 AND 1),
    notes TEXT,
    PRIMARY KEY (event_id, key_node_id)
);

CREATE INDEX IF NOT EXISTS idx_event_key_nodes_key_node_id
    ON event_key_nodes(key_node_id);

CREATE TABLE IF NOT EXISTS event_skills (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    effect_type TEXT DEFAULT 'evidence' CHECK (
        effect_type IN ('practice', 'assessment', 'evidence', 'context')
    ),
    level_delta INTEGER DEFAULT 0 CHECK (level_delta BETWEEN -5 AND 5),
    notes TEXT,
    PRIMARY KEY (event_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_event_skills_skill_id
    ON event_skills(skill_id);

-- -----------------------------
-- 7. Weekly reviews
-- -----------------------------
CREATE TABLE IF NOT EXISTS weekly_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start TEXT NOT NULL,
    week_end TEXT NOT NULL,
    title TEXT,
    markdown_content TEXT NOT NULL,
    summary TEXT,
    body_trend TEXT,
    mind_trend TEXT,
    key_node_progress_summary TEXT,
    generated_by TEXT DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (week_start, week_end)
);

-- -----------------------------
-- 8. Energy pools
-- -----------------------------
CREATE TABLE IF NOT EXISTS energy_pools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_type TEXT NOT NULL CHECK (pool_type IN ('body', 'mind')),
    level INTEGER NOT NULL CHECK (level BETWEEN 0 AND 5),
    estimated_range_min REAL CHECK (estimated_range_min BETWEEN 0 AND 5),
    estimated_range_max REAL CHECK (estimated_range_max BETWEEN 0 AND 5),
    assessment_basis TEXT,
    measured_at TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        estimated_range_min IS NULL OR estimated_range_max IS NULL OR estimated_range_min <= estimated_range_max
    )
);

CREATE INDEX IF NOT EXISTS idx_energy_pools_type_measured_at
    ON energy_pools(pool_type, measured_at DESC);

-- -----------------------------
-- 9. Snapshots
-- -----------------------------
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TEXT NOT NULL,
    phase TEXT NOT NULL CHECK (
        phase IN (
            'reconstruction',
            'stabilizing',
            'exploration',
            'expansion',
            'overload',
            'recovery'
        )
    ),
    body_level INTEGER NOT NULL CHECK (body_level BETWEEN 0 AND 5),
    mind_level INTEGER NOT NULL CHECK (mind_level BETWEEN 0 AND 5),
    active_channels_json TEXT,
    active_key_nodes_json TEXT,
    summary TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshots_snapshot_time
    ON snapshots(snapshot_time DESC);

COMMIT;
