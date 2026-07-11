"""
╔══════════════════════════════════════════╗
║        NIGHT KILLERS - MAFIA BOT         ║
║        Production version 4.0            ║
╚══════════════════════════════════════════╝
"""

import asyncio
import logging
import random
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, List, Any, Tuple
import json
import os
import sys
from functools import wraps
from dataclasses import dataclass, field

try:
    sys.path.insert(0, r"D:\pylibs")
except Exception:
    pass

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery, Message, ErrorEvent
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ── CONFIG (env only — no fallbacks for secrets) ──

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7820231987"))
CARD_NUMBER = os.environ.get("CARD_NUMBER", "4073-4200-7154-7032")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mafia.db")

MAX_PLAYERS = 100
MIN_PLAYERS = 4
NIGHT_TIME = 45
DAY_TIME = 45

# ── STATE MACHINE ──

class GamePhase(str, Enum):
    WAITING = "waiting"
    STARTING = "starting"
    ROLE_ASSIGN = "role_assign"
    NIGHT = "night"
    MORNING = "morning"
    DAY = "day"
    VOTING = "voting"
    EXECUTION = "execution"
    ENDED = "ended"

PHASE_DISPLAY = {
    GamePhase.WAITING: "⏳ Ro'yxatdan o'tish",
    GamePhase.STARTING: "🚀 O'yin boshlanmoqda",
    GamePhase.ROLE_ASSIGN: "🎭 Rollar tarqatilmoqda",
    GamePhase.NIGHT: "🌙 Tun",
    GamePhase.MORNING: "🌅 Tong",
    GamePhase.DAY: "☀️ Kun",
    GamePhase.VOTING: "🗳 Ovoz berish",
    GamePhase.EXECUTION: "⚖️ Natija",
    GamePhase.ENDED: "🏁 Tugadi",
}

# ── ROLE SYSTEM ──

class Role(str, Enum):
    MAFIA = "Mafia"
    DON = "Don"
    KOMISSAR = "Komissar"
    DOKTOR = "Doktor"
    TINCH = "Tinch aholi"
    MANIYAK = "Maniyak"
    SHERIF = "Sherif"
    ADVOKAT = "Advokat"

ROLE_ICON = {
    Role.MAFIA: "🔪",
    Role.DON: "👑",
    Role.KOMISSAR: "🔍",
    Role.DOKTOR: "💊",
    Role.TINCH: "👤",
    Role.MANIYAK: "🪓",
    Role.SHERIF: "🛡",
    Role.ADVOKAT: "⚖️",
}

ROLE_EMOJI = {
    Role.MAFIA: "🔪",
    Role.DON: "👑",
    Role.KOMISSAR: "🔍",
    Role.DOKTOR: "💊",
    Role.TINCH: "👤",
    Role.MANIYAK: "🪓",
    Role.SHERIF: "🛡",
    Role.ADVOKAT: "⚖️",
}

ROLE_DISPLAY = {
    Role.MAFIA: "🔪 Mafia",
    Role.DON: "👑 Don",
    Role.KOMISSAR: "🔍 Komissar",
    Role.DOKTOR: "💊 Doktor",
    Role.TINCH: "👤 Tinch aholi",
    Role.MANIYAK: "🪓 Maniyak",
    Role.SHERIF: "🛡 Sherif",
    Role.ADVOKAT: "⚖️ Advokat",
}

ROLE_TEAM = {
    Role.MAFIA: "mafia",
    Role.DON: "mafia",
    Role.KOMISSAR: "village",
    Role.DOKTOR: "village",
    Role.TINCH: "village",
    Role.MANIYAK: "neutral",
    Role.SHERIF: "village",
    Role.ADVOKAT: "village",
}

ROLE_DESC = {
    Role.MAFIA: "Tun bo'yi boshqa mafiya a'zolari bilan kimni o'ldirishni tanlaysiz",
    Role.DON: "Mafiya boshlig'i. Ovozingiz hal qiluvchi",
    Role.KOMISSAR: "Tun bo'yi bir o'yinchini tekshirib, uning mafiya yoki tinch ekanligini bilib olasiz",
    Role.DOKTOR: "Tun bo'yi bir o'yinchini davolaysiz. Mafiya o'sha odamni otsa, u tirik qoladi",
    Role.TINCH: "Tun bo'yi uxlaysiz. Kunning yorishini kutasiz",
    Role.MANIYAK: "Tun bo'yi bir o'yinchini o'ldirasiz. Mafiyadan mustaqil harakat qilasiz",
    Role.SHERIF: "Mafiya sizni otmoqchi bo'lsa, siz ham ulardan birini o'ldirasiz",
    Role.ADVOKAT: "Kun bo'yi bir o'yinchini himoya qilishingiz mumkin. U ovoz berishda chiqarib yuborilmaydi",
}

ROLE_PRICES = {
    Role.MAFIA: 30,
    Role.DON: 80,
    Role.KOMISSAR: 60,
    Role.DOKTOR: 50,
    Role.TINCH: 5,
    Role.MANIYAK: 100,
    Role.SHERIF: 70,
    Role.ADVOKAT: 40,
}

BOT_NAMES = [
    "Alex", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace",
    "Hank", "Ivy", "Jack", "Kate", "Leo", "Mia", "Nick", "Olga",
    "Paul", "Quinn", "Rita", "Sam", "Tina", "Uma", "Vince", "Wendy",
    "Xander", "Yara", "Zack",
]

# ── LOGGING ──

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("MafiaBot")

log = setup_logging()

# ── DATABASE ──

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
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {col} INTEGER DEFAULT 0")
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
        "olmos": 0, "evro": 0,
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

