"""Database layer — connection caching, schema, CRUD"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any

log = logging.getLogger("MafiaBot.DB")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mafia.db")
_conn_cache: Dict[str, sqlite3.Connection] = {}


def get_db() -> sqlite3.Connection:
    pid = str(os.getpid())
    if pid not in _conn_cache:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _conn_cache[pid] = conn
    return _conn_cache[pid]


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT DEFAULT '',
            username TEXT DEFAULT '',
            olmos INTEGER DEFAULT 0,
            dollars INTEGER DEFAULT 0,
            evro INTEGER DEFAULT 0,
            games INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            bought_role TEXT DEFAULT NULL,
            hero INTEGER DEFAULT 0,
            hero_attack INTEGER DEFAULT 0,
            hero_defense INTEGER DEFAULT 0,
            last_daily TEXT DEFAULT NULL
        )
    """)
    for col in ["hero_attack", "hero_defense", "last_daily"]:
        try:
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {col} DEFAULT 0")
        except Exception:
            pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weekly_scores (
            user_id INTEGER,
            week_num INTEGER,
            score INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, week_num)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weekly_titles (
            user_id INTEGER PRIMARY KEY,
            title TEXT DEFAULT '',
            week_num INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            min_players INTEGER DEFAULT 4,
            night_time INTEGER DEFAULT 45,
            vote_time INTEGER DEFAULT 45,
            mode TEXT DEFAULT 'classic'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            game_id TEXT,
            timestamp TEXT,
            event TEXT,
            data TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS active_games (
            chat_id INTEGER PRIMARY KEY,
            state TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()


def get_profile(user_id: int, name: str = "", username: str = "") -> dict:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT OR IGNORE INTO profiles (user_id, name, username) VALUES (?, ?, ?)",
            (user_id, name, username)
        )
        conn.commit()
        return {
            "user_id": user_id, "name": name, "username": username,
            "olmos": 0, "dollars": 0, "evro": 0,
            "games": 0, "wins": 0, "losses": 0,
            "bought_role": None, "hero": 0,
            "hero_attack": 0, "hero_defense": 0, "last_daily": None,
        }
    return dict(row)


def save_profile(user_id: int, data: dict):
    conn = get_db()
    conn.execute("""
        UPDATE profiles SET
            name=?, username=?, olmos=?, evro=?,
            games=?, wins=?, losses=?, bought_role=?, hero=?,
            hero_attack=?, hero_defense=?, last_daily=?
        WHERE user_id=?
    """, (
        data.get("name", ""), data.get("username", ""),
        data.get("olmos", 0), data.get("evro", 0),
        data.get("games", 0), data.get("wins", 0), data.get("losses", 0),
        data.get("bought_role"), data.get("hero", 0),
        data.get("hero_attack", 0), data.get("hero_defense", 0),
        data.get("last_daily"), user_id
    ))
    conn.commit()


def update_weekly_score(user_id: int, score_delta: int = 1):
    week_num = datetime.now().isocalendar()[1]
    conn = get_db()
    conn.execute("""
        INSERT INTO weekly_scores (user_id, week_num, score)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, week_num) DO UPDATE SET
            score = score + ?
    """, (user_id, week_num, score_delta, score_delta))
    conn.commit()


def get_weekly_top(limit: int = 20) -> List[dict]:
    week_num = datetime.now().isocalendar()[1]
    conn = get_db()
    rows = conn.execute("""
        SELECT s.user_id, s.score, p.name, p.username
        FROM weekly_scores s
        LEFT JOIN profiles p ON p.user_id = s.user_id
        WHERE s.week_num = ?
        ORDER BY s.score DESC LIMIT ?
    """, (week_num, limit)).fetchall()
    return [dict(r) for r in rows]


def get_weekly_titles_dict() -> dict:
    conn = get_db()
    rows = conn.execute(
        "SELECT user_id, title, week_num FROM weekly_titles"
    ).fetchall()
    return {r["user_id"]: {"title": r["title"], "week": r["week_num"]} for r in rows}


def save_weekly_title(user_id: int, title: str, week_num: int):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO weekly_titles (user_id, title, week_num) VALUES (?, ?, ?)",
        (user_id, title, week_num)
    )
    conn.commit()


def get_chat_setting(chat_id: int, key: str, default=None):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    if row is None:
        return default
    return dict(row).get(key, default)


def set_chat_setting(chat_id: int, key: str, value):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)",
        (chat_id,)
    )
    conn.execute(
        f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?",
        (value, chat_id)
    )
    conn.commit()


def get_all_profiles() -> dict:
    conn = get_db()
    rows = conn.execute("SELECT * FROM profiles").fetchall()
    return {r["user_id"]: dict(r) for r in rows}


def log_event(chat_id: int, game_id: str, event: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO game_logs (chat_id, game_id, timestamp, event, data) VALUES (?, ?, ?, ?, ?)",
            (chat_id, game_id, datetime.now().isoformat(), event, data)
        )
        conn.commit()
    except Exception as e:
        log.error(f"Log write failed: {e}")


def save_active_game(game):
    from .models import MafiaGame
    try:
        state = game.to_dict()
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO active_games (chat_id, state, updated_at) VALUES (?, ?, ?)",
            (game.chat_id, json.dumps(state), datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        log.error(f"Failed to save active game {game.chat_id}: {e}")


def load_active_games():
    from .models import MafiaGame
    conn = get_db()
    rows = conn.execute("SELECT * FROM active_games").fetchall()
    result = {}
    for row in rows:
        try:
            state = json.loads(row["state"])
            state["chat_id"] = row["chat_id"]
            game = MafiaGame.from_dict(state)
            result[game.chat_id] = game
        except Exception as e:
            log.error(f"Failed to load game {row['chat_id']}: {e}")
            conn.execute("DELETE FROM active_games WHERE chat_id = ?", (row["chat_id"],))
            conn.commit()
    return result


def delete_active_game(chat_id: int):
    try:
        conn = get_db()
        conn.execute("DELETE FROM active_games WHERE chat_id = ?", (chat_id,))
        conn.commit()
    except Exception as e:
        log.error(f"Failed to delete active game {chat_id}: {e}")
