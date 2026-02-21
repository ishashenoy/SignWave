"""
FlowState Rehab — Database Module
==================================
SQLite storage for sessions, per-note joint deviation data, and ideal poses.
"""

import sqlite3
import json
import os
import time
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flowstate_rehab.db")

# 21 MediaPipe hand landmark names (index matches landmark ID)
LANDMARK_NAMES = [
    "WRIST",
    "THUMB_CMC", "THUMB_MCP", "THUMB_IP", "THUMB_TIP",
    "INDEX_FINGER_MCP", "INDEX_FINGER_PIP", "INDEX_FINGER_DIP", "INDEX_FINGER_TIP",
    "MIDDLE_FINGER_MCP", "MIDDLE_FINGER_PIP", "MIDDLE_FINGER_DIP", "MIDDLE_FINGER_TIP",
    "RING_FINGER_MCP", "RING_FINGER_PIP", "RING_FINGER_DIP", "RING_FINGER_TIP",
    "PINKY_MCP", "PINKY_PIP", "PINKY_DIP", "PINKY_TIP",
]


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
            -- Sessions: one row per song play-through
            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id     TEXT    NOT NULL,
                song_title  TEXT    NOT NULL,
                mode        TEXT    NOT NULL DEFAULT 'song',
                started_at  REAL    NOT NULL,
                ended_at    REAL,
                score       INTEGER DEFAULT 0,
                max_combo   INTEGER DEFAULT 0,
                total_notes INTEGER DEFAULT 0,
                hits        INTEGER DEFAULT 0,
                misses      INTEGER DEFAULT 0,
                perfects    INTEGER DEFAULT 0,
                goods       INTEGER DEFAULT 0,
                oks         INTEGER DEFAULT 0,
                accuracy    REAL    DEFAULT 0.0,
                -- JSON blob: average deviation per joint (21 floats)
                avg_joint_deviations TEXT
            );

            -- Per-note attempt data: one row per note in a session
            CREATE TABLE IF NOT EXISTS session_notes (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id    INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                note_index    INTEGER NOT NULL,
                pose_expected INTEGER NOT NULL,
                pose_detected INTEGER,
                accuracy_label TEXT,
                hit           INTEGER NOT NULL DEFAULT 0,
                -- JSON: 21-element list of {x, y} for detected landmarks
                landmarks_detected TEXT,
                -- JSON: 21-element list of {x, y} for ideal landmarks
                landmarks_ideal    TEXT,
                -- JSON: 21-element list of floats (Euclidean deviation per joint)
                joint_deviations   TEXT,
                timestamp     REAL NOT NULL
            );

            -- Ideal poses: one row per pose (5 total). Captured from user or preset.
            CREATE TABLE IF NOT EXISTS ideal_poses (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                pose_idx  INTEGER NOT NULL UNIQUE,
                pose_name TEXT    NOT NULL,
                -- JSON: 21-element list of {x, y} (wrist-normalized)
                landmarks TEXT    NOT NULL,
                captured_at REAL  NOT NULL
            );

            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_session_notes_session
                ON session_notes(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_song
                ON sessions(song_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_started
                ON sessions(started_at);
        """)


# ──────────────────────────────────────────────────
#  Session CRUD
# ──────────────────────────────────────────────────

def create_session(song_id, song_title, mode="song"):
    """Start a new session. Returns the session ID."""
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (song_id, song_title, mode, started_at) VALUES (?, ?, ?, ?)",
            (song_id, song_title, mode, time.time()),
        )
        return cur.lastrowid


def end_session(session_id, score, max_combo, total_notes, hits, misses,
                perfects, goods, oks, accuracy, avg_joint_deviations=None):
    """Finalize a session with summary stats."""
    devs_json = json.dumps(avg_joint_deviations) if avg_joint_deviations else None
    with get_db() as conn:
        conn.execute("""
            UPDATE sessions SET
                ended_at = ?, score = ?, max_combo = ?, total_notes = ?,
                hits = ?, misses = ?, perfects = ?, goods = ?, oks = ?,
                accuracy = ?, avg_joint_deviations = ?
            WHERE id = ?
        """, (time.time(), score, max_combo, total_notes, hits, misses,
              perfects, goods, oks, accuracy, devs_json, session_id))


def get_session(session_id):
    """Fetch a single session by ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None


def get_all_sessions(limit=50, song_id=None):
    """Fetch recent sessions, optionally filtered by song."""
    with get_db() as conn:
        if song_id:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE song_id = ? ORDER BY started_at DESC LIMIT ?",
                (song_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────────
#  Per-note data
# ──────────────────────────────────────────────────

def add_note_data(session_id, note_index, pose_expected, pose_detected,
                  accuracy_label, hit, landmarks_detected, landmarks_ideal,
                  joint_deviations, timestamp):
    """Record per-note joint tracking data."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO session_notes
                (session_id, note_index, pose_expected, pose_detected,
                 accuracy_label, hit, landmarks_detected, landmarks_ideal,
                 joint_deviations, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, note_index, pose_expected, pose_detected,
            accuracy_label, int(hit),
            json.dumps(landmarks_detected) if landmarks_detected else None,
            json.dumps(landmarks_ideal) if landmarks_ideal else None,
            json.dumps(joint_deviations) if joint_deviations else None,
            timestamp,
        ))


def get_session_notes(session_id):
    """Get all note data for a session."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM session_notes WHERE session_id = ? ORDER BY note_index",
            (session_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Parse JSON fields
            for field in ("landmarks_detected", "landmarks_ideal", "joint_deviations"):
                if d[field]:
                    d[field] = json.loads(d[field])
            result.append(d)
        return result


def get_joint_averages(session_id):
    """Compute per-joint average deviation for a session."""
    notes = get_session_notes(session_id)
    if not notes:
        return None

    totals = [0.0] * 21
    counts = [0] * 21

    for note in notes:
        devs = note.get("joint_deviations")
        if devs and len(devs) == 21:
            for i, d in enumerate(devs):
                if d is not None:
                    totals[i] += d
                    counts[i] += 1

    averages = []
    for i in range(21):
        averages.append(round(totals[i] / counts[i], 4) if counts[i] > 0 else None)
    return averages


# ──────────────────────────────────────────────────
#  Ideal Poses
# ──────────────────────────────────────────────────

def save_ideal_pose(pose_idx, pose_name, landmarks):
    """Save or update the ideal landmark positions for a pose.
    `landmarks` is a list of 21 {x, y} dicts (wrist-normalized)."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO ideal_poses (pose_idx, pose_name, landmarks, captured_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(pose_idx) DO UPDATE SET
                landmarks = excluded.landmarks,
                captured_at = excluded.captured_at
        """, (pose_idx, pose_name, json.dumps(landmarks), time.time()))


def get_ideal_pose(pose_idx):
    """Get the ideal landmark positions for a pose."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM ideal_poses WHERE pose_idx = ?", (pose_idx,)
        ).fetchone()
        if row:
            d = dict(row)
            d["landmarks"] = json.loads(d["landmarks"])
            return d
        return None


def get_all_ideal_poses():
    """Get all stored ideal poses."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM ideal_poses ORDER BY pose_idx").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["landmarks"] = json.loads(d["landmarks"])
            result.append(d)
        return result


def has_ideal_poses():
    """Check if all 5 ideal poses have been captured."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM ideal_poses").fetchone()[0]
        return count >= 5


# ──────────────────────────────────────────────────
#  Analytics Helpers
# ──────────────────────────────────────────────────

def get_session_comparison(session_id_a, session_id_b):
    """Compare joint averages between two sessions."""
    avgs_a = get_joint_averages(session_id_a)
    avgs_b = get_joint_averages(session_id_b)
    if not avgs_a or not avgs_b:
        return None

    comparison = []
    for i in range(21):
        a = avgs_a[i] if avgs_a[i] is not None else 0
        b = avgs_b[i] if avgs_b[i] is not None else 0
        comparison.append({
            "joint": LANDMARK_NAMES[i],
            "index": i,
            "session_a": round(a, 4),
            "session_b": round(b, 4),
            "improvement": round(a - b, 4),  # positive = improved (lower deviation)
        })
    return comparison


def get_progress_over_time(song_id=None, limit=20):
    """Get accuracy trend over recent sessions."""
    sessions = get_all_sessions(limit=limit, song_id=song_id)
    return [{
        "id": s["id"],
        "song_title": s["song_title"],
        "accuracy": s["accuracy"],
        "score": s["score"],
        "started_at": s["started_at"],
    } for s in reversed(sessions)]  # chronological order


# Initialize DB on import
init_db()