def save_active_game(game: 'MafiaGame'):
    try:
        state = {
            "phase": game.phase.value,
            "day": game.day,
            "game_msg_id": game.game_msg_id,
            "night_time": game.night_time,
            "vote_time": game.vote_time,
            "min_players": game.min_players,
            "game_id": game.game_id,
            "players": {
                str(uid): {
                    "user_id": p.user_id,
                    "name": p.name,
                    "username": p.username,
                    "is_bot": p.is_bot,
                    "role": p.role.value if p.role else None,
                    "team": p.team,
                    "alive": p.alive,
                    "vote": p.vote,
                    "protected": p.protected,
                    "hero_attack": p.hero_attack,
                    "hero_defense": p.hero_defense,
                }
                for uid, p in game.players.items()
            },
            "mafia_votes": {str(k): v for k, v in game.mafia_votes.items()},
            "don_target": game.don_target,
            "komissar_target": game.komissar_target,
            "doktor_target": game.doktor_target,
            "kill_target": game.kill_target,
            "healed_player": game.healed_player,
            "maniyak_target": game.maniyak_target,
            "advokat_protect": game.advokat_protect,
        }
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO active_games (chat_id, state, updated_at) VALUES (?, ?, ?)",
            (game.chat_id, json.dumps(state), datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        log.error(f"Failed to save active game {game.chat_id}: {e}")

def load_active_games() -> Dict[int, 'MafiaGame']:
    conn = get_db()
    rows = conn.execute("SELECT * FROM active_games").fetchall()
    result = {}
    for row in rows:
        try:
            state = json.loads(row["state"])
            game = MafiaGame(chat_id=row["chat_id"])
            game.phase = GamePhase(state["phase"])
            game.day = state["day"]
            game.game_msg_id = state.get("game_msg_id")
            game.night_time = state.get("night_time", NIGHT_TIME)
            game.vote_time = state.get("vote_time", DAY_TIME)
            game.min_players = state.get("min_players", MIN_PLAYERS)
            game.game_id = state.get("game_id", "")
            game.mafia_votes = {int(k): v for k, v in state.get("mafia_votes", {}).items()}
            game.don_target = state.get("don_target")
            game.komissar_target = state.get("komissar_target")
            game.doktor_target = state.get("doktor_target")
            game.kill_target = state.get("kill_target")
            game.healed_player = state.get("healed_player")
            game.maniyak_target = state.get("maniyak_target")
            game.advokat_protect = state.get("advokat_protect")
            for uid_str, pdata in state.get("players", {}).items():
                p = Player(
                    user_id=pdata["user_id"],
                    name=pdata["name"],
                    username=pdata.get("username", ""),
                    is_bot=pdata.get("is_bot", False),
                    role=Role(pdata["role"]) if pdata.get("role") else None,
                    team=pdata.get("team", ""),
                    alive=pdata.get("alive", True),
                    vote=pdata.get("vote"),
                    protected=pdata.get("protected", False),
                    hero_attack=pdata.get("hero_attack", 0),
                    hero_defense=pdata.get("hero_defense", 0),
                )
                game.players[p.user_id] = p
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

# ── PLAYER CLASS ──

@dataclass
class Player:
    user_id: int
    name: str
    username: str = ""
    is_bot: bool = False
    role: Optional[Role] = None
    team: str = ""
    alive: bool = True
    vote: Optional[int] = None
    protected: bool = False
    hero_attack: int = 0
    hero_defense: int = 0
    joined_at: float = field(default_factory=lambda: datetime.now().timestamp())

    @property
    def display(self) -> str:
        if self.username:
            return f"@{self.username}"
        return self.name

    @property
    def role_display(self) -> str:
        if not self.role:
            return "❓ Noma'lum"
        icon = ROLE_ICON.get(self.role, "❓")
        return f"{icon} {self.role.value}"

    def status_icon(self) -> str:
        return "🟢" if self.alive else "💀"

    def to_card(self, show_role: bool = False) -> str:
        lines = [
            f"{self.status_icon()} <b>{self.name}</b>",
            f"├ ID: <code>{self.user_id}</code>",
        ]
        if self.username:
            lines.append(f"├ Username: @{self.username}")
        if show_role and self.role:
            lines.append(f"├ Role: {self.role_display}")
        lines.append(f"└ Status: {'🟢 Alive' if self.alive else '💀 Dead'}")
        return "\n".join(lines)

# ── GAME CLASS ──

@dataclass
class MafiaGame:
    chat_id: int
    phase: GamePhase = GamePhase.WAITING
    day: int = 0
    players: Dict[int, Player] = field(default_factory=dict)
    action_ready: Dict[int, bool] = field(default_factory=dict)
    night_task: Optional[asyncio.Task] = None
    day_task: Optional[asyncio.Task] = None
    game_msg_id: Optional[int] = None
    winner: Optional[str] = None
    start_time: Optional[float] = None
    night_time: int = NIGHT_TIME
    vote_time: int = DAY_TIME
    min_players: int = MIN_PLAYERS
    mafia_votes: Dict[int, int] = field(default_factory=dict)
    don_target: Optional[int] = None
    komissar_target: Optional[int] = None
    doktor_target: Optional[int] = None
    kill_target: Optional[int] = None
    healed_player: Optional[int] = None
    maniyak_target: Optional[int] = None
    advokat_protect: Optional[int] = None
    game_id: str = ""

    def __post_init__(self):
        self.game_id = f"G{self.chat_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.night_time = get_chat_setting(self.chat_id, "night_time", NIGHT_TIME)
        self.vote_time = get_chat_setting(self.chat_id, "vote_time", DAY_TIME)
        self.min_players = get_chat_setting(self.chat_id, "min_players", MIN_PLAYERS)

    @property
    def alive_players(self) -> List[Player]:
        return [p for p in self.players.values() if p.alive]

    @property
    def mafia_players(self) -> List[Player]:
        return [p for p in self.alive_players if p.team == "mafia"]

    @property
    def village_players(self) -> List[Player]:
        return [p for p in self.alive_players if p.team == "village"]

    @property
    def mafia_votes_received(self) -> Dict[int, int]:
        votes = {}
        for target in self.mafia_votes.values():
            votes[target] = votes.get(target, 0) + 1
        if self.don_target is not None:
            votes[self.don_target] = votes.get(self.don_target, 0) + 1
        return votes

    def get_player(self, user_id: int) -> Optional[Player]:
        return self.players.get(user_id)

    def cancel_timers(self):
        for t in [self.night_task, self.day_task]:
            if t and not t.done():
                t.cancel()
        self.night_task = None
        self.day_task = None

    def reset_night(self):
        for p in self.players.values():
            p.protected = False
        self.action_ready = {}
        self.mafia_votes = {}
        self.don_target = None
        self.komissar_target = None
        self.doktor_target = None
        self.kill_target = None
        self.healed_player = None
        self.maniyak_target = None
        self.advokat_protect = None

    def reset_day(self):
        for p in self.players.values():
            p.vote = None
        self.action_ready = {}

    def get_roles_text(self) -> str:
        lines = []
        for p in self.players.values():
            icon = ROLE_ICON.get(p.role, "❓") if p.role else "❓"
            status = "✅" if p.alive else "💀"
            lines.append(f"{status} {p.display}: {icon} {p.role.value if p.role else 'Noma\'lum'}")
        return "\n".join(lines)

    def player_list_text(self, show_roles: bool = False) -> str:
        parts = []
        for p in self.players.values():
            if p.alive:
                team_icon = "🔪" if p.team == "mafia" else "👤"
                role_part = f" ({p.role_display})" if show_roles and p.role else ""
                parts.append(f"{team_icon} {p.display}{role_part}")
        return "\n".join(parts)

    def log(self, event: str, data: str = ""):
        log_event(self.chat_id, self.game_id, event, data)
        save_active_game(self)

# ── GLOBAL STATE ──

games: Dict[int, MafiaGame] = {}
bot_instance: Optional[Bot] = None
dp_instance: Optional[Dispatcher] = None

# ── HELPERS ──

def safe(coro):
    """Run async call safely, logging errors instead of crashing."""
    async def wrapper(*args, **kwargs):
        try:
            return await coro(*args, **kwargs)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error(f"Error in {coro.__name__}: {e}", exc_info=True)
            return None
    return wrapper

def make_inline_keyboard(buttons: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def make_players_keyboard(
    players: List[Player],
    callback_prefix: str,
    chat_id: Optional[int] = None,
    exclude_ids: Optional[set] = None,
    columns: int = 2,
    show_roles: bool = False,
) -> InlineKeyboardMarkup:
    exclude_ids = exclude_ids or set()
    builder = InlineKeyboardBuilder()
    for p in players:
        if p.user_id not in exclude_ids:
            prefix = f"{callback_prefix}:{chat_id}" if chat_id is not None else callback_prefix
            role_icon = ROLE_ICON.get(p.role, "👤") if p.role and show_roles else "👤"
            builder.button(
                text=f"{p.status_icon()} {role_icon} {p.display}",
                callback_data=f"{prefix}:{p.user_id}"
            )
    builder.adjust(columns)
    return builder.as_markup()

async def safe_send_message(
    bot: Bot, chat_id: int, text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML"
) -> Optional[Message]:
    try:
        return await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramForbiddenError:
        log.warning(f"Cannot send to {chat_id} (blocked)")
    except TelegramBadRequest as e:
        log.warning(f"Send error to {chat_id}: {e}")
    except Exception as e:
        log.error(f"Unexpected send error: {e}")
    return None

async def safe_edit_message(
    bot: Bot, chat_id: int, message_id: int,
    text: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: str = "HTML"
):
    try:
        if text is not None:
            await bot.edit_message_text(
                text, chat_id=chat_id, message_id=message_id,
                reply_markup=reply_markup, parse_mode=parse_mode
            )
    except TelegramBadRequest:
        try:
            await bot.edit_message_caption(
                chat_id=chat_id, message_id=message_id,
                caption=text, reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except TelegramBadRequest:
            pass
    except Exception as e:
        log.error(f"Edit error: {e}")

def check_winner(game: MafiaGame) -> Optional[str]:
    alive = game.alive_players
    mafia_alive = len([p for p in alive if p.team == "mafia"])
    village_alive = len([p for p in alive if p.team == "village"])
    neutral_alive = len([p for p in alive if p.team == "neutral"])
    if neutral_alive == 1 and mafia_alive + village_alive == 0:
        return "neutral"
    if mafia_alive == 0:
        return "village"
    if mafia_alive >= village_alive:
        return "mafia"
    return None

def distribute_roles(player_count: int) -> List[Role]:
    roles = []
    if player_count <= 6:
        mafia_count = 1
    elif player_count <= 10:
        mafia_count = 2
    elif player_count <= 15:
        mafia_count = 3
    else:
        mafia_count = 4
    roles.extend([Role.MAFIA] * mafia_count)
    roles.append(Role.DON)
    roles.append(Role.KOMISSAR)
    roles.append(Role.DOKTOR)
    while len(roles) < player_count:
        roles.append(Role.TINCH)
    random.shuffle(roles)
    return roles

def validate_callback(
    callback: CallbackQuery, game: Optional[MafiaGame],
    allowed_phases: Optional[List[GamePhase]] = None,
    require_alive: bool = False,
) -> Optional[str]:
    if game is None:
        return "❌ O'yin topilmadi"
    if allowed_phases and game.phase not in allowed_phases:
        return f"❌ Bu amal {PHASE_DISPLAY.get(game.phase, game.phase.value)} fazasida mumkin emas"
    if require_alive:
        player = game.get_player(callback.from_user.id)
        if not player:
            return "❌ Siz o'yinda emassiz"
        if not player.alive:
            return "💀 Siz o'lgansiz"
    return None

# ── UI COMPONENTS ──

def make_game_banner(phase: GamePhase, day: int = 0) -> str:
    banners = {
        GamePhase.WAITING: "═══════════════════════════════════\n💀 <b>NIGHT KILLERS</b> 💀\n═══════════════════════════════════",
        GamePhase.NIGHT: "╔══════════════════════════════════╗\n║         🌙 TUN FAZASI 🌙          ║\n╚══════════════════════════════════╝",
        GamePhase.MORNING: "╔══════════════════════════════════╗\n║        🌅 TONG OTD! 🌅            ║\n╚══════════════════════════════════╝",
        GamePhase.DAY: "╔══════════════════════════════════╗\n║         ☀️ KUN FAZASI ☀️          ║\n╚══════════════════════════════════╝",
        GamePhase.VOTING: "╔══════════════════════════════════╗\n║       🗳 OVOZ BERISH 🗳           ║\n╚══════════════════════════════════╝",
        GamePhase.EXECUTION: "╔══════════════════════════════════╗\n║       ⚖️ NATIJA ⚖️              ║\n╚══════════════════════════════════╝",
        GamePhase.ENDED: "╔══════════════════════════════════╗\n║        🏆 O'YIN TUGADI 🏆        ║\n╚══════════════════════════════════╝",
        GamePhase.STARTING: "╔══════════════════════════════════╗\n║      🚀 O'YIN BOSHLANDI 🚀       ║\n╚══════════════════════════════════╝",
        GamePhase.ROLE_ASSIGN: "╔══════════════════════════════════╗\n║      🎭 ROLLAR TARQATILMOQDA 🎭   ║\n╚══════════════════════════════════╝",
    }
    banner = banners.get(phase, "═══════════════════════════════════")
    if day > 0:
        banner += f"\n📅 <b>{day}-kun / {day}-tun</b>"
    return banner

def make_player_card(player: Player, show_role: bool = False) -> str:
    team_icon = "🔪" if player.team == "mafia" else "👤"
    role_line = f"├ {'Role'}: {player.role_display}\n" if show_role and player.role else ""
    return (
        f"{'🟢' if player.alive else '💀'} <b>{player.display}</b>\n"
        f"{role_line}"
        f"└ {'Status'}: {'Alive ✅' if player.alive else 'Dead ❌'}"
    )

# ── COMMAND HANDLERS ──

async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    get_profile(user.id, user.first_name, user.username or "")
    try:
        bot_user = await bot.get_me()
        bot_username = bot_user.username
    except:
        bot_username = "Nightkillersbot"

    text = (
        f"<b>🌙 NIGHT KILLERS</b>\n"
        f"<i>Zulmatda hech kim begunoh emas...</i>\n\n"
        f"👤 <b>{user.first_name}</b>, xush kelibsiz!\n\n"
        f"<b>Nega aynan biz?</b>\n"
        f"🌙 5 xil rol bilan qiziqarli o'yin\n"
        f"🏆 Haftalik reyting va noyob unvonlar\n"
        f"💎 Olmos va evro — iqtisod tizimi\n"
        f"🦸 Hero va maxsus imkoniyatlar\n\n"
        f"<b>O'ynash uchun:</b>\n"
        f"1️⃣ Guruhga @{bot_username} qo'shing\n"
        f"2️⃣ /mafia yozib o'yin yarating\n"
        f"3️⃣ /join yoki tugmani bosing\n"
        f"4️⃣ Admin /startgame bilan boshlaydi"
    )

    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="🎮 O'yin yaratish", url=f"https://t.me/{bot_username}?startgroup=new"),
         InlineKeyboardButton(text="➕ Qo'shilish", callback_data="start_join")],
        [InlineKeyboardButton(text="👤 Profil", callback_data="start_profile"),
         InlineKeyboardButton(text="💰 Hisob", callback_data="start_money")],
        [InlineKeyboardButton(text="🏆 Reyting", callback_data="start_top"),
         InlineKeyboardButton(text="🛒 Do'kon", callback_data="start_shop")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="start_stats"),
         InlineKeyboardButton(text="📖 Yordam", callback_data="start_help")],
        [InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="start_about")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

