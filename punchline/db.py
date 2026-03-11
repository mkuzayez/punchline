"""SQLite database for storing posts, scripts, and pipeline state."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "punchline.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            subreddit TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            url TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            upvote_ratio REAL DEFAULT 0,
            num_comments INTEGER DEFAULT 0,
            created_utc REAL DEFAULT 0,
            fetched_at TEXT DEFAULT (datetime('now')),
            punchline_score REAL DEFAULT 0,
            status TEXT DEFAULT 'new'
        );

        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT NOT NULL REFERENCES posts(id),
            lang TEXT NOT NULL DEFAULT 'en',
            hook TEXT NOT NULL,
            body TEXT NOT NULL,
            cta TEXT NOT NULL DEFAULT '',
            mood TEXT NOT NULL DEFAULT 'neutral',
            full_text TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS voices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id INTEGER NOT NULL REFERENCES scripts(id),
            audio_path TEXT NOT NULL,
            duration_sec REAL NOT NULL,
            voice_name TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS renders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id TEXT NOT NULL REFERENCES posts(id),
            script_id INTEGER NOT NULL REFERENCES scripts(id),
            voice_id INTEGER NOT NULL REFERENCES voices(id),
            subs_path TEXT,
            video_path TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()
