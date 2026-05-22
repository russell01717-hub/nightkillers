import sys
sys.path.insert(0, r"D:\pylibs")
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

import os, random, logging, asyncio, json, time
from typing import Dict, Optional

TOKEN = os.getenv("BOT_TOKEN", "8388604050:AAFLH3sa6kIbg3YuuiLGMp1VBJT0JT2X9vg")
MAX_PLAYERS = 40
DEFAULT_NIGHT = 30
DEFAULT_VOTE = 30
NIGHT_GIF = "BQACAgIAAxkBAAOoag8GAhuRN1n13dquB5-1trg6dVYAApOiAAKZ6IFIO8rY5Yz9VEU7BA"
DAY_GIF = "BQACAgIAAxkBAAOpag8GBuyutTcDWHvrj17Rfu7NIBwAApSiAAKZ6IFIkFcNCmuX2Wg7BA"
STATS_FILE = os.path.join(os.path.dirname(__file__), "stats.json")
PROFILES_FILE = os.path.join(os.path.dirname(__file__), "profiles.json")
CARD_NUMBER = "4073-4200-7154-7032"
ADMIN_ID = 7820231987

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
games: Dict[int, "MafiaGame"] = {}
user_game: Dict[int, int] = {}
ghosts: Dict[int, set] = {}
settings_chats: Dict[int, dict] = {}
pending_checks: Dict[int, dict] = {}
GAME_MODES = {"classic": "Classic", "full": "Full"}