async def cmd_mafia(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        await message.answer("❌ Bu buyruq faqat guruhlarda ishlaydi!")
        return
    if chat_id in games:
        existing = games[chat_id]
        if existing.phase != GamePhase.ENDED:
            await message.answer(
                f"❌ Bu guruhda allaqachon o'yin davom etmoqda.\n"
                f"Faza: {PHASE_DISPLAY.get(existing.phase, existing.phase.value)}\n"
                f"Avval mavjud o'yinni tugating."
            )
            return

    game = MafiaGame(chat_id)
    games[chat_id] = game
    game.log("game_created", f"by {message.from_user.id}")

    text = (
        f"{make_game_banner(GamePhase.WAITING)}\n\n"
        f"<b>O'yin yaratildi!</b>\n"
        f"Ro'yxatdan o'tish boshlandi.\n\n"
        f"➕ Qo'shilish uchun /join bosing\n"
        f"👥 Minimal: {game.min_players} o'yinchi\n\n"
        f"<b>O'yinchilar:</b>\n"
        f"Hali hech kim qo'shilgani yo'q."
    )

    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="➕ Qo'shilish", callback_data=f"join:{chat_id}")],
        [InlineKeyboardButton(text="❌ Chiqish", callback_data=f"leave:{chat_id}")],
    ])

    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    game.game_msg_id = sent.message_id

async def cmd_join(message: Message, bot: Bot):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas! /mafia yozib o'yin yarating.")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await message.answer("❌ O'yin boshlangan. Yangi o'yinchi qo'shila olmaydi.")
        return
    if user.id in game.players:
        await message.answer("❌ Siz allaqachon o'yindasiz!")
        return
    if len(game.players) >= MAX_PLAYERS:
        await message.answer("❌ O'yin to'liq!")
        return

    game.players[user.id] = Player(
        user_id=user.id, name=user.first_name, username=user.username or ""
    )
    game.log("player_joined", f"{user.id}")
    await update_game_message(game, bot)
    try:
        await bot.send_message(
            user.id,
            f"✅ O'yinga qo'shildingiz!\n"
            f"Guruh: {message.chat.title}\n"
            f"O'yin boshlanishini kuting."
        )
    except TelegramForbiddenError:
        pass

async def cmd_leave(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await message.answer("❌ Ro'yxatdan o'tish tugagan!")
        return
    if user_id not in game.players:
        await message.answer("❌ Siz o'yinda emassiz!")
        return
    del game.players[user_id]
    game.log("player_left", f"{user_id}")
    await update_game_message(game, bot)
    await message.answer("✅ O'yindan chiqdingiz.")

async def cmd_startgame(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await message.answer("❌ O'yin allaqachon boshlangan!")
        return
    if user_id != ADMIN_ID:
        is_group_admin = False
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            is_group_admin = member.status in ("creator", "administrator")
        except:
            pass
        if not is_group_admin:
            await message.answer("❌ Faqat admin o'yinni boshlashi mumkin!")
            return

    player_count = len(game.players)
    if player_count < game.min_players:
        await message.answer(f"❌ Kamida {game.min_players} o'yinchi kerak! Hozir: {player_count}")
        return

    # ── Lobby lock: STARTING phase ──
    game.phase = GamePhase.STARTING
    game.log("game_starting", f"{player_count} players")

    # ── Role assignment ──
    game.phase = GamePhase.ROLE_ASSIGN
    roles_available = distribute_roles(player_count)
    random.shuffle(roles_available)
    assigned_roles = []
    bought_role_players = []
    for player in game.players.values():
        profile = get_profile(player.user_id)
        bought = profile.get("bought_role")
        if bought:
            try:
                preferred = Role(bought)
                if preferred in roles_available:
                    player.role = preferred
                    player.team = ROLE_TEAM.get(preferred, "village")
                    roles_available.remove(preferred)
                    assigned_roles.append(player.user_id)
                    if profile.get("hero"):
                        player.hero_attack = profile.get("hero_attack", 0)
                        player.hero_defense = profile.get("hero_defense", 0)
            except ValueError:
                pass
    for player in game.players.values():
        if player.user_id in assigned_roles:
            continue
        if roles_available:
            role = roles_available.pop(0)
            player.role = role
            player.team = ROLE_TEAM.get(role, "village")
        profile = get_profile(player.user_id)
        if profile.get("hero"):
            player.hero_attack = profile.get("hero_attack", 0)
            player.hero_defense = profile.get("hero_defense", 0)

    game.log("roles_assigned", f"{player_count} roles distributed")

    # ── Game message ──
    player_list = "\n".join([f"• {p.display}" for p in game.players.values()])
    text = (
        f"{make_game_banner(GamePhase.STARTING)}\n\n"
        f"<b>O'yinchilar ({player_count}):</b>\n{player_list}\n\n"
        f"{make_game_banner(GamePhase.NIGHT, 1)}"
    )
    if game.game_msg_id:
        await safe_edit_message(bot, chat_id, game.game_msg_id, text)

    # ── Send roles to each player ──
    try:
        bot_user = await bot.get_me()
        bot_username = bot_user.username
    except:
        bot_username = "Nightkillersbot"

    blocked_users = []
    for player in game.players.values():
        role_text = (
            f"🌙 <b>NIGHT KILLERS</b>\n\n"
            f"Sizning rolingiz: <b>{ROLE_DISPLAY.get(player.role, player.role.value if player.role else '?')}</b>\n\n"
            f"{ROLE_DESC.get(player.role, '')}\n\n"
        )
        if player.role in (Role.MAFIA, Role.DON):
            teammates = [p for p in game.players.values() if p.team == "mafia" and p.user_id != player.user_id]
            if teammates:
                role_text += "👥 <b>Sizning mafia guruingiz:</b>\n"
                for t in teammates:
                    role_text += f"• {t.display}\n"
        result = await safe_send_message(bot, player.user_id, role_text)
        if result is None:
            blocked_users.append(player.display)
        await asyncio.sleep(0.05)

    if blocked_users:
        await message.answer(
            f"⚠️ <b>Ogohlantirish:</b>\n"
            f"Quyidagi o'yinchilar botni shaxsiy xabarda ishga tushirmagan:\n"
            f"{chr(10).join('• ' + u for u in blocked_users)}\n\n"
            f"Ular <b>@{bot_username}</b> ga yozib /start bosmagani uchun\n"
            f"rol va tungi tugmalarni ololmaydi!\n"
            f"Iltimos, ularga botga yozishni ayting.",
            parse_mode="HTML"
        )

    await message.answer(
        f"🌙 <b>1-tun boshlandi!</b>\n"
        f"Tun davomiyligi: {game.night_time} soniya\n\n"
        f"Maxsus rollar PM dan harakat qiling."
    )

    await start_night_phase(game, bot)

async def cmd_cancel(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!")
        return

    is_global_admin = (user_id == ADMIN_ID)
    is_group_admin = False
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        is_group_admin = member.status in ("creator", "administrator")
    except:
        pass

    if not is_global_admin and not is_group_admin:
        await message.answer("❌ Faqat guruh admini o'yinni bekor qilishi mumkin!")
        return

    game = games[chat_id]
    game.cancel_timers()
    game.phase = GamePhase.ENDED
    game.log("game_cancelled", f"by {user_id}")
    del games[chat_id]
    delete_active_game(chat_id)
    await message.answer("❌ O'yin bekor qilindi.")

async def update_game_message(game: MafiaGame, bot: Bot):
    if not game.game_msg_id:
        return
    count = len(game.players)
    player_list = "\n".join([
        f"{i}. {p.display}" for i, p in enumerate(game.players.values(), 1)
    ]) or "Hali hech kim qo'shilgani yo'q."

    text = (
        f"{make_game_banner(GamePhase.WAITING)}\n\n"
        f"<b>O'yinchilar ({count}):</b>\n{player_list}\n\n"
        f"Minimal: {game.min_players} o'yinchi"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="➕ Qo'shilish", callback_data=f"join:{game.chat_id}")],
        [InlineKeyboardButton(text="❌ Chiqish", callback_data=f"leave:{game.chat_id}")],
    ])
    await safe_edit_message(bot, game.chat_id, game.game_msg_id, text, reply_markup=kb)

# ── NIGHT PHASE ──

async def start_night_phase(game: MafiaGame, bot: Bot):
    game.cancel_timers()
    game.phase = GamePhase.NIGHT
    game.day += 1
    game.reset_night()
    game.log("night_started", f"Day {game.day}")

    mafia_targets = [p for p in game.alive_players if p.team != "mafia"]
    cid = game.chat_id

    for player in game.alive_players:
        if player.role == Role.MAFIA:
            if mafia_targets:
                kb = make_players_keyboard(mafia_targets, "nv_kill", chat_id=cid)
                await safe_send_message(
                    bot, player.user_id,
                    f"🌙 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz?",
                    reply_markup=kb
                )
            game.action_ready[player.user_id] = False

        elif player.role == Role.DON:
            if mafia_targets:
                kb = make_players_keyboard(mafia_targets, "nv_don", chat_id=cid)
                await safe_send_message(
                    bot, player.user_id,
                    f"🌙 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz? (Sizning ovozingiz hal qiluvchi)",
                    reply_markup=kb
                )
            game.action_ready[player.user_id] = False

        elif player.role == Role.KOMISSAR:
            check_targets = [p for p in game.alive_players if p.user_id != player.user_id]
            if check_targets:
                kb = make_players_keyboard(check_targets, "nv_check", chat_id=cid)
                await safe_send_message(
                    bot, player.user_id,
                    f"🌙 <b>{game.day}-tun</b>\n\nKimni tekshiramiz? 🔍",
                    reply_markup=kb
                )
            game.action_ready[player.user_id] = False

        elif player.role == Role.DOKTOR:
            heal_targets = [p for p in game.alive_players if p.user_id != player.user_id]
            if heal_targets:
                kb = make_players_keyboard(heal_targets, "nv_heal", chat_id=cid)
                await safe_send_message(
                    bot, player.user_id,
                    f"🌙 <b>{game.day}-tun</b>\n\nKimni davolaymiz?",
                    reply_markup=kb
                )
            game.action_ready[player.user_id] = False

        elif player.role == Role.MANIYAK:
            maniyak_targets = [p for p in game.alive_players if p.user_id != player.user_id]
            if maniyak_targets:
                kb = make_players_keyboard(maniyak_targets, "nv_maniyak", chat_id=cid)
                await safe_send_message(
                    bot, player.user_id,
                    f"🪓 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz? (Mustaqil harakat)",
                    reply_markup=kb
                )
            game.action_ready[player.user_id] = False

        elif player.role == Role.SHERIF:
            await safe_send_message(
                bot, player.user_id,
                f"🛡 <b>{game.day}-tun</b>\n\nSiz himoyadasiz. Mafiya sizni otmoqchi bo'lsa, ulardan biri o'ladi."
            )
            game.action_ready[player.user_id] = True

        else:
            await safe_send_message(bot, player.user_id, f"🌙 <b>{game.day}-tun</b>\n\nSiz uxlayapsiz... Ertangi kunni kuting.")
            game.action_ready[player.user_id] = True

        await asyncio.sleep(0.05)

    game.night_task = asyncio.create_task(night_timer(game, bot))

