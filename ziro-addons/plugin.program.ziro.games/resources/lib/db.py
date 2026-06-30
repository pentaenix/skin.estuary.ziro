from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .paths import db_path
from .platforms import all_platform_rows

SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_info (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS platforms (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  short_name TEXT NOT NULL,
  manufacturer TEXT,
  sort_order INTEGER NOT NULL DEFAULT 999
);
CREATE TABLE IF NOT EXISTS genres (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS emulator_profiles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  platform_id TEXT,
  executable_path TEXT NOT NULL,
  arguments_template TEXT NOT NULL,
  working_directory TEXT,
  process_name TEXT,
  exit_hotkey TEXT,
  fullscreen INTEGER NOT NULL DEFAULT 1,
  return_focus_to_kodi INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  platform_id TEXT NOT NULL,
  folder_path TEXT NOT NULL,
  recursive INTEGER NOT NULL DEFAULT 1,
  file_extensions TEXT NOT NULL,
  emulator_profile_id TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  label TEXT,
  date_added TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(platform_id, folder_path)
);
CREATE TABLE IF NOT EXISTS games (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  sort_title TEXT NOT NULL,
  platform_id TEXT NOT NULL,
  release_year INTEGER,
  developer TEXT,
  publisher TEXT,
  description TEXT,
  rom_path TEXT NOT NULL UNIQUE,
  emulator_profile_id TEXT NOT NULL,
  source_id INTEGER,
  cover_path TEXT,
  fanart_path TEXT,
  logo_path TEXT,
  screenshot_path TEXT,
  favorite INTEGER NOT NULL DEFAULT 0,
  hidden INTEGER NOT NULL DEFAULT 0,
  date_added TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_played TEXT,
  play_count INTEGER NOT NULL DEFAULT 0,
  total_play_time INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_genres (
  game_id INTEGER NOT NULL,
  genre_id TEXT NOT NULL,
  PRIMARY KEY (game_id, genre_id)
);
"""

MIGRATIONS = [
    "ALTER TABLE sources ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE sources ADD COLUMN label TEXT",
    "ALTER TABLE sources ADD COLUMN date_added TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE games ADD COLUMN source_id INTEGER",
    "ALTER TABLE games ADD COLUMN sgdb_game_id INTEGER",
    "ALTER TABLE games ADD COLUMN manual_metadata_locked INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE games ADD COLUMN metadata_updated_at TEXT",
    "ALTER TABLE games ADD COLUMN ss_game_id INTEGER",
]

DEFAULT_PLATFORMS = all_platform_rows()

DEFAULT_GENRES = [
    ("rpg", "RPG"),
    ("platformer", "Platformer"),
    ("adventure", "Adventure"),
    ("racing", "Racing"),
    ("fighting", "Fighting"),
    ("coop", "Co-op"),
]


class GameDatabase:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def ensure(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            for sql in MIGRATIONS:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    # Column already exists on updated databases.
                    pass
            conn.execute("INSERT OR REPLACE INTO schema_info(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
            conn.executemany(
                "INSERT OR IGNORE INTO platforms(id, name, short_name, manufacturer, sort_order) VALUES(?,?,?,?,?)",
                DEFAULT_PLATFORMS,
            )
            conn.executemany("INSERT OR IGNORE INTO genres(id, name) VALUES(?,?)", DEFAULT_GENRES)

    def rows(self, query: str, args: Iterable = ()) -> list[dict]:
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, tuple(args)).fetchall()]

    def one(self, query: str, args: Iterable = ()) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(query, tuple(args)).fetchone()
            return dict(row) if row else None

    def execute(self, query: str, args: Iterable = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(query, tuple(args))
            return cur.rowcount

    def upsert_game(self, game: dict) -> None:
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM games WHERE rom_path=?", (game["rom_path"],)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE games SET
                      title=COALESCE(NULLIF(?, ''), title),
                      sort_title=COALESCE(NULLIF(?, ''), sort_title),
                      platform_id=?,
                      emulator_profile_id=?,
                      source_id=?,
                      hidden=0
                    WHERE rom_path=?
                    """,
                    (
                        game["title"], game["sort_title"], game["platform_id"],
                        game["emulator_profile_id"], game.get("source_id"), game["rom_path"],
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO games(title, sort_title, platform_id, rom_path, emulator_profile_id, source_id, description)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        game["title"], game["sort_title"], game["platform_id"], game["rom_path"],
                        game["emulator_profile_id"], game.get("source_id"), game.get("description", ""),
                    ),
                )

    def ensure_emulator_profile(self, profile: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO emulator_profiles(
                  id, name, platform_id, executable_path, arguments_template,
                  working_directory, process_name, exit_hotkey, fullscreen, return_focus_to_kodi
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    profile["id"], profile["name"], profile.get("platform_id"), profile["executable_path"],
                    profile["arguments_template"], profile.get("working_directory"), profile.get("process_name"),
                    profile.get("exit_hotkey"), int(profile.get("fullscreen", True)), int(profile.get("return_focus_to_kodi", True)),
                ),
            )

    def ensure_source(self, source: dict) -> int | None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sources(platform_id, folder_path, recursive, file_extensions, emulator_profile_id, enabled, label)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    source["platform_id"], source["folder_path"], int(source.get("recursive", True)),
                    ",".join(source["file_extensions"]), source["emulator_profile_id"], int(source.get("enabled", True)),
                    source.get("label"),
                ),
            )
            row = conn.execute(
                "SELECT id FROM sources WHERE platform_id=? AND folder_path=?",
                (source["platform_id"], source["folder_path"]),
            ).fetchone()
            return int(row["id"]) if row else None

    def list_sources(self, enabled_only: bool = False) -> list[dict]:
        where = "WHERE s.enabled=1" if enabled_only else ""
        return self.rows(
            f"""
            SELECT s.*, p.name AS platform_name, p.short_name AS platform_short_name
            FROM sources s
            LEFT JOIN platforms p ON p.id=s.platform_id
            {where}
            ORDER BY p.sort_order, s.folder_path
            """
        )

    def delete_source(self, source_id: int, *, purge_games: bool = False) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM sources WHERE id=?", (source_id,))
            if purge_games:
                conn.execute("UPDATE games SET hidden=1 WHERE source_id=?", (source_id,))
            else:
                conn.execute("UPDATE games SET source_id=NULL WHERE source_id=?", (source_id,))

    def clear_games_for_source(self, source_id: int) -> None:
        self.execute("UPDATE games SET hidden=1 WHERE source_id=?", (source_id,))

    def get_game(self, game_id: int) -> dict | None:
        return self.one("SELECT * FROM games WHERE id=? AND hidden=0", (game_id,))

    def list_games_without_artwork(self, limit: int | None = None) -> list[dict]:
        query = """
            SELECT * FROM games
            WHERE hidden=0
              AND manual_metadata_locked=0
              AND (cover_path IS NULL OR cover_path='')
            ORDER BY sort_title
        """
        if limit:
            query += f" LIMIT {int(limit)}"
        return self.rows(query)

    def update_game_artwork(self, game_id: int, fields: dict) -> None:
        allowed = {
            "cover_path", "fanart_path", "logo_path", "screenshot_path",
            "sgdb_game_id", "ss_game_id", "metadata_updated_at", "description",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return
        columns = ", ".join(f"{column}=?" for column in updates)
        values = list(updates.values()) + [game_id]
        self.execute(f"UPDATE games SET {columns} WHERE id=?", values)