def load_profiles():
    try:
        with open(PROFILES_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except:
        return {}
    changed = False
    for k, v in d.items():
        if "items" not in v:
            v["items"] = {}
            changed = True
        for it in ["shield", "kill_protect", "vote_protect", "rifle", "mask", "fake_doc"]:
            if it in v["items"] and isinstance(v["items"][it], int):
                v["items"][it] = {"count": v["items"][it], "active": True}
                changed = True
            if it not in v["items"]:
                v["items"][it] = {"count": 0, "active": True}
                changed = True
        for fld in ["hero", "hero_attack", "hero_defense"]:
            if fld not in v:
                v[fld] = (False if fld == "hero" else 0)
                changed = True
        for fld in ["dollars", "olmos", "evro", "games", "wins", "losses"]:
            if fld not in v:
                v[fld] = 0
                changed = True
        if "bought_role" not in v:
            v["bought_role"] = None
            changed = True
    if changed:
        save_profiles(d)
    return d


def save_profiles(data):
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_profile(uid, name=None):
    d = load_profiles()
    k = str(uid)
    if k not in d:
        d[k] = {
            "name": name or str(uid), "dollars": 0, "olmos": 0, "evro": 0,
            "items": {it: {"count": 0, "active": True} for it in ["shield", "kill_protect", "vote_protect", "rifle", "mask", "fake_doc"]},
            "games": 0, "wins": 0, "losses": 0, "bought_role": None,
            "hero": False, "hero_attack": 0, "hero_defense": 0,
        }
        save_profiles(d)
    elif name and d[k]["name"] == str(uid):
        d[k]["name"] = name
        save_profiles(d)
    return d[k]


def save_profile(uid, data):
    d = load_profiles()
    d[str(uid)] = data
    save_profiles(d)


def has_item(uid, item):
    d = load_profiles()
    k = str(uid)
    return k in d and d[k].get("items", {}).get(item, {}).get("count", 0) > 0 and d[k]["items"].get(item, {}).get("active", False)


def remove_item(uid, item, count=1):
    d = load_profiles()
    k = str(uid)
    if k in d and d[k].get("items", {}).get(item, {}).get("count", 0) >= count:
        d[k]["items"][item]["count"] -= count
        save_profiles(d)
        return True
    return False


def add_item(uid, item, count=1):
    d = load_profiles()
    k = str(uid)
    if k in d:
        if item not in d[k]["items"]:
            d[k]["items"][item] = {"count": 0, "active": True}
        d[k]["items"][item]["count"] += count
        save_profiles(d)


def toggle_item(uid, item):
    d = load_profiles()
    k = str(uid)
    if k in d and item in d[k]["items"]:
        d[k]["items"][item]["active"] = not d[k]["items"][item]["active"]
        save_profiles(d)
        return d[k]["items"][item]["active"]
    return False


def add_olmos(uid, amount):
    d = load_profiles()
    k = str(uid)
    if k in d:
        d[k]["olmos"] = d[k].get("olmos", 0) + amount
        save_profiles(d)


def spend_olmos(uid, amount):
    d = load_profiles()
    k = str(uid)
    if k in d and d[k].get("olmos", 0) >= amount:
        d[k]["olmos"] -= amount
        save_profiles(d)
        return True
    return False


async def is_admin(chat, user_id, context):
    try:
        m = await context.bot.get_chat_member(chat.id, user_id)
        return m.status in ("administrator", "creator")
    except:
        return False


def get_set(chat_id):
    if chat_id not in settings_chats:
        settings_chats[chat_id] = {"min": 1, "night": DEFAULT_NIGHT, "vote": DEFAULT_VOTE, "mode": "classic"}
    return settings_chats[chat_id]


class Player:
    def __init__(self, user_id, first_name, username=None):
        self.user_id = user_id
        self.first_name = first_name
        self.username = username
        self.role = None
        self.alive = True
        self.lover = None
        self.defended = False
        self.guard_target = None
        self.blocked = False
        self.team = "village"
        self.actions_used = {}
        self.hero = False

    @property
    def display(self):
        return f"@{self.username}" if self.username else self.first_name

    @property
    def name(self):
        return self.display


class MafiaGame:
    def __init__(self, chat_id, mode="classic"):
        self.chat_id = chat_id
        self.mode = mode
        self.players: Dict[int, Player] = {}
        self.phase = "registration"
        self.day = 0
        self.votes: Dict[int, int] = {}
        self.actions = {}
        self.used_actions = {}
        self.action_ready = {}
        self.maniac_present = False
        self.mine_target = None
        self.sniper_targets = {}
        self.watch_results = {}
        self.chemist_target = None
        self.fan_targets = {}
        self.chameleon_targets = {}
        self.drunk_targets = {}
        self.teacher_targets = {}
        self.seller_targets = {}
        self.blocked_players = set()
        self.rifle_uses: Dict[int, int] = {}

    @property
    def alive_players(self):
        return [p for p in self.players.values() if p.alive]

    @property
    def mafia_alive(self):
        return [p for p in self.players.values() if p.role in ("Don", "Mafia") and p.alive]

    def get_player(self, uid):
        return self.players.get(uid)

    def alive_count(self):
        return len(self.alive_players)


ROLE_ICON = {
    "Don": chr(0x1F974), "Mafia": chr(0x1F974) + chr(0x1F3FC),
    "Shifokor": chr(0x1F469) + chr(0x200D) + chr(0x2695) + chr(0xFE0F),
    "Komissar": chr(0x1F575) + chr(0xFE0F), "Manyak": chr(0x1F5E1) + chr(0xFE0F),
    "Daydi": chr(0x1F9D9), "Advokat": chr(0x1F9D1) + chr(0x200D) + chr(0x2696) + chr(0xFE0F),
    "Bodyguard": chr(0x1F6E1) + chr(0xFE0F), "Oshiq": chr(0x1F491),
    "Kamikaze": chr(0x1F4A3), "Tinch aholi": chr(0x1F9CD),
    "Mashuqa": chr(0x1F483), "Serjant": chr(0x1F46E) + chr(0x200D) + chr(0x2642) + chr(0xFE0F),
    "Buqalamun": chr(0x1F98E), "Omadli": chr(0x1F91E), "Aferist": chr(0x1F939),
    "Sehrgar": chr(0x1F9D9) + chr(0x200D) + chr(0x2642) + chr(0xFE0F),
    "Suidsid": chr(0x1F9CC), "Don xotini": chr(0x1F470) + chr(0x200D) + chr(0x2640) + chr(0xFE0F),
    "Kimyogar": chr(0x1F468) + chr(0x200D) + chr(0x1F52C), "Sotuvchi": chr(0x1F381),
    "Tentak": chr(0x1F472), "Oqituvchi": chr(0x1F468) + chr(0x200D) + chr(0x1F3EB),
    "Muxlis": chr(0x1F52E), "Minior": chr(0x2620) + chr(0xFE0F),
    "Mergan": chr(0x1F3A4), "Majnun": chr(0x1F57A), "Ubica": chr(0x1F978),
}

ROLE_DISPLAY = {
    "Don": "Don", "Mafia": "Mafiya", "Shifokor": "Shifokor", "Komissar": "Komissar",
    "Manyak": "Manyak", "Daydi": "Daydi", "Advokat": "Advokat", "Bodyguard": "Tansoqchi",
    "Oshiq": "Oshiq", "Kamikaze": "Kamikaze", "Tinch aholi": "Tinch aholi",
    "Mashuqa": "Mashuqa", "Serjant": "Serjant", "Buqalamun": "Buqalamun",
    "Omadli": "Omadli", "Aferist": "Aferist", "Sehrgar": "Sehrgar",
    "Suidsid": "Suitsid", "Don xotini": "Donning xotini", "Kimyogar": "Kimyogar",
    "Sotuvchi": "Sotuvchi", "Tentak": "Tentak", "Oqituvchi": "Oqituvchi",
    "Muxlis": "Muxlis", "Minior": "Minior", "Mergan": "Mergan (Snayper)",
    "Majnun": "Majnun", "Ubica": "Ubica",
}

MODE_ROLES = {
    "classic": ["Don", "Mafia", "Shifokor", "Komissar", "Manyak", "Advokat", "Daydi", "Kamikaze", "Mashuqa", "Serjant", "Suidsid", "Tinch aholi"],
    "full": ["Don", "Mafia", "Shifokor", "Daydi", "Komissar", "Kamikaze", "Mashuqa", "Serjant", "Aferist", "Tentak", "Advokat", "Don xotini", "Kimyogar", "Sotuvchi", "Suidsid", "Muxlis", "Manyak", "Minior", "Mergan", "Majnun", "Buqalamun", "Oqituvchi", "Tinch aholi"],
}

print("Module loaded OK")