async def night_timer(game: MafiaGame, bot: Bot):
    try:
        await asyncio.sleep(game.night_time)
        await end_night_phase(game, bot)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"Night timer error for {game.chat_id}: {e}")

async def end_night_phase(game: MafiaGame, bot: Bot):
    if game.phase != GamePhase.NIGHT:
        return
    game.log("night_ended", f"Day {game.day}")

    # ── Resolve night actions ──
    mafia_votes = game.mafia_votes_received
    if mafia_votes:
        max_votes = max(mafia_votes.values())
        top_targets = [t for t, v in mafia_votes.items() if v == max_votes]
        game.kill_target = random.choice(top_targets)
    elif game.don_target is not None:
        game.kill_target = game.don_target

    killed_player = None
    if game.kill_target is not None and game.kill_target in game.players:
        target = game.get_player(game.kill_target)
        if target and target.alive:
            if game.kill_target == game.doktor_target:
                game.healed_player = game.kill_target
                target.protected = True
            else:
                target.alive = False
                killed_player = target

    # ── Maniyak kill ──
    maniyak_killed = None
    if game.maniyak_target is not None and game.maniyak_target in game.players:
        target = game.get_player(game.maniyak_target)
        if target and target.alive:
            target.alive = False
            maniyak_killed = target

    # ── Sherif vengeance ──
    sherif_vengeance = None
    if killed_player and killed_player.role == Role.SHERIF:
        mafia_alive = game.mafia_players
        if mafia_alive:
            vengeance_target = random.choice(mafia_alive)
            vengeance_target.alive = False
            sherif_vengeance = vengeance_target

    # ── Detective result ──
    if game.komissar_target is not None and game.komissar_target in game.players:
        checked = game.get_player(game.komissar_target)
        if checked:
            is_mafia = checked.team == "mafia"
            result = "🔴 MAFIA" if is_mafia else "🟢 Tinch aholi"
            for p in game.players.values():
                if p.role == Role.KOMISSAR and p.alive:
                    await safe_send_message(
                        bot, p.user_id,
                        f"🔍 <b>Tekshiruv natijasi:</b>\n{checked.display}: {result}"
                    )

    # ── Morning message ──
    game.phase = GamePhase.MORNING
    death_messages = []
    if killed_player:
        death_messages.append(f"💀 <b>{killed_player.display}</b> o'ldirildi! ({ROLE_ICON.get(killed_player.role, '❓')} {killed_player.role.value if killed_player.role else '?'})")
    if sherif_vengeance:
        death_messages.append(f"🛡 Sherif qasosi! <b>{sherif_vengeance.display}</b> otib o'ldirildi! ({ROLE_ICON.get(sherif_vengeance.role, '❓')} {sherif_vengeance.role.value if sherif_vengeance.role else '?'})")
    if maniyak_killed and maniyak_killed != killed_player:
        death_messages.append(f"🪓 <b>{maniyak_killed.display}</b> Maniyak tomonidan o'ldirildi! ({ROLE_ICON.get(maniyak_killed.role, '❓')} {maniyak_killed.role.value if maniyak_killed.role else '?'})")
    if game.healed_player and not killed_player:
        healed = game.get_player(game.healed_player)
        death_messages.append(f"💊 Doktor {healed.display} ni davoladi! Hech kim o'lmadi!" if healed else "Bu tun hech kim o'lmadi...")

    if death_messages:
        text = f"{make_game_banner(GamePhase.MORNING, game.day)}\n\n" + "\n".join(death_messages) + "\n\n"
    else:
        text = f"{make_game_banner(GamePhase.MORNING, game.day)}\n\nBu tun hech kim o'lmadi...\n\n"

    alive_list = "\n".join([
        make_player_card(p) for p in game.alive_players
    ])
    text += f"<b>Tirik o'yinchilar ({len(game.alive_players)}):</b>\n{alive_list}\n\n"

    winner = check_winner(game)
    if winner:
        await end_game(game, bot, winner)
        return

    text += f"⏳ <b>Ovoz berish {game.vote_time} soniyadan keyin boshlanadi...</b>"
    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text)

    game.day_task = asyncio.create_task(morning_timer(game, bot))

async def morning_timer(game: MafiaGame, bot: Bot):
    try:
        await asyncio.sleep(10)
        await start_day_phase(game, bot)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"Morning timer error for {game.chat_id}: {e}")

# ── DAY PHASE ──

async def start_day_phase(game: MafiaGame, bot: Bot):
    if game.phase != GamePhase.MORNING:
        return
    game.phase = GamePhase.VOTING
    game.reset_day()
    game.log("voting_started", f"Day {game.day}")

    text = (
        f"{make_game_banner(GamePhase.VOTING, game.day)}\n\n"
        f"⏱ Vaqt: {game.vote_time} soniya\n\n"
        f"<b>Tirik o'yinchilar ({len(game.alive_players)}):</b>\n" +
        "\n".join([make_player_card(p) for p in game.alive_players]) +
        "\n\n<b>Kimni chetlatamiz?</b>"
    )

    kb = make_players_keyboard(game.alive_players, "d_vote", chat_id=game.chat_id, columns=2)
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"d_skip:{game.chat_id}")
    ])

    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text, reply_markup=kb)
    else:
        sent = await bot.send_message(game.chat_id, text, reply_markup=kb, parse_mode="HTML")
        game.game_msg_id = sent.message_id

    game.cancel_timers()
    game.day_task = asyncio.create_task(day_timer(game, bot))

async def day_timer(game: MafiaGame, bot: Bot):
    try:
        await asyncio.sleep(game.vote_time)
        await end_day_phase(game, bot)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"Day timer error for {game.chat_id}: {e}")

async def end_day_phase(game: MafiaGame, bot: Bot):
    if game.phase != GamePhase.VOTING:
        return
    game.phase = GamePhase.EXECUTION
    game.log("voting_ended", f"Day {game.day}")

    # ── Count votes ──
    votes = {}
    for player in game.alive_players:
        if player.vote is not None and player.vote > 0:
            votes[player.vote] = votes.get(player.vote, 0) + 1

    eliminated = None
    if votes:
        max_votes = max(votes.values())
        top_voted = [t for t, v in votes.items() if v == max_votes]
        elim_id = random.choice(top_voted)
        eliminated = game.get_player(elim_id)
        if eliminated:
            eliminated.alive = False

    # ── Results ──
    text = (
        f"{make_game_banner(GamePhase.EXECUTION, game.day)}\n\n"
    )
    if eliminated:
        text += (
            f"🗳 <b>{eliminated.display}</b> eng ko'p ovoz oldi!\n"
            f"Role: {ROLE_ICON.get(eliminated.role, '❓')} <b>{eliminated.role.value if eliminated.role else '?'}</b>\n\n"
        )
    else:
        text += "Hech kim ovoz bermadi... Chetlatish yo'q.\n\n"

    alive_list = "\n".join([make_player_card(p) for p in game.alive_players])
    text += f"<b>Tirik o'yinchilar ({len(game.alive_players)}):</b>\n{alive_list}\n\n"

    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text)

    winner = check_winner(game)
    if winner:
        await end_game(game, bot, winner)
        return

    text += f"🌙 <b>{game.day + 1}-tun boshlandi!</b>\nMaxsus rollar PM dan harakat qiling."
    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text)

    await start_night_phase(game, bot)

async def end_game(game: MafiaGame, bot: Bot, winner: str):
    game.phase = GamePhase.ENDED
    game.winner = winner
    game.cancel_timers()
    game.log("game_ended", f"Winner: {winner}")

    for player in game.players.values():
        profile = get_profile(player.user_id)
        profile["games"] = profile.get("games", 0) + 1
        if winner == player.team:
            profile["wins"] = profile.get("wins", 0) + 1
            update_weekly_score(player.user_id, 3)
        else:
            profile["losses"] = profile.get("losses", 0) + 1
            update_weekly_score(player.user_id, 1)
        save_profile(player.user_id, profile)

    if winner == "neutral":
        winner_text = "🪓 <b>MANIYAK</b>"
    else:
        winner_text = "🔪 <b>MAFIA</b>" if winner == "mafia" else "👤 <b>VILLAGE</b>"
    text = (
        f"{make_game_banner(GamePhase.ENDED)}\n\n"
        f"🏆 <b>G'olib: {winner_text}</b> 🏆\n\n"
        f"<b>Barcha rol va o'yinchilar:</b>\n{game.get_roles_text()}\n\n"
        f"Yangi o'yin uchun /mafia yozing."
    )

    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text)
    else:
        await bot.send_message(game.chat_id, text, parse_mode="HTML")

    if game.chat_id in games:
        del games[game.chat_id]
    delete_active_game(game.chat_id)

async def continue_game(bot: Bot, chat_id: int):
    if chat_id not in games:
        return
    game = games[chat_id]
    phase_banner = make_game_banner(game.phase)
    if game.phase == GamePhase.NIGHT:
        await bot.send_message(chat_id, f"{phase_banner}\n\n🌙 Tun davom etmoqda...")
        game.night_task = asyncio.create_task(night_timer(game, bot))
    elif game.phase == GamePhase.MORNING:
        await bot.send_message(chat_id, f"{phase_banner}\n\n🌅 Ertalab... Natijalar kutilmoqda.")
    elif game.phase == GamePhase.VOTING:
        await bot.send_message(chat_id, f"{phase_banner}\n\n🗳 Ovoz berish davom etmoqda.")
        game.day_task = asyncio.create_task(day_timer(game, bot))
    elif game.phase == GamePhase.WAITING:
        await bot.send_message(chat_id, "🔄 Bot qayta ishga tushdi. Lobby saqlanib qoldi.")
        await update_game_message(game, bot)

# ── CALLBACK HANDLER ──

