"""Night Killers - Mafia Bot v6.0"""

__version__ = "6.0.0"

from .config import TOKEN, ADMIN_ID, CARD_NUMBER, MAX_PLAYERS, MIN_PLAYERS, NIGHT_TIME, DAY_TIME, BOT_NAMES
from .models import MafiaGame, Player, GamePhase, games, find_game, ghosts
from .db import init_db, get_profile
from .economy import buy_role, claim_daily, get_shop_text, add_olmos, spend_olmos, dist_weekly_prizes
from .roles import Role, ROLE_ICON, ROLE_DISPLAY, ROLE_DESC, ROLE_TEAM, ROLE_PRICES, IS_NIGHT_ACTIVE, distribute_roles, MODE_ROLES, TOWN_ROLES, MAFIA_ROLES, NEUTRAL_ROLES
from .utils import atomic_write, safe_json_load
from .handlers.commands import check_flood, cooldown, chat_cooldown
from .game_engine import start_night_phase, end_night_phase, make_inline_keyboard, check_winner as check_win
from .db import load_active_games as load_profiles, get_all_profiles as flush_profiles

# Compatibility shims for old monolith API
BOT_DISCUSSIONS = {}
pending_checks = {}
confirmed_payments = set()
pending_payments = {}  # legacy dict, not used in new code

__all__ = [
    "TOKEN", "ADMIN_ID", "CARD_NUMBER", "MAX_PLAYERS", "MIN_PLAYERS", "NIGHT_TIME", "DAY_TIME", "BOT_NAMES",
    "MafiaGame", "Player", "GamePhase", "games", "find_game", "ghosts",
    "init_db", "get_profile", "add_olmos", "spend_olmos", "dist_weekly_prizes",
    "buy_role", "claim_daily", "get_shop_text",
    "Role", "ROLE_ICON", "ROLE_DISPLAY", "ROLE_DESC", "ROLE_TEAM", "ROLE_PRICES", "IS_NIGHT_ACTIVE",
    "distribute_roles", "MODE_ROLES", "TOWN_ROLES", "MAFIA_ROLES", "NEUTRAL_ROLES",
    "atomic_write", "safe_json_load",
    "check_flood", "cooldown", "chat_cooldown",
    "start_night_phase", "end_night_phase", "make_inline_keyboard",
]