async def handle_callback(callback: CallbackQuery, bot: Bot):
    data = callback.data
    user_id = callback.from_user.id

    try:
        await callback.answer()
    except:
        pass

    try:
        # ── Start menu ──
        if data == "start_join":
            await callback.answer("O'yin bor guruhda /join yozing!")
            return
        if data == "start_profile":
            await show_profile(callback, bot); return
        if data == "start_money":
            await show_money(callback, bot); return
        if data == "start_top":
            await show_top(callback, bot); return
        if data == "start_shop":
            await show_shop(callback, bot); return
        if data == "start_stats":
            await show_stats_cb(callback, bot); return
        if data == "start_help":
            await show_help(callback, bot); return
        if data == "start_about":
            await show_about(callback, bot); return
        if data == "start_weekly":
            await show_weekly(callback, bot); return

        # ── Payment ──
        if data == "payment":
            await show_payment(callback, bot); return

        # ── Join/Leave ──
        if data.startswith("join:"):
            await handle_join_callback(callback, bot); return
        if data.startswith("leave:"):
            await handle_leave_callback(callback, bot); return

        # ── Night actions ──
        if data.startswith("nv_kill:"):
            await handle_night_kill(callback, bot); return
        if data.startswith("nv_don:"):
            await handle_night_don(callback, bot); return
        if data.startswith("nv_check:"):
            await handle_night_check(callback, bot); return
        if data.startswith("nv_heal:"):
            await handle_night_heal(callback, bot); return
        if data.startswith("nv_maniyak:"):
            await handle_night_maniyak(callback, bot); return

        # ── Day vote ──
        if data.startswith("d_vote:"):
            await handle_day_vote(callback, bot); return
        if data.startswith("d_skip:"):
            await handle_day_skip(callback, bot); return

        # ── Shop ──
        if data == "buyhero":
            await handle_buy_hero(callback, bot); return
        if data == "buyrole":
            await handle_buy_role_menu(callback, bot); return
        if data.startswith("buyrole:"):
            await handle_buy_role_confirm(callback, bot); return

        # ── Payment confirm/reject ──
        if data.startswith("confirm_pay:"):
            if user_id != ADMIN_ID:
                await callback.answer("❌ Faqat admin!", show_alert=True); return
            target_id = int(data.split(":")[1])
            profile = get_profile(target_id)
            profile["olmos"] = profile.get("olmos", 0) + 50
            save_profile(target_id, profile)
            await callback.message.edit_caption("✅ To'lov tasdiqlandi!")
            await bot.send_message(target_id, "✅ To'lockingiz tasdiqlandi! +50💎 olmos hisobingizga qo'shildi.")
            return
        if data.startswith("reject_pay:"):
            if user_id != ADMIN_ID:
                await callback.answer("❌ Faqat admin!", show_alert=True); return
            target_id = int(data.split(":")[1])
            await callback.message.edit_caption("❌ To'lov rad etildi.")
            await bot.send_message(target_id, "❌ To'lockingiz rad etildi. Admin bilan bog'lanib tekshiring.")
            return

        # ── Back to menu ──
        if data == "back_menu":
            await show_main_menu(callback, bot); return

    except Exception as e:
        log.error(f"Callback error: {data} by {user_id}: {e}", exc_info=True)
        try:
            await callback.answer("Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", show_alert=True)
        except:
            pass

# ── CALLBACK HANDLERS ──

async def show_main_menu(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    try:
        bot_user = await bot.get_me()
        bot_username = bot_user.username
    except:
        bot_username = "Nightkillersbot"

    text = (
        f"<b>🌙 NIGHT KILLERS</b>\n"
        f"<i>Zulmatda hech kim begunoh emas...</i>\n\n"
        f"👤 <b>{user.first_name}</b>, xush kelibsiz!\n\n"
        f"<b>Nega aynan biz?</b>\n"
        f"🌙 8 xil rol bilan qiziqarli o'yin\n"
        f"🏆 Haftalik reyting va noyob unvonlar\n"
        f"💎 Olmos va evro — iqtisod tizimi\n"
        f"🦸 Hero va maxsus imkoniyatlar"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="🎮 O'yin yaratish", url=f"https://t.me/{bot_username}?startgroup=new"),
         InlineKeyboardButton(text="➕ Qo'shilish", callback_data="start_join")],
        [InlineKeyboardButton(text="👤 Profil", callback_data="start_profile"),
         InlineKeyboardButton(text="💰 Hisob", callback_data="start_money")],
        [InlineKeyboardButton(text="🏆 Reyting", callback_data="start_top"),
         InlineKeyboardButton(text="🛒 Do'kon", callback_data="start_shop")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="start_stats"),
         InlineKeyboardButton(text="📖 Yordam", callback_data="start_help")],
        [InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="start_about")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_profile(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    profile = get_profile(user.id, user.first_name, user.username or "")
    hero_str = f"⚔ {profile.get('hero_attack',0)}/🛡 {profile.get('hero_defense',0)}" if profile.get("hero") else "❌ Yo'q"
    role_str = profile.get("bought_role") or "Yo'q"
    pct = profile.get('wins', 0) / max(profile.get('games', 0), 1) * 100

    text = (
        f"👤 <b>{user.first_name}</b>\n\n"
        f"💎 Olmos: <b>{profile.get('olmos', 0)}</b>\n"
        f"💶 Evro: <b>{profile.get('evro', 0)}</b>\n\n"
        f"🦸 Hero: {hero_str}\n"
        f"🎭 Rol: {role_str}\n\n"
        f"📊 <b>Statistika</b>\n"
        f"🎮 O'yinlar: {profile.get('games', 0)}\n"
        f"🏆 G'alaba: {profile.get('wins', 0)}\n"
        f"💔 Mag'lubiyat: {profile.get('losses', 0)}\n"
        f"📈 Winrate: <b>{pct:.1f}%</b>"
    )
    titles = get_weekly_titles_dict()
    if user.id in titles:
        text += f"\n\n🏅 <b>Unvon:</b> {titles[user.id]['title']}"

    kb = make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_money(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    profile = get_profile(user.id, user.first_name, user.username or "")
    text = (
        f"💰 <b>Hisobingiz</b>\n\n"
        f"💎 Olmos: <b>{profile.get('olmos', 0)}</b>\n"
        f"💶 Evro: <b>{profile.get('evro', 0)}</b>\n\n"
        f"💱 /change sum — Olmos → Evro\n"
        f"📤 /send @user sum — Olmos yuborish"
    )
    kb = make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_top(callback: CallbackQuery, bot: Bot):
    profiles = get_all_profiles()
    sorted_users = sorted(profiles.values(), key=lambda x: x.get('wins', 0), reverse=True)[:20]
    text = "🏆 <b>TOP REYTING</b> 🏆\n\n"
    if not sorted_users:
        text += "Statistika yo'q."
    else:
        for i, p in enumerate(sorted_users, 1):
            name = p.get("name") or f"ID:{p['user_id']}"
            text += f"{i}. {name}: {p.get('wins',0)} g'alaba ({p.get('games',0)} o'yin)\n"
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="📅 Haftalik reyting", callback_data="start_weekly")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_stats_cb(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    profile = get_profile(user_id)
    pct = profile.get('wins', 0) / max(profile.get('games', 0), 1) * 100
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"🎮 O'yinlar: <b>{profile.get('games', 0)}</b>\n"
        f"🏆 G'alaba: <b>{profile.get('wins', 0)}</b>\n"
        f"💔 Mag'lubiyat: <b>{profile.get('losses', 0)}</b>\n"
        f"📈 Winrate: <b>{pct:.1f}%</b>"
    )
    kb = make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_help(callback: CallbackQuery, bot: Bot):
    text = (
        "📖 <b>Yordam</b>\n\n"
        "<b>O'yin buyruqlari (guruhda):</b>\n"
        "/mafia — O'yin yaratish\n"
        "/join — Qo'shilish\n"
        "/leave — Chiqish\n"
        "/startgame — Boshlash (admin)\n"
        "/cancel — Bekor qilish (admin)\n"
        "/addbot son — AI bot qo'shish (admin)\n"
        "/status — O'yin holati\n\n"
        "<b>Tun fazasi:</b>\n"
        "• Mafia va Don — kimni o'ldirishni tanlaydi\n"
        "• Komissar — kimni tekshirishni tanlaydi\n"
        "• Doktor — kimni davolashni tanlaydi\n"
        "• Tinch aholi — uxlaydi\n\n"
        "<b>Shaxsiy buyruqlar:</b>\n"
        "/start — Botni ishga tushirish\n"
        "/profile — Profil\n"
        "/hafta — Haftalik reyting\n"
        "/change sum — Olmos → Evro\n"
        "/geroyinfo — Hero ma'lumoti\n"
        "/send @user sum — Olmos yuborish\n"
        "/daily — Kunlik bonus\n\n"
        "<b>Admin buyruqlari:</b>\n"
        "/give @user sum — Olmos berish\n"
        "/giveaway sum — Tasodifiy o'yinchiga olmos\n"
        "/settings — Sozlamalar\n"
        "/set param value — Sozlash (min, night, vote)"
    )
    kb = make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_about(callback: CallbackQuery, bot: Bot):
    text = (
        "ℹ️ <b>Night Killers Bot</b>\n\n"
        "🌙 Versiya: <b>4.0 (aiogram)</b>\n"
        "🎭 Rollar: 8 xil (Mafia, Don, Komissar, Doktor, Tinch aholi, Maniyak, Sherif, Advokat)\n"
        "👥 Maks: 100 o'yinchi\n"
        "💎 Iqtisod: Olmos va Evro\n"
        "🦸 Hero maxsus tizimi\n"
        "📅 Haftalik bonus va sovrinlar\n\n"
        "👨‍💻 Dasturchi: @shohnurrajabov\n"
        "📢 Kanal: https://t.me/+HpBlh_qPFZVkMzhi\n\n"
        "Powered by aiogram 3.x"
    )
    kb = make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_weekly(callback: CallbackQuery, bot: Bot):
    top_players = get_weekly_top(20)
    text = "📅 <b>HAFTA REYTINGI</b> 📅\n\n"
    if not top_players:
        text += "Bu hafta hali hech kim o'ynamadi."
    else:
        for i, p in enumerate(top_players, 1):
            name = p.get("name") or f"ID:{p['user_id']}"
            text += f"{i}. {name}: {p['score']} ball\n"
        text += "\n<b>Sovrinlar:</b>\n"
        text += "🥇 Top 1: 200💎 Olmos\n"
        text += "🥈 Top 2-10: 10💎 Olmos\n"
        text += "🥉 Top 11-20: 4💎 Olmos\n"
    kb = make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_shop(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    profile = get_profile(user.id, user.first_name, user.username or "")
    text = (
        f"🛒 <b>Do'kon</b>\n"
        f"💎 Olmos: <b>{profile.get('olmos', 0)}</b>\n"
        f"💶 Evro: <b>{profile.get('evro', 0)}</b>\n\n"
        f"<b>Maxsus buyumlar:</b>"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="🦸 Hero (90💎)", callback_data="buyhero")],
        [InlineKeyboardButton(text="🎭 Rol sotib olish", callback_data="buyrole")],
        [InlineKeyboardButton(text="💳 To'lov", callback_data="payment")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def show_payment(callback: CallbackQuery, bot: Bot):
    text = (
        f"💳 <b>To'lov</b>\n\n"
        f"Karta: <code>{CARD_NUMBER}</code>\n"
        f"Min: 50 olmos, Max: 10000 olmos\n\n"
        f"To'lov qilish uchun kartaga pul o'tkazing\n"
        f"va chek rasmini dasturchiga yuboring.\n\n"
        f"<b>Narxlar:</b>\n"
        f"50 olmos — 5 000 so'm\n"
        f"100 olmos — 10 000 so'm\n"
        f"500 olmos — 45 000 so'm\n"
        f"1000 olmos — 80 000 so'm\n"
        f"5000 olmos — 350 000 so'm\n"
        f"10000 olmos — 600 000 so'm"
    )
    kb = make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)

async def handle_buy_hero(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    profile = get_profile(user.id, user.first_name, user.username or "")
    if profile.get("hero"):
        await callback.answer("Sizda allaqachon hero bor!", show_alert=True); return
    if profile.get("olmos", 0) < 90:
        await callback.answer("90 olmos kerak!", show_alert=True); return
    profile["olmos"] = profile.get("olmos", 0) - 90
    profile["hero"] = 1
    profile["hero_attack"] = random.randint(5, 15)
    profile["hero_defense"] = random.randint(5, 15)
    save_profile(user.id, profile)
    await callback.answer("🎉 Hero sotib olindi!", show_alert=True)
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id,
        f"🦸 <b>Hero sotib olindi!</b>\n\n⚔ Hujum: +{profile['hero_attack']}\n🛡 Himoya: +{profile['hero_defense']}",
        reply_markup=make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]])
    )

async def handle_buy_role_menu(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    profile = get_profile(user.id, user.first_name, user.username or "")
    text = f"🎭 <b>Rol sotib olish</b>\n💶 Sizda: {profile.get('evro', 0)} evro\n\n"
    btn_rows = []
    for role, price in sorted(ROLE_PRICES.items(), key=lambda x: x[1]):
        btn_rows.append([
            InlineKeyboardButton(
                text=f"{ROLE_ICON.get(role, '')} {ROLE_DISPLAY.get(role, role.value)} - {price}💶",
                callback_data=f"buyrole:{role.value}"
            )
        ])
    btn_rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text,
        reply_markup=make_inline_keyboard(btn_rows))

async def handle_buy_role_confirm(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    role_name = callback.data.split(":", 1)[1]
    try:
        role = Role(role_name)
    except ValueError:
        await callback.answer("Noto'g'ri rol!", show_alert=True); return
    profile = get_profile(user.id, user.first_name, user.username or "")
    price = ROLE_PRICES.get(role, 0)
    if profile.get("evro", 0) < price:
        await callback.answer(f"{price} evro kerak!", show_alert=True); return
    profile["evro"] = profile.get("evro", 0) - price
    profile["bought_role"] = role.value
    save_profile(user.id, profile)
    await callback.answer(f"✅ {ROLE_DISPLAY.get(role, role.value)} sotib olindi!", show_alert=True)
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id,
        f"✅ <b>Rol sotib olindi!</b>\n\n{ROLE_DISPLAY.get(role, role.value)}\n\nEndi o'yin boshlanganda shu rol bilan boshlaysiz!",
        reply_markup=make_inline_keyboard([[InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_menu")]]))

async def handle_join_callback(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Xatolik!", show_alert=True); return
    try:
        target_chat = int(parts[1])
    except ValueError:
        await callback.answer("Xatolik!", show_alert=True); return
    if target_chat not in games:
        await callback.answer("O'yin mavjud emas!", show_alert=True); return
    game = games[target_chat]
    if game.phase != GamePhase.WAITING:
        await callback.answer("O'yin boshlangan. Yangi o'yinchi qo'shila olmaydi.", show_alert=True); return
    if user.id in game.players:
        await callback.answer("Siz allaqachon o'yindasiz!", show_alert=True); return
    if len(game.players) >= MAX_PLAYERS:
        await callback.answer("O'yin to'liq!", show_alert=True); return
    game.players[user.id] = Player(user.id, user.first_name, user.username or "")
    game.log("player_joined_cb", f"{user.id}")
    await update_game_message(game, bot)
    await callback.answer("✅ O'yinga qo'shildingiz!")

async def handle_leave_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Xatolik!", show_alert=True); return
    try:
        target_chat = int(parts[1])
    except ValueError:
        await callback.answer("Xatolik!", show_alert=True); return
    if target_chat not in games:
        await callback.answer("O'yin mavjud emas!", show_alert=True); return
    game = games[target_chat]
    if game.phase != GamePhase.WAITING:
        await callback.answer("Ro'yxatdan o'tish tugagan!", show_alert=True); return
    if user_id not in game.players:
        await callback.answer("Siz o'yinda emassiz!", show_alert=True); return
    del game.players[user_id]
    game.log("player_left_cb", f"{user_id}")
    await update_game_message(game, bot)
    await callback.answer("✅ O'yindan chiqdingiz!")

# ── NIGHT ACTION HANDLERS ──

async def _parse_night_callback(callback: CallbackQuery, bot: Bot, required_role: Role) -> tuple:
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Xatolik!", show_alert=True); return None, None, None
    try:
        chat_id = int(parts[1])
        target_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Xatolik!", show_alert=True); return None, None, None
    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.answer(err, show_alert=True); return None, None, None
    player = game.get_player(callback.from_user.id)
    if player.role != required_role:
        await callback.answer(f"Siz {required_role.value} emassiz!", show_alert=True); return None, None, None
    target = game.get_player(target_id)
    if not target or not target.alive:
        await callback.answer("Bu o'yinchi tirik emas!", show_alert=True); return None, None, None
    return game, target, target_id

async def handle_night_kill(callback: CallbackQuery, bot: Bot):
    result = await _parse_night_callback(callback, bot, Role.MAFIA)
    if result[0] is None:
        return
    game, target, target_id = result
    user_id = callback.from_user.id
    if user_id in game.mafia_votes:
        await callback.answer("Siz allaqachon ovoz berdingiz!", show_alert=True); return
    if target.team == "mafia":
        await callback.answer("Mafia a'zosiga ovoz berolmaysiz!", show_alert=True); return
    game.mafia_votes[user_id] = target_id
    game.action_ready[user_id] = True
    await callback.answer(f"✅ {target.display} ga ovoz berildi!")
    try:
        await callback.message.edit_text(
            f"✅ Ovoz berildi: {target.display}\n\nBoshqa mafia a'zolarining qarorini kuting...",
            parse_mode="HTML"
        )
    except:
        pass

async def handle_night_don(callback: CallbackQuery, bot: Bot):
    result = await _parse_night_callback(callback, bot, Role.DON)
    if result[0] is None:
        return
    game, target, target_id = result
    if game.don_target is not None:
        await callback.answer("Siz allaqachon tanladingiz!", show_alert=True); return
    if target.team == "mafia":
        await callback.answer("Mafia a'zosiga ovoz berolmaysiz!", show_alert=True); return
    game.don_target = target_id
    game.action_ready[callback.from_user.id] = True
    await callback.answer(f"✅ {target.display} ga ovoz berildi!")
    try:
        await callback.message.edit_text(
            f"✅ Siz {target.display} ni tanladingiz!\n\nBoshqa mafia a'zolarining qarorini kuting...",
            parse_mode="HTML"
        )
    except:
        pass

async def handle_night_check(callback: CallbackQuery, bot: Bot):
    result = await _parse_night_callback(callback, bot, Role.KOMISSAR)
    if result[0] is None:
        return
    game, target, target_id = result
    user_id = callback.from_user.id
    if target_id == user_id:
        await callback.answer("O'zingizni tekshira olmaysiz!", show_alert=True); return
    if game.komissar_target is not None:
        await callback.answer("Siz allaqachon tekshirgansiz!", show_alert=True); return
    game.komissar_target = target_id
    game.action_ready[user_id] = True
    await callback.answer(f"✅ {target.display} tekshiriladi!")
    try:
        await callback.message.edit_text(
            f"✅ {target.display} tekshirishga tanlandi.\n\nErtalab natijani bilib olasiz.",
            parse_mode="HTML"
        )
    except:
        pass

async def handle_night_heal(callback: CallbackQuery, bot: Bot):
    result = await _parse_night_callback(callback, bot, Role.DOKTOR)
    if result[0] is None:
        return
    game, target, target_id = result
    if game.doktor_target is not None:
        await callback.answer("Siz allaqachon davoladingiz!", show_alert=True); return
    game.doktor_target = target_id
    game.action_ready[callback.from_user.id] = True
    await callback.answer(f"✅ {target.display} davolanadi!")
    try:
        await callback.message.edit_text(
            f"💊 <b>Davolash qabul qilindi</b>\n\n{target.display} himoya qilinadi.",
            parse_mode="HTML"
        )
    except:
        pass

async def handle_night_maniyak(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Xatolik!", show_alert=True); return
    try:
        chat_id = int(parts[1])
        target_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Xatolik!", show_alert=True); return
    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.answer(err, show_alert=True); return
    player = game.get_player(callback.from_user.id)
    if player.role != Role.MANIYAK:
        await callback.answer("Siz Maniyak emassiz!", show_alert=True); return
    target = game.get_player(target_id)
    if not target or not target.alive:
        await callback.answer("Bu o'yinchi tirik emas!", show_alert=True); return
    if game.maniyak_target is not None:
        await callback.answer("Siz allaqachon nishon tanlagansiz!", show_alert=True); return
    game.maniyak_target = target_id
    game.action_ready[callback.from_user.id] = True
    await callback.answer(f"🪓 {target.display} nishonga olindi!")
    try:
        await callback.message.edit_text(
            f"🪓 <b>Nishon qabul qilindi</b>\n\n{target.display} o'ldiriladi.",
            parse_mode="HTML"
        )
    except:
        pass

# ── DAY VOTE HANDLERS ──

async def handle_day_vote(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("Xatolik!", show_alert=True); return
    try:
        chat_id = int(parts[1])
        target_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Xatolik!", show_alert=True); return
    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.VOTING], require_alive=True)
    if err:
        await callback.answer(err, show_alert=True); return
    player = game.get_player(user_id)
    if player.vote is not None:
        await callback.answer("Siz allaqachon ovoz bergansiz!", show_alert=True); return
    if target_id == user_id:
        await callback.answer("O'zingizga ovoz bera olmaysiz!", show_alert=True); return
    target = game.get_player(target_id)
    if not target or not target.alive:
        await callback.answer("Bu o'yinchi tirik emas!", show_alert=True); return
    player.vote = target_id
    await callback.answer(f"✅ {target.display} ga ovoz berdingiz!")
    try:
        await callback.message.edit_text(
            f"✅ Siz {target.display} ga ovoz berdingiz!\n\nNatijalarni kuting...",
            parse_mode="HTML"
        )
    except:
        pass

async def handle_day_skip(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    if len(parts) < 2:
        await callback.answer("Xatolik!", show_alert=True); return
    try:
        chat_id = int(parts[1])
    except ValueError:
        await callback.answer("Xatolik!", show_alert=True); return
    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.VOTING], require_alive=True)
    if err:
        await callback.answer(err, show_alert=True); return
    player = game.get_player(user_id)
    if player.vote is not None:
        await callback.answer("Siz allaqachon ovoz bergansiz!", show_alert=True); return
    player.vote = -1
    await callback.answer("✅ Ovoz bermadingiz!")
    try:
        await callback.message.edit_text("✅ Ovoz berish o'tkazib yuborildi.", parse_mode="HTML")
    except:
        pass

# ── TEXT COMMANDS ──

async def cmd_profile(message: Message, bot: Bot):
    user = message.from_user
    profile = get_profile(user.id, user.first_name, user.username or "")
    pct = profile.get('wins', 0) / max(profile.get('games', 0), 1) * 100
    text = (
        f"👤 <b>{user.first_name}</b>\n\n"
        f"💎 Olmos: <b>{profile.get('olmos', 0)}</b>\n"
        f"💶 Evro: <b>{profile.get('evro', 0)}</b>\n\n"
        f"🎮 O'yinlar: {profile.get('games', 0)}\n"
        f"🏆 G'alaba: {profile.get('wins', 0)}\n"
        f"💔 Mag'lubiyat: {profile.get('losses', 0)}\n"
        f"📈 Winrate: <b>{pct:.1f}%</b>"
    )
    titles = get_weekly_titles_dict()
    if user.id in titles:
        text += f"\n\n🏅 <b>Unvon:</b> {titles[user.id]['title']}"
    await message.answer(text, parse_mode="HTML")

async def cmd_status(message: Message, bot: Bot):
    chat_id = message.chat.id
    if chat_id not in games:
        await message.answer("Bu chatda o'yin mavjud emas!")
        return
    game = games[chat_id]
    phase_name = PHASE_DISPLAY.get(game.phase, game.phase.value)
    text = (
        f"🎮 <b>O'yin holati</b>\n\n"
        f"📊 Faza: <b>{phase_name}</b>\n"
        f"📅 Kun: <b>{game.day}</b>\n"
        f"👥 O'yinchilar: <b>{len(game.players)}</b>\n"
        f"💀 Tirik: <b>{len(game.alive_players)}</b>\n\n"
    )
    if game.phase not in (GamePhase.WAITING, GamePhase.ENDED):
        mafia_c = len([p for p in game.alive_players if p.team == "mafia"])
        village_c = len([p for p in game.alive_players if p.team == "village"])
        text += f"🔪 Mafia: <b>{mafia_c}</b>\n👤 Village: <b>{village_c}</b>\n"
    await message.answer(text, parse_mode="HTML")

async def cmd_hafta(message: Message, bot: Bot):
    top_players = get_weekly_top(20)
    text = "📅 <b>HAFTA REYTINGI</b> 📅\n\n"
    if not top_players:
        text += "Bu hafta hali hech kim o'ynamadi."
    else:
        for i, p in enumerate(top_players, 1):
            name = p.get("name") or f"ID:{p['user_id']}"
            text += f"{i}. {name}: {p['score']} ball\n"
        text += "\n<b>Sovrinlar:</b>\n"
        text += "🥇 Top 1: 45💎 Olmos\n🥈 Top 2-10: 10💎 Olmos\n🥉 Top 11-20: 4💎 Olmos\n🏅 Top 21-50: 500💰 Evro"
    await message.answer(text, parse_mode="HTML")

async def cmd_change(message: Message, bot: Bot):
    user = message.from_user
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Format: /change summa"); return
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri summa!"); return
    if amount <= 0 or amount > 1_000_000:
        await message.answer("❌ Summa noto'g'ri!"); return
    profile = get_profile(user.id, user.first_name, user.username or "")
    if profile.get("olmos", 0) < amount:
        await message.answer("❌ Yetarli olmos yo'q!"); return
    evro_amt = amount * 1000
    if evro_amt > 1_000_000_000:
        await message.answer("❌ Summa juda katta!"); return
    profile["olmos"] = profile.get("olmos", 0) - amount
    profile["evro"] = profile.get("evro", 0) + evro_amt
    save_profile(user.id, profile)
    await message.answer(f"✅ {amount} olmos → {evro_amt} evro")

async def cmd_geroyinfo(message: Message, bot: Bot):
    user = message.from_user
    profile = get_profile(user.id, user.first_name, user.username or "")
    if profile.get("hero"):
        text = (
            f"🦸 <b>Heroingiz</b>\n\n"
            f"⚔️ Hujum: <b>{profile.get('hero_attack', 0)}</b>\n"
            f"🛡 Himoya: <b>{profile.get('hero_defense', 0)}</b>\n\n"
            f"Hero o'yinda qo'shimcha imkoniyatlar beradi."
        )
    else:
        text = "❌ Sizda hero yo'q. Do'kondan sotib oling! (/start)"
    await message.answer(text, parse_mode="HTML")

async def cmd_send(message: Message, bot: Bot):
    user = message.from_user
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Format: /send @username sum"); return
    target_raw = args[1].lstrip("@")
    try:
        amount = int(args[2])
    except ValueError:
        await message.answer("❌ Noto'g'ri summa!"); return
    if amount <= 0 or amount > 1_000_000_000:
        await message.answer("❌ Summa noto'g'ri!"); return
    profile = get_profile(user.id, user.first_name, user.username or "")
    if profile.get("olmos", 0) < amount:
        await message.answer("❌ Yetarli olmos yo'q!"); return
    target_id = None
    if target_raw.isdigit():
        target_id = int(target_raw)
    else:
        for g in games.values():
            for pid, p in g.players.items():
                if p.username and p.username.lower() == target_raw.lower():
                    target_id = pid; break
            if target_id: break
        if not target_id:
            for pid_str, pdata in get_all_profiles().items():
                if pdata.get("username", "").lower() == target_raw.lower():
                    target_id = int(pid_str); break
    if not target_id:
        await message.answer("❌ Foydalanuvchi topilmadi!"); return
    profile["olmos"] = profile.get("olmos", 0) - amount
    save_profile(user.id, profile)
    tprof = get_profile(target_id)
    tprof["olmos"] = tprof.get("olmos", 0) + amount
    save_profile(target_id, tprof)
    await message.answer(f"✅ {amount}💎 olmos yuborildi!")

async def cmd_daily(message: Message, bot: Bot):
    user = message.from_user
    profile = get_profile(user.id, user.first_name, user.username or "")
    last_daily = profile.get("last_daily")
    if last_daily:
        try:
            last = datetime.fromisoformat(last_daily)
            if datetime.now() - last < timedelta(hours=24):
                remaining = timedelta(hours=24) - (datetime.now() - last)
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                await message.answer(f"⏳ Keyingi bonus {hours}h {mins}m dan keyin!"); return
        except:
            pass
    bonus = random.randint(5, 25)
    profile["olmos"] = profile.get("olmos", 0) + bonus
    profile["last_daily"] = datetime.now().isoformat()
    save_profile(user.id, profile)
    await message.answer(f"🎁 Kunlik bonus: +{bonus}💎 Olmos!")

async def handle_photo(message: Message, bot: Bot):
    user = message.from_user
    if message.chat.type != "private":
        return
    profile = get_profile(user.id, user.first_name, user.username or "")
    caption = message.caption or ""
    text = (
        f"📸 Chek rasmi qabul qilindi!\n\n"
        f"Admin tekshirib, olmoslarni hisobingizga qo'shadi.\n"
        f"Iltimos kuting..."
    )
    await message.answer(text)
    try:
        kb = make_inline_keyboard([
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_pay:{user.id}"),
             InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_pay:{user.id}")]
        ])
        await bot.send_photo(
            ADMIN_ID,
            photo=message.photo[-1].file_id,
            caption=f"💳 To'lov cheki\n\nFoydalanuvchi: {user.full_name}\nID: {user.id}\nUsername: @{user.username or 'none'}\n\nIzoh: {caption}",
            reply_markup=kb
        )
    except Exception as e:
        log.error(f"Failed to forward photo to admin: {e}")

async def cmd_pay(message: Message, bot: Bot):
    text = (
        f"💳 <b>To'lov</b>\n\n"
        f"Karta: <code>{CARD_NUMBER}</code>\n"
        f"Min: 50 olmos, Max: 10000 olmos\n\n"
        f"<b>Narxlar:</b>\n"
        f"50 olmos — 5 000 so'm\n"
        f"100 olmos — 10 000 so'm\n"
        f"500 olmos — 45 000 so'm\n"
        f"1000 olmos — 80 000 so'm\n"
        f"5000 olmos — 350 000 so'm\n"
        f"10000 olmos — 600 000 so'm\n\n"
        f"To'lov qilgach, chek rasmini shu yerga yuboring."
    )
    await message.answer(text, parse_mode="HTML")

# ── ADMIN COMMANDS ──

def admin_only(func):
    @wraps(func)
    async def wrapper(message: Message, bot: Bot, *args, **kwargs):
        user_id = message.from_user.id
        if user_id == ADMIN_ID:
            return await func(message, bot, *args, **kwargs)
        if message.chat.type != "private":
            try:
                member = await bot.get_chat_member(message.chat.id, user_id)
                if member.status in ("creator", "administrator"):
                    return await func(message, bot, *args, **kwargs)
            except:
                pass
        await message.answer("❌ Faqat admin!")
        return
    return wrapper

@admin_only
async def cmd_give(message: Message, bot: Bot):
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Format: /give @user sum"); return
    target_raw = args[1].lstrip("@")
    try:
        amount = int(args[2])
    except ValueError:
        await message.answer("❌ Son yozing!"); return
    if amount <= 0 or amount > 100000:
        await message.answer("❌ 1-100000 oralig'ida!"); return
    target_id = None
    if target_raw.isdigit():
        target_id = int(target_raw)
    else:
        for uid, p in get_all_profiles().items():
            if p.get("username", "").lower() == target_raw.lower():
                target_id = uid; break
        if target_id is None:
            await message.answer("❌ Foydalanuvchi topilmadi!"); return
    profile = get_profile(target_id)
    profile["olmos"] = profile.get("olmos", 0) + amount
    save_profile(target_id, profile)
    await message.answer(f"✅ {amount}💎 olmos berildi (ID: {target_id})")
    try:
        await bot.send_message(target_id, f"🎁 Sizga {amount}💎 olmos berildi!")
    except:
        pass
    profile = get_profile(target_id)
    profile["olmos"] = profile.get("olmos", 0) + amount
    save_profile(target_id, profile)
    await message.answer(f"✅ {amount}💎 olmos berildi (ID: {target_id})")
    try:
        await bot.send_message(target_id, f"🎁 Sizga {amount}💎 olmos berildi!")
    except:
        pass

@admin_only
async def cmd_giveaway(message: Message, bot: Bot):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Format: /giveaway sum"); return
    try:
        amount = int(args[1])
    except ValueError:
        return
    if amount <= 0 or amount > 1_000_000:
        return
    alive_players = [p for g in games.values() for p in g.players.values() if p.alive]
    if not alive_players:
        await message.answer("O'yinchilar yo'q!"); return
    winner = random.choice(alive_players)
    profile = get_profile(winner.user_id, winner.name, winner.username or "")
    profile["olmos"] = profile.get("olmos", 0) + amount
    save_profile(winner.user_id, profile)
    await message.answer(f"🎉 Giveaway! {winner.display} {amount} olmos yutdi!")

@admin_only
async def cmd_settings(message: Message, bot: Bot):
    chat_id = message.chat.id
    min_p = get_chat_setting(chat_id, "min_players", MIN_PLAYERS)
    night_t = get_chat_setting(chat_id, "night_time", NIGHT_TIME)
    vote_t = get_chat_setting(chat_id, "vote_time", DAY_TIME)
    mode = get_chat_setting(chat_id, "mode", "classic")
    text = (
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"👥 Min o'yinchilar: <b>{min_p}</b>\n"
        f"🌙 Tun vaqti: <b>{night_t}s</b>\n"
        f"🗳 Ovoz vaqti: <b>{vote_t}s</b>\n"
        f"🎮 Mode: <b>{mode}</b>\n\n"
        f"/set min 4 — Minimal o'yinchilar\n"
        f"/set night 45 — Tun vaqti (5-120s)\n"
        f"/set vote 45 — Ovoz vaqti (5-120s)"
    )
    await message.answer(text, parse_mode="HTML")

@admin_only
async def cmd_set(message: Message, bot: Bot):
    chat_id = message.chat.id
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Format: /set param qiymat"); return
    param = args[1].lower()
    value = args[2]
    active_game = games.get(chat_id)
    try:
        if param == "min":
            v = int(value)
            if 4 <= v <= MAX_PLAYERS:
                set_chat_setting(chat_id, "min_players", v)
                if active_game and active_game.phase == GamePhase.WAITING:
                    active_game.min_players = v
                await message.answer(f"✅ Min o'yinchilar: {v}")
            else:
                await message.answer(f"❌ 4-{MAX_PLAYERS} oralig'ida!")
        elif param == "night":
            v = int(value)
            if 5 <= v <= 120:
                set_chat_setting(chat_id, "night_time", v)
                if active_game:
                    active_game.night_time = v
                await message.answer(f"✅ Tun vaqti: {v}s")
            else:
                await message.answer("❌ 5-120 oralig'ida!")
        elif param == "vote":
            v = int(value)
            if 5 <= v <= 120:
                set_chat_setting(chat_id, "vote_time", v)
                if active_game:
                    active_game.vote_time = v
                await message.answer(f"✅ Ovoz vaqti: {v}s")
            else:
                await message.answer("❌ 5-120 oralig'ida!")
        else:
            await message.answer("❌ Parametr: min, night, vote")
    except ValueError:
        await message.answer("❌ Noto'g'ri qiymat!")

@admin_only
async def cmd_addbot(message: Message, bot: Bot):
    chat_id = message.chat.id
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!"); return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await message.answer("❌ O'yin boshlangan!"); return
    args = message.text.split()
    available = MAX_PLAYERS - len(game.players)
    count = available
    if len(args) >= 2:
        try:
            count = int(args[1])
        except ValueError:
            await message.answer("Son yozing! Masalan: /addbot 5"); return
    if count < 5:
        await message.answer("Kamida 5 ta bot!"); return
    if count > 30:
        await message.answer("Ko'pi bilan 30 ta bot!"); return
    if count > available:
        await message.answer(f"Ko'pi bilan {available} ta bot!"); return
    added = 0
    for i in range(count):
        bid = -(len(game.players) + i + 1)
        bname = BOT_NAMES[(len(game.players) + i) % len(BOT_NAMES)]
        existing_names = [p.name for p in game.players.values()]
        if bname in existing_names:
            bname += str(len(game.players) + i)
        game.players[bid] = Player(bid, bname, is_bot=True)
        added += 1
    game.log("bots_added", f"{added} bots")
    await message.answer(f"✅ {added} ta AI bot qo'shildi! Jami: {len(game.players)}/{MAX_PLAYERS}")
    await update_game_message(game, bot)

# ── WEEKLY SYSTEM ──

async def distribute_weekly_prizes(bot: Bot):
    week_num = datetime.now().isocalendar()[1]
    previous_week = week_num - 1 if week_num > 1 else 52
    top_players = get_weekly_top(2)
    if len(top_players) >= 1:
        top1 = top_players[0]
        save_weekly_title(top1["user_id"], "Don Corleone", previous_week)
        profile = get_profile(top1["user_id"])
        profile["olmos"] = profile.get("olmos", 0) + 200
        save_profile(top1["user_id"], profile)
        try:
            await bot.send_message(top1["user_id"],
                f"🏆 <b>Tabriklaymiz!</b>\n\nSiz haftaning eng yaxshi o'yinchisi bo'ldingiz!\n👑 Unvon: <b>\"Don Corleone\"</b>\n🎁 Sovrin: 200💎 Olmos",
                parse_mode="HTML")
        except: pass
    if len(top_players) >= 2:
        top2 = top_players[1]
        save_weekly_title(top2["user_id"], "Soyadagi Strateg", previous_week)
        profile = get_profile(top2["user_id"])
        profile["olmos"] = profile.get("olmos", 0) + 100
        save_profile(top2["user_id"], profile)
        try:
            await bot.send_message(top2["user_id"],
                f"🏆 <b>Tabriklaymiz!</b>\n\nSiz haftaning 2-o'yinchisi bo'ldingiz!\n🎯 Unvon: <b>\"Soyadagi Strateg\"</b>\n🎁 Sovrin: 100💎 Olmos",
                parse_mode="HTML")
        except: pass

async def weekly_check_job(bot: Bot):
    last_week = 0
    while True:
        try:
            current_week = datetime.now().isocalendar()[1]
            if current_week != last_week:
                if last_week != 0:
                    await distribute_weekly_prizes(bot)
                last_week = current_week
        except Exception as e:
            log.error(f"Weekly check error: {e}")
        await asyncio.sleep(3600)

# ── BOT SETUP ──

async def global_error_handler(event: ErrorEvent):
    log.error(f"Global error: {event.exception}", exc_info=True)
    try:
        if event.message:
            await event.message.answer("⚠️ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.")
        elif event.callback:
            await event.callback.answer("⚠️ Xatolik yuz berdi.", show_alert=True)
    except Exception:
        pass

async def shutdown_bot():
    log.info("Saving active games before shutdown...")
    for game in games.values():
        save_active_game(game)
    log.info("Bot to'xtatildi.")

async def restore_active_games(bot: Bot):
    restored = load_active_games()
    if restored:
        log.info(f"Restoring {len(restored)} active games from DB...")
    for chat_id, game in restored.items():
        games[chat_id] = game
        try:
            if game.phase != GamePhase.ENDED:
                msg_text = "🔄 Bot qayta ishga tushdi. O'yin davom etmoqda..."
                await bot.send_message(chat_id, msg_text)
                await continue_game(bot, chat_id)
        except Exception as e:
            log.error(f"Failed to restore game {chat_id}: {e}")
            delete_active_game(chat_id)
            if chat_id in games:
                del games[chat_id]

async def on_startup():
    await restore_active_games(bot_instance)

async def setup_bot():
    global bot_instance, dp_instance
    init_db()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    bot_instance = bot
    dp_instance = dp

    dp.startup.register(on_startup)
    dp.shutdown.register(shutdown_bot)
    dp.errors.register(global_error_handler)

    # Message handlers
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_mafia, Command("mafia"))
    dp.message.register(cmd_join, Command("join"))
    dp.message.register(cmd_leave, Command("leave"))
    dp.message.register(cmd_startgame, Command("startgame"))
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(cmd_give, Command("give"))
    dp.message.register(cmd_settings, Command("settings"))
    dp.message.register(cmd_set, Command("set"))
    dp.message.register(cmd_profile, Command("profile"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_hafta, Command("hafta"))
    dp.message.register(cmd_change, Command("change"))
    dp.message.register(cmd_geroyinfo, Command("geroyinfo"))
    dp.message.register(cmd_giveaway, Command("giveaway"))
    dp.message.register(cmd_send, Command("send"))
    dp.message.register(cmd_addbot, Command("addbot"))
    dp.message.register(cmd_daily, Command("daily"))
    dp.message.register(cmd_pay, Command("pay"))
    dp.message.register(handle_photo, F.photo)

    # Callback handler
    dp.callback_query.register(handle_callback)

    # Weekly check
    asyncio.create_task(weekly_check_job(bot))

    log.info("Bot ishga tushdi!")
    log.info(f"Admin ID: {ADMIN_ID}")
    log.info("Bot polling started (processing pending updates)")
    await dp.start_polling(bot, skip_updates=False)

def main():
    try:
        asyncio.run(setup_bot())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi.")
    except Exception as e:
        log.critical(f"Bot crashed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
