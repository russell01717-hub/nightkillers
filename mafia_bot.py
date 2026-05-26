import os, sys, random, logging, asyncio, json, time, tempfile, shutil
from typing import Dict, Optional
try:
    sys.path.insert(0, r"D:\pylibs")
except:
    pass
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN", "8388604050:AAFLH3sa6kIbg3YuuiLGMp1VBJT0JT2X9vg")
MAX_PLAYERS = 40
DEFAULT_NIGHT = 45
DEFAULT_VOTE = 45
NIGHT_GIF = "BQACAgIAAxkBAAOoag8GAhuRN1n13dquB5-1trg6dVYAApOiAAKZ6IFIO8rY5Yz9VEU7BA"
DAY_GIF = "BQACAgIAAxkBAAOpag8GBuyutTcDWHvrj17Rfu7NIBwAApSiAAKZ6IFIkFcNCmuX2Wg7BA"
STATS_FILE = os.path.join(os.path.dirname(__file__), "stats.json")
PROFILES_FILE = os.path.join(os.path.dirname(__file__), "profiles.json")
WEEKLY_FILE = os.path.join(os.path.dirname(__file__), "weekly.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
GAME_IMAGE = None
CARD_NUMBER = "4073-4200-7154-7032"
ADMIN_ID = 7820231987
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

games: Dict[int, "MafiaGame"] = {}
ghosts: Dict[int, set] = {}
settings_chats: Dict[int, dict] = {}
pending_checks: Dict[int, dict] = {}
night_step: Dict[int, dict] = {}
cooldown: Dict[int, float] = {}
profile_cache: dict = None
profile_cache_dirty = False
GAME_MODES = {"classic": "Classic", "full": "Full"}
awaiting_image: set = set()


def atomic_write(filepath, data):
    tmp = filepath + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        try:
            if os.path.exists(filepath):
                os.replace(tmp, filepath)
            else:
                shutil.move(tmp, filepath)
        except:
            pass
    except:
        pass


def load_profiles():
    global profile_cache
    if profile_cache is not None:
        return profile_cache
    try:
        with open(PROFILES_FILE, encoding="utf-8") as f:
            profile_cache = json.load(f)
    except:
        profile_cache = {}
    changed = False
    for k, v in profile_cache.items():
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
        if "username" not in v:
            v["username"] = ""
            changed = True
    if changed:
        atomic_write(PROFILES_FILE, profile_cache)
    return profile_cache


def save_profiles(data):
    global profile_cache, profile_cache_dirty
    profile_cache = data
    profile_cache_dirty = True


def flush_profiles():
    global profile_cache_dirty
    if profile_cache_dirty and profile_cache is not None:
        atomic_write(PROFILES_FILE, profile_cache)
        profile_cache_dirty = False


def get_profile(uid, name=None, username=None):
    d = load_profiles()
    k = str(uid)
    if k not in d:
        d[k] = {
            "name": name or str(uid), "username": username or "",
            "dollars": 0, "olmos": 0, "evro": 0,
            "items": {it: {"count": 0, "active": True} for it in ["shield", "kill_protect", "vote_protect", "rifle", "mask", "fake_doc"]},
            "games": 0, "wins": 0, "losses": 0, "bought_role": None,
            "hero": False, "hero_attack": 0, "hero_defense": 0,
        }
        save_profiles(d)
    elif name and d[k]["name"] == str(uid):
        d[k]["name"] = name
        d[k]["username"] = username or d[k].get("username", "")
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


def find_game(uid, chat_id=None):
    if chat_id and chat_id in games:
        g = games[chat_id]
        if uid in g.players and g.players[uid].alive:
            return g
    for g in games.values():
        if uid in g.players and g.players[uid].alive:
            return g
    return None


def check_flood(uid):
    now = time.time()
    if uid in cooldown and now - cooldown[uid] < 0.8:
        return True
    cooldown[uid] = now
    return False


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
        self.doc_choice = None
        self.maniac_target = None
        self.advokat_target = None
        self.serjant_choice = None
        self.don_target = None
        self.mafia_targets = {}
        self.muxlis_target = None
        self.majnun_target = None
        self.blocked_players = set()
        self.msg_id = None
        self.game_msg_id = None
        self.start_time = None

    @property
    def alive_players(self):
        return [p for p in self.players.values() if p.alive]

    @property
    def mafia_alive(self):
        return [p for p in self.players.values() if p.role in ("Don", "Mafia") and p.alive]

    def get_player(self, uid):
        return self.players.get(uid)


ROLE_ICON = {
    "Don": "\U0001F974", "Mafia": "\U0001F974\U0001F3FC",
    "Shifokor": "\U0001F469\u200D\u2695\uFE0F",
    "Komissar": "\U0001F575\uFE0F", "Manyak": "\U0001F5E1\uFE0F",
    "Daydi": "\U0001F9D9", "Advokat": "\U0001F9D1\u200D\u2696\uFE0F",
    "Bodyguard": "\U0001F6E1\uFE0F", "Oshiq": "\U0001F491",
    "Kamikaze": "\U0001F4A3", "Tinch aholi": "\U0001F9CD",
    "Mashuqa": "\U0001F483", "Serjant": "\U0001F46E\u200D\u2642\uFE0F",
    "Buqalamun": "\U0001F98E", "Omadli": "\U0001F91E", "Aferist": "\U0001F939",
    "Sehrgar": "\U0001F9D9\u200D\u2642\uFE0F",
    "Suidsid": "\U0001F9CC", "Don xotini": "\U0001F470\u200D\u2640\uFE0F",
    "Kimyogar": "\U0001F468\u200D\u0001F52C", "Sotuvchi": "\U0001F381",
    "Tentak": "\U0001F472", "Oqituvchi": "\U0001F468\u200D\U0001F3EB",
    "Muxlis": "\U0001F52E", "Minior": "\u2620\uFE0F",
    "Mergan": "\U0001F3A4", "Majnun": "\U0001F57A", "Ubica": "\U0001F978",
}
ROLE_DISPLAY = {
    "Don": "Don", "Mafia": "Mafiya", "Shifokor": "Shifokor", "Komissar": "Komissar",
    "Manyak": "Manyak", "Daydi": "Daydi", "Advokat": "Advokat", "Bodyguard": "Tansoqchi",
    "Oshiq": "Oshiq", "Kamikaze": "Kamikaze", "Tinch aholi": "Tinch aholi",
    "Mashuqa": "Mashuqa", "Serjant": "Serjant", "Buqalamun": "Buqalamun",
    "Omadli": "Omadli", "Aferist": "Aferist", "Sehrgar": "Sehrgar",
    "Suidsid": "Suitsid", "Don xotini": "Donning xotini", "Kimyogar": "Kimyogar",
    "Sotuvchi": "Sotuvchi", "Tentak": "Tentak", "Oqituvchi": "O'qituvchi",
    "Muxlis": "Muxlis", "Minior": "Minior", "Mergan": "Mergan (Snayper)",
    "Majnun": "Majnun", "Ubica": "Ubica",
}
MODE_ROLES = {
    "classic": ["Don", "Mafia", "Shifokor", "Komissar", "Manyak", "Advokat", "Daydi", "Kamikaze", "Mashuqa", "Serjant", "Suidsid", "Tinch aholi"],
    "full": ["Don", "Mafia", "Shifokor", "Daydi", "Komissar", "Kamikaze", "Mashuqa", "Serjant", "Aferist", "Tentak", "Advokat", "Don xotini", "Kimyogar", "Sotuvchi", "Suidsid", "Muxlis", "Manyak", "Minior", "Mergan", "Majnun", "Buqalamun", "Oqituvchi", "Oshiq", "Sehrgar", "Omadli", "Ubica", "Tinch aholi"],
}
ROLE_PRICES = {
    "Tinch aholi": 100, "Shifokor": 300, "Daydi": 400, "Komissar": 500,
    "Kamikaze": 350, "Mashuqa": 450, "Serjant": 400, "Oqituvchi": 600,
    "Tentak": 500, "Muxlis": 350, "Advokat": 400, "Don xotini": 550,
    "Kimyogar": 600, "Sotuvchi": 700, "Suidsid": 650, "Manyak": 750,
    "Minior": 700, "Mergan": 800, "Buqalamun": 650, "Majnun": 550,
    "Aferist": 600, "Sehrgar": 900, "Ubica": 1000, "Don": 1200, "Mafia": 800,
    "Oshiq": 500, "Bodyguard": 550, "Omadli": 600,
}
ITEM_PRICES = {"shield": 100, "vote_protect": 150, "fake_doc": 200, "mask": 250, "kill_protect": 300, "rifle": 500}
ITEM_NAMES = {"shield": "Himoya", "kill_protect": "Qotildan himoya", "vote_protect": "Ovoz himoyasi",
              "rifle": "Miltiq", "mask": "Maska", "fake_doc": "Soxta hujjat"}
NIGHT_ATMOSPHERE = {
    "Don": "🤵🏻 Don qurbonini tanladi...",
    "Mafia": "🔫 Mafiya qurbonini tanladi...",
    "Shifokor": "👨‍⚕️ Shifokor tungi navbatchilikga ketdi...",
    "Komissar": "🕵️‍ Komissar Katani pistoletini o'qladi...",
    "Manyak": "🔪 Qotil Butalar orasiga yashirinib oldi...",
    "Daydi": "🚶 Daydi tungi sayohatga chiqdi...",
    "Advokat": "⚖ Advokat himoya nutqini tayyorladi...",
    "Bodyguard": "🛡 Tansoqchi postini egalladi...",
    "Oshiq": "💕 Oshiq sevgilisi haqida o'ylamoqda...",
    "Kamikaze": "💣 Kamikaze portlashga tayyor...",
    "Mashuqa": "💃 Ma'shuqa sevgilisini kutmoqda...",
    "Serjant": "👮 Serjant navbatchilikni boshqarmoqda...",
    "Buqalamun": "🦎 Buqalamun rangini o'zgartirdi...",
    "Omadli": "🍀 Omadli omadiga ishonmoqda...",
    "Aferist": "🎭 Aferist o'z rejasini boshladi...",
    "Sehrgar": "✨ Sehrgar afsun o'qimoqda...",
    "Suidsid": "💔 Suitsid o'z qarorini qildi...",
    "Don xotini": "👸 Donning xotini maxfiy ma'lumot to'plamoqda...",
    "Kimyogar": "☠ Kimyogar zahar tayyorlamoqda...",
    "Sotuvchi": "🔫 Sotuvchi qurolini charxlamoqda...",
    "Tentak": "🐙 Tentak o'z qurbonini kutmoqda...",
    "Oqituvchi": "📚 O'qituvchi darsiga tayyorlanmoqda...",
    "Muxlis": "👁 Muxlis kumirini kuzatmoqda...",
    "Minior": "☄ Minior portlashga tayyor...",
    "Mergan": "🎯 Mergan nishonga olmoqda...",
    "Majnun": "🔗 Majnun o'z sevgisini o'ylamoqda...",
    "Ubica": "💀 Ubica qurbonini kuzatmoqda...",
    "Tinch aholi": "👤 Tinch aholi uyqusida...",
}


def fmt_player(p):
    return f'<a href="tg://user?id={p.user_id}">{p.display}</a>'


async def send_safe(context, chat_id, text=None, photo=None, animation=None, caption=None, reply_markup=None, parse_mode=None):
    try:
        if animation:
            return await context.bot.send_animation(chat_id, animation, caption=caption, parse_mode=parse_mode)
        if photo:
            return await context.bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup)
        if text:
            return await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logging.warning(f"send_safe failed to {chat_id}: {e}")
    return None


async def update_game_msg(context, game):
    if not game.game_msg_id:
        return
    count = len(game.players)
    text = f"Ro'yxatdan o'tish davom etmoqda!\n\nRo'yhatdan o'tganlar:\n\n"
    for i, p in enumerate(game.players.values(), 1):
        text += f"{i}. {p.first_name}\n"
    text += f"\nJami: {count} ta"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ O'yinga qo'shilish", callback_data="joingame")]])
    try:
        await context.bot.edit_message_caption(chat_id=game.chat_id, message_id=game.game_msg_id, caption=text, reply_markup=kb)
    except:
        try:
            await context.bot.edit_message_text(text, chat_id=game.chat_id, message_id=game.game_msg_id, reply_markup=kb)
        except:
            pass


def role_counts(game):
    counts = {}
    for p in game.alive_players:
        counts[p.role] = counts.get(p.role, 0) + 1
    return ", ".join(f"{ROLE_ICON.get(r,'')} {ROLE_DISPLAY.get(r,r)}" + (f" - {c}" if c > 1 else "") for r, c in sorted(counts.items()))


def make_kb_for_game(game, player_ids, action, emoji=None):
    kb = []
    row = []
    for pid in player_ids:
        p = game.get_player(pid)
        prefix = (emoji + " ") if emoji else ""
        name = p.display if p else "?"
        row.append(InlineKeyboardButton(prefix + name, callback_data=f"{action}:{pid}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(kb)


def make_single_kb(buttons):
    kb = [[InlineKeyboardButton(text, callback_data=cb)] for text, cb in buttons]
    return InlineKeyboardMarkup(kb)


def load_stats():
    try:
        with open(STATS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_stats(data):
    atomic_write(STATS_FILE, data)


def load_weekly():
    try:
        with open(WEEKLY_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except:
        return {"week": int(time.time()), "players": {}, "distributed": False}
    now = int(time.time())
    week_sec = 7 * 24 * 3600
    if now - d.get("week", 0) > week_sec and not d.get("distributed", False):
        dist_weekly_prizes(d)
        d["distributed"] = True
        save_weekly(d)
        d = {"week": now, "players": {}, "distributed": False}
        save_weekly(d)
    elif now - d.get("week", 0) > week_sec:
        d = {"week": now, "players": {}, "distributed": False}
        save_weekly(d)
    return d


def save_weekly(data):
    atomic_write(WEEKLY_FILE, data)


def dist_weekly_prizes(w):
    if not w or not w.get("players"):
        return
    sorted_u = sorted(w["players"].items(), key=lambda x: x[1].get("score", 0), reverse=True)[:50]
    for i, (uid_str, data) in enumerate(sorted_u, 1):
        uid = int(uid_str)
        rank = i
        if rank == 1:
            add_olmos(uid, 45)
        elif rank <= 10:
            add_olmos(uid, 10)
        elif rank <= 20:
            add_olmos(uid, 4)
        else:
            prof = get_profile(uid)
            prof["evro"] = prof.get("evro", 0) + 500
            save_profile(uid, prof)


# ────────── COMMANDS ──────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = (f"👋 Assalomu alaykum {u.first_name}! Mafia o'yin botiga xush kelibsiz.\n\n"
            "🌙 Bu yerda siz mafiya a'zosi yoki fuqaro bo'lib o'ynaysiz.\n"
            "Tun zulmatida mafiya qurbon tanlaydi, kunduzi esa ovoz berib mafiyani topasiz.\n\n"
            "Buyruqlar:\n"
            "/mafia - 🎮 O'yin yaratish\n/join - ➕ Qo'shilish\n/leave - ➖ Chiqish\n"
            "/startgame - 🚀 Boshlash (admin)\n/players - 👥 O'yinchilar\n"
            "/vote @user - 🗳 Ovoz berish\n/status - 📊 Holat\n"
            "/money - 💰 Hisob\n/profile - 👤 Profil\n/shop - 🛒 Do'kon\n"
            "/top - 🏆 Top\n/hafta - 📅 Hafta reytingi\n"
            "/help - 📖 Yordam")
    if GAME_IMAGE:
        await send_safe(context, u.id, photo=GAME_IMAGE, caption=text)
    else:
        await update.message.reply_text(text)


async def mafia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        if chat_id in games:
            await update.message.reply_text("Bu chatda allaqachon o'yin bor!")
            return
        game = MafiaGame(chat_id, get_set(chat_id)["mode"])
        games[chat_id] = game
        text = "Ro'yxatdan o'tish davom etmoqda!\n\nRo'yhatdan o'tganlar:\n\n"
        text += "Hali hech kim qo'shilgani yo'q."
        text += f"\n\nJami: 0 ta"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("➕ O'yinga qo'shilish", callback_data="joingame")]])
        if GAME_IMAGE:
            msg = await send_safe(context, chat_id, photo=GAME_IMAGE, caption=text, reply_markup=kb)
        else:
            msg = await update.message.reply_text(text, reply_markup=kb)
        game.game_msg_id = msg.message_id
    except Exception as e:
        logging.error(f"mafia: {e}")
        await update.message.reply_text("Xatolik yuz berdi")


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if check_flood(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in games or games[chat_id].phase != "registration":
        await update.message.reply_text("Hozir qo'shilish mumkin emas!")
        return
    game = games[chat_id]
    if user.id in game.players:
        await update.message.reply_text("Siz allaqachon o'yindasiz!")
        return
    if len(game.players) >= MAX_PLAYERS:
        await update.message.reply_text("O'yin to'liq!")
        return
    game.players[user.id] = Player(user.id, user.first_name, user.username)
    if chat_id not in ghosts:
        ghosts[chat_id] = set()
    ghosts[chat_id].add(user.id)
    await update_game_msg(context, game)


async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if check_flood(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in games or games[chat_id].phase != "registration":
        await update.message.reply_text("Hozir chiqib bo'lmaydi!")
        return
    game = games[chat_id]
    if user.id not in game.players:
        await update.message.reply_text("Siz o'yinda emassiz!")
        return
    del game.players[user.id]
    if chat_id in ghosts and user.id in ghosts[chat_id]:
        ghosts[chat_id].discard(user.id)
    text = f"O'yinchilar ({len(game.players)}/{MAX_PLAYERS}):\n"
    for i, p in enumerate(game.players.values(), 1):
        text += f"{i}. {p.display}\n"
    await update.message.reply_text(text)
    if not game.players:
        del games[chat_id]
        ghosts.pop(chat_id, None)
        await update.message.reply_text("Hech kim qolmadi, o'yin bekor qilindi.")


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("O'yin yo'q!")
        return
    game = games[chat_id]
    if not game.players:
        await update.message.reply_text("O'yinchilar yo'q!")
        return
    text = f"O'yinchilar ({len(game.alive_players)}/{MAX_PLAYERS}):\n"
    for i, p in enumerate(game.alive_players, 1):
        rs = f" - {ROLE_ICON.get(p.role,'')} {ROLE_DISPLAY.get(p.role,p.role)}" if p.role else ""
        text += f"{i}. {p.display}{rs}\n"
    await update.message.reply_text(text, parse_mode="HTML")


async def money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prof = get_profile(user.id, user.first_name, user.username)
    await update.message.reply_text(f"💰 Hisob:\n💎 Olmos: {prof['olmos']}\n💵 Dollar: {prof['dollars']}\n💶 Evro: {prof['evro']}")


async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    parts = text.split()
    if len(parts) < 3:
        await update.message.reply_text("Format: /send @username sum")
        return
    target_name = parts[1].strip("@")
    try:
        amount = int(parts[2])
    except:
        await update.message.reply_text("Noto'g'ri summa!")
        return
    if amount <= 0:
        await update.message.reply_text("Summa musbat!")
        return
    prof = get_profile(user.id, user.first_name, user.username)
    if prof["dollars"] < amount:
        await update.message.reply_text("Yetarli dollar yo'q!")
        return
    target_id = None
    for g in games.values():
        for pid, p in g.players.items():
            if p.username and p.username.lower() == target_name.lower():
                target_id = pid
                break
        if target_id:
            break
    if not target_id:
        for pid_str, pdata in load_profiles().items():
            if pdata.get("name", "").lower().replace("@", "") == target_name.lower():
                target_id = int(pid_str)
                break
            if pdata.get("username", "").lower().replace("@", "") == target_name.lower():
                target_id = int(pid_str)
                break
    if not target_id:
        await update.message.reply_text("Foydalanuvchi topilmadi!")
        return
    prof["dollars"] -= amount
    save_profile(user.id, prof)
    tprof = get_profile(target_id)
    tprof["dollars"] = tprof.get("dollars", 0) + amount
    save_profile(target_id, tprof)
    await update.message.reply_text(f"${amount} yuborildi!")


async def give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Faqat admin!")
        return
    text = update.message.text
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text("Format: /give @user sum yoki reply /give sum")
        return
    if update.message.reply_to_message and len(parts) == 2:
        target_id = update.message.reply_to_message.from_user.id
        try:
            amount = int(parts[1])
        except:
            await update.message.reply_text("Noto'g'ri summa!")
            return
        if amount <= 0:
            return
        add_olmos(target_id, amount)
        await update.message.reply_text(f"{amount} olmos berildi!")
        return
    if len(parts) < 3:
        await update.message.reply_text("Format: /give @user sum yoki reply /give sum")
        return
    target_name = parts[1].strip("@")
    try:
        amount = int(parts[2])
    except:
        await update.message.reply_text("Noto'g'ri summa!")
        return
    if amount <= 0:
        return
    target_id = None
    for pid_str, pdata in load_profiles().items():
        if pdata.get("name", "").lower().replace("@", "") == target_name.lower():
            target_id = int(pid_str)
            break
        if pdata.get("username", "").lower().replace("@", "") == target_name.lower():
            target_id = int(pid_str)
            break
    if not target_id:
        await update.message.reply_text("Topilmadi!")
        return
    add_olmos(target_id, amount)
    await update.message.reply_text(f"{amount} olmos berildi!")


async def gsend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Faqat admin!")
        return
    text = update.message.text
    parts = text.split()
    if len(parts) < 4:
        await update.message.reply_text("Format: /gsend @username miqdor tur")
        return
    target_name = parts[1].strip("@")
    try:
        amount = int(parts[2])
    except:
        await update.message.reply_text("Noto'g'ri summa!")
        return
    currency = parts[3].lower()
    if currency not in ("dollar", "olmos", "evro"):
        await update.message.reply_text("dollar/olmos/evro")
        return
    target_id = None
    for g in games.values():
        for pid, p in g.players.items():
            if p.username and p.username.lower() == target_name.lower():
                target_id = pid
                break
        if target_id:
            break
    if not target_id:
        for pid_str, pdata in load_profiles().items():
            if pdata.get("name", "").lower().replace("@", "") == target_name.lower():
                target_id = int(pid_str)
                break
    if not target_id:
        await update.message.reply_text("Topilmadi!")
        return
    prof = get_profile(target_id)
    prof[currency] = prof.get(currency, 0) + amount
    save_profile(target_id, prof)
    await update.message.reply_text(f"{amount} {currency} berildi!")


async def change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text("Format: /change summa")
        return
    try:
        amount = int(parts[1])
    except:
        await update.message.reply_text("Noto'g'ri summa!")
        return
    if amount <= 0:
        await update.message.reply_text("Summa musbat!")
        return
    prof = get_profile(user.id, user.first_name, user.username)
    if prof["olmos"] < amount:
        await update.message.reply_text("Yetarli olmos yo'q!")
        return
    prof["olmos"] -= amount
    prof["evro"] = prof.get("evro", 0) + amount
    save_profile(user.id, prof)
    await update.message.reply_text(f"{amount} olmos -> {amount} evro")


async def giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    args = context.args
    if len(args) < 1:
        await update.message.reply_text("Format: /giveaway sum")
        return
    try:
        amount = int(args[0])
    except:
        return
    if amount <= 0:
        return
    plist = [p for g in games.values() for p in g.players.values() if p.alive]
    if not plist:
        await update.message.reply_text("O'yinchilar yo'q!")
        return
    winner = random.choice(plist)
    add_olmos(winner.user_id, amount)
    await update.message.reply_text(f"🎉 Giveaway! {winner.display} {amount} olmos yutdi!")


async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prof = get_profile(user.id, user.first_name, user.username)
    kb = [[InlineKeyboardButton(f"{n} - {ITEM_PRICES[i]} olmos", callback_data=f"buy:{i}")] for i, n in ITEM_NAMES.items()]
    await update.message.reply_text(f"🛒 Do'kon\n💎 Olmos: {prof['olmos']}", reply_markup=InlineKeyboardMarkup(kb))


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prof = get_profile(user.id, user.first_name, user.username)
    items_str = ""
    for item_id, item_name in ITEM_NAMES.items():
        item_data = prof["items"].get(item_id, {"count": 0, "active": True})
        items_str += f"{'✅' if item_data['active'] else '❌'} {item_name}: {item_data['count']}\n"
    hero_str = f"✅ Hujum: {prof.get('hero_attack',0)}, Himoya: {prof.get('hero_defense',0)}" if prof.get("hero") else "❌ Sotib olinmagan"
    role_str = prof.get("bought_role") or "Yo'q"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Hero sotib olish (90 olmos)", callback_data="buyhero")] if not prof.get("hero") else [],
        [InlineKeyboardButton("Rol sotib olish", callback_data="buyrole")],
        [InlineKeyboardButton("To'lov", callback_data="payment")],
    ])
    await update.message.reply_text(
        f"👤 {user.first_name}\n💎 Olmos: {prof['olmos']} | 💵 Dollar: {prof['dollars']} | 💶 Evro: {prof.get('evro',0)}\n\n"
        f"📦 Itemlar:\n{items_str}🦸 Hero: {hero_str}\n🎭 Rol: {role_str}\n"
        f"O'yinlar: {prof.get('games',0)} | G'alaba: {prof.get('wins',0)} | Mag'lubiyat: {prof.get('losses',0)}",
        reply_markup=kb
    )


async def geroyinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🦸 Qahramon (Hero)\n\nNarxi: 90 olmos\nImkoniyat: Hujum va himoya kuchini oshiradi\nSotib olish uchun /profile -> Hero sotib olish")


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if not await is_admin(update.effective_chat, user.id, context):
        await update.message.reply_text("Faqat admin!")
        return
    if chat_id not in games or games[chat_id].phase != "registration":
        await update.message.reply_text("O'yin mavjud emas!")
        return
    game = games[chat_id]
    if len(game.players) < get_set(chat_id)["min"]:
        await update.message.reply_text(f"Kamida {get_set(chat_id)['min']} o'yinchi kerak!")
        return
    await start_gameplay(update, context, game)


async def start_gameplay(update, context, game):
    chat_id = game.chat_id
    players = list(game.players.values())
    count = len(players)
    mode = game.mode
    role_pool = MODE_ROLES.get(mode, MODE_ROLES["classic"][:])
    base_roles = [r for r in role_pool if r != "Tinch aholi"]
    if count <= 6:
        assigned = base_roles[:count]
    else:
        assigned = base_roles[:]
        while len(assigned) < count:
            assigned.append("Tinch aholi")
        assigned = assigned[:count]
    random.shuffle(assigned)
    for p, role in zip(players, assigned):
        p.role = role
        if role in ("Don", "Mafia"):
            p.team = "mafia"
        elif role in ("Manyak", "Ubica", "Zombi"):
            p.team = "neutral"
        else:
            p.team = "village"
    game.day = 0
    game.phase = "night"
    game.start_time = time.time()
    await send_safe(context, chat_id, animation=NIGHT_GIF, caption=f"🌙 *{count} o'yinchi bilan o'yin boshlandi!*\n1-tun boshlanishi...", parse_mode="Markdown")
    for p in players:
        try:
            await context.bot.send_message(p.user_id, f"Sizning rolingiz: {ROLE_ICON.get(p.role,'')} {ROLE_DISPLAY.get(p.role,p.role)}\n\n{ROLE_HELP.get(p.role,'')}")
        except:
            pass
    await asyncio.sleep(3)
    await night_phase(context, game)


ROLE_HELP = {
    "Don": "Don (Mafiya boshlig'i). Tunda mafiyani boshqarib, 🩸 kimni o'ldirishni tanlaysiz.",
    "Mafia": "Mafiya a'zosi. Tunda Don bilan birga 🩸 odam o'ldirasiz.",
    "Shifokor": "Shifokor. Tunda bir o'yinchini davolaysiz 💊",
    "Komissar": "Komissar. Tunda 🔍 tekshirasiz yoki 🗡 o'ldirasiz.",
    "Manyak": "Manyak. Tunda bir o'yinchini o'ldirasiz 🗡",
    "Daydi": "Daydi. Tunda bir o'yinchiga tashrif buyurasiz 👤",
    "Advokat": "Advokat. Tunda bir o'yinchini himoya qilasiz ⚖",
    "Bodyguard": "Tansoqchi. Tunda bir o'yinchini qo'riqlaysiz 🛡",
    "Oshiq": "Oshiq. Tunda sevganingizga tashrif buyurasiz 💕",
    "Kamikaze": "Kamikaze. Ovoz berilganda portlaysiz 💥",
    "Mashuqa": "Mashuqa. Oshiq bilan bog'langansiz 💕",
    "Serjant": "Serjant. Komissar o'lsa uning o'rnini olasiz. 🗳 ovoz berish",
    "Buqalamun": "Buqalamun. Tunda ko'rinishingizni o'zgartirasiz 🦎",
    "Omadli": "Omadli. O'limdan qochish imkoniyati 50% 🍀",
    "Aferist": "Aferist. Tunda bir o'yinchini bloklaysiz 🔒",
    "Sehrgar": "Sehrgar. Tunda sehrli kuch ishlatasiz ✨",
    "Suidsid": "Suitsid. Ovoz berilganda o'zingizni o'ldirasiz 💔",
    "Don xotini": "Donning xotini. Tunda bir o'yinchini tekshirasiz 🔍",
    "Kimyogar": "Kimyogar. Tunda zahar tayyorlaysiz ☠",
    "Sotuvchi": "Sotuvchi. Tunda qurol sotasiz 🔫",
    "Tentak": "Tentak. Tunda bir o'yinchiga yopishasiz 🐙",
    "Oqituvchi": "O'qituvchi. Tunda bir o'yinchiga dars berasiz 📚",
    "Muxlis": "Muxlis. Tunda kumingizni kuzatasiz 👁",
    "Minior": "Minior. O'lganda portlaysiz ☄",
    "Mergan": "Snayper. Tunda bir o'yinchini otasiz 🎯",
    "Majnun": "Majnun. Tunda bir o'yinchiga bog'lanasiz 🔗",
    "Ubica": "Ubica. Tunda bir o'yinchini o'ldirasiz 💀",
    "Tinch aholi": "Tinch aholi. Kunda ovoz berib mafiyani toping.",
}


async def night_phase(context, game):
    chat_id = game.chat_id
    game.phase = "night"
    game.day += 1
    game.actions = {}
    game.votes = {}
    game.doc_choice = None
    game.maniac_target = None
    game.advokat_target = None
    game.serjant_choice = None
    game.don_target = None
    game.mafia_targets = {}
    game.muxlis_target = None
    game.majnun_target = None
    game.mine_target = None
    game.blocked_players = set()
    alive = game.alive_players
    if len(alive) < 2:
        await end_game(context, game)
        return
    for p in alive:
        await send_night_actions(context, game, p)
    setts = get_set(chat_id)
    await asyncio.sleep(setts["night"])
    await resolve_night(context, game)


async def send_night_actions(context, game, p):
    role = p.role
    alive_ids = [pl.user_id for pl in game.alive_players if pl.user_id != p.user_id]
    if not alive_ids:
        return
    text = f"🌙 {game.day}-tun. Siz: {ROLE_ICON.get(role,'')} {ROLE_DISPLAY.get(role,role)}\n\n"
    if role == "Komissar":
        text += "Harakat tanlang:"
        kb = make_single_kb([("🔍 Tekshirish", f"nact:kom_check:{game.day}"), ("🗡 O'ldirish", f"nact:kom_kill:{game.day}")])
    elif role == "Don":
        text += "Kimni o'ldirishni buyurasiz? 🩸"
        kb = make_kb_for_game(game, alive_ids, f"ndon_kill:{game.day}", emoji="🩸")
    elif role == "Mafia":
        text += "Kimni o'ldirishga ovoz berasiz? 🩸"
        kb = make_kb_for_game(game, alive_ids, f"nmafia_vote:{game.day}", emoji="🩸")
    elif role == "Serjant":
        text += "Kimni himoya qilishga ovoz berasiz? 🗳"
        kb = make_kb_for_game(game, alive_ids, f"nserjant:{game.day}", emoji="🗳")
    elif role == "Shifokor":
        text += "Kimni davolaysiz? 💊"
        kb = make_kb_for_game(game, alive_ids, f"ndoc:{game.day}", emoji="💊")
    elif role == "Manyak":
        text += "Kimni o'ldirasiz? 🗡"
        kb = make_kb_for_game(game, alive_ids, f"nmaniac:{game.day}", emoji="🗡")
    elif role == "Daydi":
        text += "Kimga tashrif buyurasiz? 👤"
        kb = make_kb_for_game(game, alive_ids, f"ndaydi:{game.day}")
    elif role == "Advokat":
        text += "Kimni himoya qilasiz? ⚖"
        kb = make_kb_for_game(game, alive_ids, f"nadv:{game.day}", emoji="⚖")
    elif role == "Bodyguard":
        text += "Kimni qo'riqlaysiz? 🛡"
        kb = make_kb_for_game(game, alive_ids, f"nguard:{game.day}", emoji="🛡")
    elif role == "Oshiq":
        text += "Sevganingizni tanlang: 💕"
        kb = make_kb_for_game(game, alive_ids, f"noshik:{game.day}", emoji="💕")
    elif role == "Mashuqa":
        text += "Oshigingiz bilan muloqot: 💕"
        kb = make_kb_for_game(game, alive_ids, f"nmashuqa:{game.day}", emoji="💕")
    elif role == "Aferist":
        text += "Kimni bloklaysiz? 🔒"
        kb = make_kb_for_game(game, alive_ids, f"nafer:{game.day}", emoji="🔒")
    elif role == "Sehrgar":
        text += "Sehrli kuchingizni kimga ishlatasiz? ✨"
        kb = make_kb_for_game(game, alive_ids, f"nsehr:{game.day}", emoji="✨")
    elif role == "Don xotini":
        text += "Kimni tekshirasiz? 🔍"
        kb = make_kb_for_game(game, alive_ids, f"ndonx:{game.day}", emoji="🔍")
    elif role == "Kimyogar":
        text += "Kimga zahar tayyorlaysiz? ☠"
        kb = make_kb_for_game(game, alive_ids, f"nkimyo:{game.day}", emoji="☠")
    elif role == "Sotuvchi":
        text += "Kimga qurol sotasiz? 🔫"
        kb = make_kb_for_game(game, alive_ids, f"nsotuv:{game.day}", emoji="🔫")
    elif role == "Tentak":
        text += "Kimga yopishasiz? 🐙"
        kb = make_kb_for_game(game, alive_ids, f"ntentak:{game.day}", emoji="🐙")
    elif role == "Oqituvchi":
        text += "Kimga dars berasiz? 📚"
        kb = make_kb_for_game(game, alive_ids, f"noqit:{game.day}", emoji="📚")
    elif role == "Muxlis":
        text += "Kumingizni tanlang: 👁"
        kb = make_kb_for_game(game, alive_ids, f"nmuxlis:{game.day}", emoji="👁")
    elif role == "Mergan":
        text += "Kimni otasiz? 🎯"
        kb = make_kb_for_game(game, alive_ids, f"nmergan:{game.day}", emoji="🎯")
    elif role == "Majnun":
        text += "Kimga bog'lanasiz? 🔗"
        kb = make_kb_for_game(game, alive_ids, f"nmajnun:{game.day}", emoji="🔗")
    elif role == "Ubica":
        text += "Kimni o'ldirasiz? 💀"
        kb = make_kb_for_game(game, alive_ids, f"nubica:{game.day}", emoji="💀")
    elif role in ("Tinch aholi", "Kamikaze", "Suidsid", "Minior", "Buqalamun", "Omadli"):
        text += "Tunda harakatingiz yo'q."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Kutish ✅", callback_data=f"wait:{game.day}")]])
    else:
        text += "Harakatingiz yo'q."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Kutish ✅", callback_data=f"wait:{game.day}")]])
    try:
        await context.bot.send_message(p.user_id, text, reply_markup=kb)
    except Exception as e:
        logging.error(f"send_night to {p.user_id}: {e}")


async def resolve_night(context, game):
    chat_id = game.chat_id
    kills = set()
    protected = set()
    doc_save = set()
    daydi_visitors = {}

    actions_snapshot = dict(game.actions)
    for uid, action in actions_snapshot.items():
        player = game.get_player(uid)
        if not player or not player.alive:
            continue
        target_id = action.get("target")
        atype = action.get("type", "")

        if atype == "don_kill" and target_id:
            game.don_target = target_id
        elif atype == "mafia_vote" and target_id:
            game.mafia_targets[uid] = target_id
        elif atype == "doc_heal" and target_id:
            game.doc_choice = target_id
        elif atype == "kom_check" and target_id:
            if game.day > 1:
                tp = game.get_player(target_id)
                if tp:
                    res = "Mafiya" if tp.team in ("mafia", "neutral") else "Fuqaro"
                    try:
                        await context.bot.send_message(uid, f"🔍 Natija: {res}")
                    except:
                        pass
        elif atype == "kom_kill" and target_id:
            kills.add(target_id)
        elif atype == "maniac_kill" and target_id:
            game.maniac_target = target_id
        elif atype == "adv_protect" and target_id:
            game.advokat_target = target_id
        elif atype == "guard_protect" and target_id:
            protected.add(target_id)
        elif atype == "serjant_vote" and target_id:
            game.serjant_choice = target_id
        elif atype == "daydi_visit" and target_id:
            if target_id not in daydi_visitors:
                daydi_visitors[target_id] = []
            daydi_visitors[target_id].append(uid)
        elif atype == "afer_blok" and target_id:
            game.blocked_players.add(target_id)
        elif atype == "kimyo_poison" and target_id:
            kills.add(target_id)
        elif atype == "mergan_shoot" and target_id:
            kills.add(target_id)
        elif atype == "ubica_kill" and target_id:
            kills.add(target_id)
        elif atype == "sehr_magic" and target_id:
            game.blocked_players.add(target_id)
        elif atype == "tentak_stick" and target_id:
            game.blocked_players.add(target_id)
        elif atype == "sotuv_sell" and target_id:
            add_item(target_id, "rifle", 1)
        elif atype == "donx_check" and target_id:
            tp = game.get_player(target_id)
            if tp:
                res = "Mafiya" if tp.team == "mafia" else "Fuqaro"
                try:
                    await context.bot.send_message(uid, f"🔍 Natija: {res}")
                except:
                    pass
        elif atype == "muxlis_watch" and target_id:
            game.muxlis_target = target_id
        elif atype == "majnun_bond" and target_id:
            game.majnun_target = target_id
        elif atype == "oqit_teach" and target_id:
            try:
                await context.bot.send_message(target_id, "📚 O'qituvchi sizga dars berdi! Keyingi ovozingiz 2 hisoblanadi.")
            except:
                pass
        elif atype == "oshik_visit" and target_id:
            tp = game.get_player(target_id)
            if tp and tp.role == "Mashuqa":
                try:
                    await context.bot.send_message(uid, "💕 Siz sevganingizni topdingiz!")
                    await context.bot.send_message(target_id, "💕 Oshigingiz sizni topdi!")
                except:
                    pass
        elif atype == "mashuqa_visit" and target_id:
            pass

    for target_id, visitors in daydi_visitors.items():
        for daydi_uid in visitors:
            names = []
            for v_uid in visitors:
                vp = game.get_player(v_uid)
                if vp and v_uid != daydi_uid:
                    names.append(vp.display)
            if names:
                try:
                    await context.bot.send_message(daydi_uid, f"👤 Sizga tashrif buyurganlar: {', '.join(names)}")
                except:
                    pass

    # Mafia kill voting
    game.don_target = None
    mafia_votes = {}
    for uid, action in actions_snapshot.items():
        if action.get("type") == "don_kill":
            game.don_target = action.get("target")
        elif action.get("type") == "mafia_vote":
            mafia_votes[uid] = action.get("target")

    if mafia_votes:
        from collections import Counter
        c = Counter(mafia_votes.values())
        if c:
            mc = c.most_common(1)[0]
            if mc[1] >= 2:
                kills.add(mc[0])
            elif game.don_target:
                kills.add(game.don_target)
            elif mc:
                kills.add(mc[0])
    if not kills and game.don_target:
        kills.add(game.don_target)
    if game.maniac_target:
        kills.add(game.maniac_target)

    if game.serjant_choice:
        protected.add(game.serjant_choice)

    killed_players = []
    saved_by_doc = False
    saved_by_adv = False
    for tid in kills:
        tp = game.get_player(tid)
        if tp and tp.alive and tp.user_id in game.blocked_players:
            try:
                await context.bot.send_message(tid, "🔒 Siz bloklangansiz! Hech qanday zarar yetmadi.")
            except:
                pass
            continue
        if tid in protected or game.doc_choice == tid:
            if game.doc_choice == tid:
                saved_by_doc = True
            if tid in protected:
                saved_by_adv = True
            continue
        if game.advokat_target == tid:
            saved_by_adv = True
            continue
        if has_item(tid, "shield") and remove_item(tid, "shield"):
            try:
                await context.bot.send_message(tid, "🛡 Himoya qutqardi!")
            except:
                pass
            continue
        target = game.get_player(tid)
        if target and target.alive:
            prof = get_profile(tid)
            if prof.get("hero") and random.random() < prof.get("hero_defense", 0) * 0.01:
                try:
                    await context.bot.send_message(tid, "🦸 Qahramon qutqardi!")
                except:
                    pass
                continue
            if target.role == "Omadli" and random.random() < 0.5:
                try:
                    await context.bot.send_message(tid, "🍀 Omad qutqardi!")
                except:
                    pass
                continue
            target.alive = False
            killed_players.append(target)

    # Serjant -> Komissar (endigina o'lganlardan keyin)
    komissar_dead = True
    serjant_alive = None
    for p in game.players.values():
        if p.role == "Komissar" and p.alive:
            komissar_dead = False
        if p.role == "Serjant" and p.alive:
            serjant_alive = p
    if komissar_dead and serjant_alive:
        serjant_alive.role = "Komissar"
        serjant_alive.team = "village"
        try:
            await context.bot.send_message(serjant_alive.user_id, "🕵️‍♂️ Komissar o'ldi! Endi siz yangi Komissarsiz!")
        except:
            pass

    if killed_players:
        names = ", ".join(fmt_player(p) for p in killed_players)
        await send_safe(context, chat_id, text=f"☠ O'ldirildi:\n{names}", parse_mode="HTML")
    else:
        msg = []
        if saved_by_doc:
            msg.append("🏥 Shifokor bir kishini o'limdan qutqardi!")
        if saved_by_adv:
            msg.append("⚖ Advokat bir kishini himoya qildi!")
        if not msg:
            msg.append("☀ Bugun hech kim o'lmadi.")
        await send_safe(context, chat_id, text="\n".join(msg))

    await send_safe(context, chat_id, animation=DAY_GIF, caption=f"☀ {game.day}-kun boshlandi!")
    game.phase = "day"
    await check_win(context, game)


async def check_win(context, game):
    alive = game.alive_players
    mafia = [p for p in alive if p.team == "mafia"]
    village = [p for p in alive if p.team == "village"]
    neutral = [p for p in alive if p.team == "neutral"]
    neutral_killers = [p for p in alive if p.role in ("Manyak", "Ubica")]
    if not mafia and not neutral_killers and not neutral:
        await end_game(context, game, "village")
    elif not village and not neutral_killers and not neutral:
        await end_game(context, game, "mafia")
    elif not mafia and not village and neutral_killers:
        await end_game(context, game, "neutral")
    elif len(mafia) >= len(village) and not neutral_killers:
        await end_game(context, game, "mafia")
    elif not mafia and not village and neutral:
        await end_game(context, game, "neutral")
    else:
        await day_phase(context, game)


async def day_phase(context, game):
    chat_id = game.chat_id
    setts = get_set(chat_id)
    game.votes = {}
    alive = game.alive_players
    if len(alive) < 2:
        await end_game(context, game)
        return
    text = f"☀ {game.day}-kun boshlandi!\n\nTirik o'yinchilar ({len(alive)}/{len(game.players)}):\n"
    for i, p in enumerate(alive, 1):
        text += f"{i}. {p.display}\n"
    text += f"\nUlardan kimlar:\n"
    role_list = {}
    for p in game.players.values():
        r = p.role
        if r:
            role_list[r] = role_list.get(r, 0) + 1
    for r, c in sorted(role_list.items(), key=lambda x: x[0]):
        text += f"{ROLE_ICON.get(r,'')} {ROLE_DISPLAY.get(r,r)} - {c}, "
    text = text.rstrip(", ") + f"\nJami: {len(alive)} kishi.\n\nTunda bo'lgan xodisalarni muxokama qilishning ayni vaqti..."
    kb = []
    row = []
    for p in alive:
        row.append(InlineKeyboardButton(f"{ROLE_ICON.get(p.role,'')} {p.display}", callback_data=f"vote:{game.day}:{p.user_id}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("O'tkazib yuborish", callback_data=f"vskip:{game.day}")])
    await send_safe(context, chat_id, text=text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    for p in alive:
        try:
            await context.bot.send_message(p.user_id, f"☀ {game.day}-kun boshlandi! Ovoz berish vaqti!\n\nGuruhda ovoz berish tugmalarini bosing yoki /vote @user")
        except:
            pass
    await asyncio.sleep(setts["vote"])
    await resolve_vote(context, game)


async def resolve_vote(context, game):
    chat_id = game.chat_id
    if not game.votes:
        await send_safe(context, chat_id, text="Hech kim ovoz bermadi.")
        await night_phase(context, game)
        return
    votes_snapshot = dict(game.votes)
    from collections import Counter
    c = Counter(votes_snapshot.values())
    if not c:
        await send_safe(context, chat_id, text="Hech kim ovoz bermadi.")
        await night_phase(context, game)
        return
    mc = c.most_common(1)[0]
    max_v = mc[1]
    alive = game.alive_players
    half = len(alive) / 2
    candidates = [uid for uid, v in c.items() if v == max_v]
    if max_v <= half or len(candidates) > 1:
        await send_safe(context, chat_id, text=f"Hech kim chiqarilmadi ({max_v}/{len(alive)}).")
        await night_phase(context, game)
        return
    ejected_id = candidates[0]
    ejected = game.get_player(ejected_id)
    if ejected and ejected.alive:
        if has_item(ejected_id, "vote_protect") and remove_item(ejected_id, "vote_protect"):
            await send_safe(context, chat_id, text=f"🛡 {ejected.display} ovoz himoyasi bilan qutuldi!")
            await night_phase(context, game)
            return
        if ejected.role == "Suidsid":
            ejected.alive = False
            await send_safe(context, chat_id, text=f"💔 {ejected.display} (Suitsid) ovoz berilishidan oldin o'zini o'ldirdi!")
            rd = f"{ROLE_ICON.get(ejected.role,'')} {ROLE_DISPLAY.get(ejected.role,ejected.role)}"
            await send_safe(context, chat_id, text=f"{ejected.display} o'zini o'ldirdi! Rol: {rd}", parse_mode="HTML")
            await check_win(context, game)
            return
        ejected.alive = False
        if ejected.role == "Kamikaze":
            await send_safe(context, chat_id, text="💥 Kamikaze portladi!")
            for vid, tid in votes_snapshot.items():
                if tid == ejected_id:
                    vp = game.get_player(vid)
                    if vp and vp.alive:
                        vp.alive = False
                        await send_safe(context, chat_id, text=f"💥 {vp.display} portlashda o'ldi!")
                    break
        elif ejected.role == "Minior":
            await send_safe(context, chat_id, text="💥 Minior portladi!")
            lst = [p for p in game.alive_players if p.user_id != ejected_id]
            if lst:
                t = random.choice(lst)
                t.alive = False
                await send_safe(context, chat_id, text=f"💥 {t.display} portlashda o'ldi!")
        if has_item(ejected_id, "mask") and remove_item(ejected_id, "mask"):
            await send_safe(context, chat_id, text=f"🎭 {ejected.display}ning roli noma'lum!")
        else:
            rd = f"{ROLE_ICON.get(ejected.role,'')} {ROLE_DISPLAY.get(ejected.role,ejected.role)}"
            await send_safe(context, chat_id, text=f"{ejected.display} chiqarildi! Rol: {rd}", parse_mode="HTML")
    await check_win(context, game)


async def end_game(context, game, winner=None):
    chat_id = game.chat_id
    if winner == "village":
        title = "Fuqarolar g'alaba qozondi! 🎉"
        winners = [p for p in game.players.values() if p.team == "village"]
        losers = [p for p in game.players.values() if p.team != "village"]
    elif winner == "mafia":
        title = "Mafiya g'alaba qozondi! 🎉"
        winners = [p for p in game.players.values() if p.team == "mafia"]
        losers = [p for p in game.players.values() if p.team != "mafia"]
    elif winner == "neutral":
        title = "Neytral kuchlar g'alaba qozondi! 🎉"
        winners = [p for p in game.players.values() if p.team == "neutral"]
        losers = [p for p in game.players.values() if p.team != "neutral"]
    else:
        title = "O'yin tugadi! 🎮"
        winners = []
        losers = list(game.players.values())
    text = f"O'yin tugadi!\n\n{title}\n\n"
    if winners:
        text += "G'olib bo'lgan o'yinchilar:\n"
        for p in winners:
            rd = f"{ROLE_ICON.get(p.role,'')} {ROLE_DISPLAY.get(p.role,p.role)}"
            text += f"{p.display} — {rd}\n"
        text += "\n"
    if losers:
        text += "Qolgan o'yinchilar ro'yhati:\n"
        for p in losers:
            rd = f"{ROLE_ICON.get(p.role,'')} {ROLE_DISPLAY.get(p.role,p.role)}"
            text += f"{p.display} — {rd}\n"
    if game.start_time:
        elapsed = int(time.time() - game.start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        if mins > 0:
            text += f"\nO'yin vaqti: {mins} minut {secs} sekund"
        else:
            text += f"\nO'yin vaqti: {secs} sekund"
    setts = get_set(chat_id)
    text += f"\n\nkun {setts['vote']}s\ntun {setts['night']}s"
    await send_safe(context, chat_id, text=text)
    w = load_weekly()
    for p in game.players.values():
        prof = get_profile(p.user_id)
        prof["games"] = prof.get("games", 0) + 1
        was_winner = False
        if winner == "village" and p.team == "village":
            prof["wins"] = prof.get("wins", 0) + 1
            prof["dollars"] = prof.get("dollars", 0) + 10
            was_winner = True
        elif winner == "mafia" and p.team == "mafia":
            prof["wins"] = prof.get("wins", 0) + 1
            prof["dollars"] = prof.get("dollars", 0) + 15
            was_winner = True
        elif winner == "neutral" and p.team == "neutral":
            prof["wins"] = prof.get("wins", 0) + 1
            prof["dollars"] = prof.get("dollars", 0) + 20
            was_winner = True
        else:
            prof["losses"] = prof.get("losses", 0) + 1
        uid_str = str(p.user_id)
        if uid_str not in w["players"]:
            w["players"][uid_str] = {"score": 0}
        w["players"][uid_str]["score"] = w["players"][uid_str].get("score", 0) + (3 if was_winner else 1)
    save_weekly(w)
    flush_profiles()
    del games[chat_id]
    ghosts.pop(chat_id, None)


async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if check_flood(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in games or games[chat_id].phase != "day":
        await update.message.reply_text("Hozir ovoz vaqti emas!")
        return
    game = games[chat_id]
    if user.id not in game.players or not game.players[user.id].alive:
        await update.message.reply_text("Siz tirik emassiz!")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Format: /vote @user")
        return
    target_name = args[0].strip("@")
    target_id = None
    for pid, p in game.players.items():
        if p.alive:
            if p.username and p.username.lower() == target_name.lower():
                target_id = pid
                break
            if p.first_name.lower() == target_name.lower():
                target_id = pid
                break
    if not target_id:
        await update.message.reply_text("Topilmadi!")
        return
    game.votes[user.id] = target_id
    await update.message.reply_text(f"Siz {game.players[target_id].display} ga ovoz berdingiz!")


async def defend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if check_flood(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in games or games[chat_id].phase != "day":
        await update.message.reply_text("Hozir himoya vaqti emas!")
        return
    game = games[chat_id]
    if user.id not in game.players or not game.players[user.id].alive:
        await update.message.reply_text("Siz tirik emassiz!")
        return
    game.players[user.id].defended = True
    await update.message.reply_text("Himoya so'zi oldingiz!")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if check_flood(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    if chat_id not in games:
        await update.message.reply_text("O'yin yo'q!")
        return
    game = games[chat_id]
    alive = game.alive_players
    dead = [p for p in game.players.values() if not p.alive]
    text = f"🎮 Faza: {game.phase.upper()} | Kun: {game.day} | Tirik: {len(alive)}/{len(game.players)}\n\nJonli:\n"
    for p in alive:
        text += f"• {p.display}\n"
    if dead:
        text += f"\nO'lgan ({len(dead)}):\n"
        for p in dead:
            text += f"• {p.display}\n"
    await update.message.reply_text(text)


async def ghost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in ghosts or user.id not in ghosts[chat_id]:
        await update.message.reply_text("Ghost chatga kira olmaysiz!")
        return
    msg = update.message.text
    if not msg.startswith("/g "):
        return
    text = msg[3:].strip()
    if not text:
        return
    for uid in ghosts.get(chat_id, set()):
        if uid != user.id:
            try:
                await context.bot.send_message(uid, f"👻 {text}")
            except:
                pass


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Yordam\n\nAsosiy:\n/mafia - Yaratish\n/join - Qo'shilish\n/leave - Chiqish\n"
        "/players - O'yinchilar\n/startgame - Boshlash (admin)\n/vote @user - Ovoz\n"
        "/defend - Himoya\n/status - Holat\n/money - Hisob\n/profile - Profil\n"
        "/shop - Do'kon\n/geroyinfo - Qahramon\n/send @user sum - Pul\n"
        "/change sum - Olmos->Evro\n/g xabar - Ghost\n/top - Reyting\n"
        "/help - Yordam\n\nAdmin:\n/give @user sum - Olmos\n"
        "/gsend @user sum tur - Pul berish\n/giveaway sum\n/settings\n/set"
    )


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = load_stats()
    profs = load_profiles()
    sorted_u = sorted(s.items(), key=lambda x: x[1].get("wins", 0), reverse=True)[:50]
    text = "🏆 *TOP REYTING* 🏆\n\n"
    for i, (uid, st) in enumerate(sorted_u, 1):
        name = profs.get(uid, {}).get("name", uid)
        text += f"{i}. {name}: {st.get('wins',0)} g'alaba ({st.get('games',0)} o'yin)\n"
    if not sorted_u:
        text += "Statistika yo'q."
    else:
        text += "\n🎁 *Sovrinlar:*\n🥇 Top 1: 200💰 Evro\n🥈 Top 2-5: 100💰 Evro\n🥉 Top 6-50: 50💰 Evro"
    await update.message.reply_text(text, parse_mode="Markdown")


async def hafta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    w = load_weekly()
    profs = load_profiles()
    players = w.get("players", {})
    if not players:
        await update.message.reply_text("📅 Bu hafta hali hech kim o'ynamadi!")
        return
    sorted_u = sorted(players.items(), key=lambda x: x[1].get("score", 0), reverse=True)[:50]
    text = "📅 *HAFTA REYTINGI* 📅\n\n"
    for i, (uid, data) in enumerate(sorted_u, 1):
        name = profs.get(uid, {}).get("name", uid)
        score = data.get("score", 0)
        text += f"{i}. {name}: {score} ball\n"
    text += "\n🎁 *Sovrinlar:*\n"
    text += "🥇 Top 1: 45💎 Olmos\n🥈 Top 2-10: 10💎 Olmos\n"
    text += "🥉 Top 11-20: 4💎 Olmos\n🏅 Top 21-50: 500💰 Evro"
    await update.message.reply_text(text, parse_mode="Markdown")


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if not await is_admin(update.effective_chat, user.id, context):
        await update.message.reply_text("Faqat admin!")
        return
    setts = get_set(chat_id)
    await update.message.reply_text(
        f"⚙ Sozlamalar:\nMin: {setts['min']}\nTun: {setts['night']}s\nOvoz: {setts['vote']}s\n"
        f"Mode: {GAME_MODES.get(setts['mode'], setts['mode'])}\n\n/set parametr qiymat\n"
        "Param: min, night, vote, mode\nMode: classic/full"
    )


async def set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if not await is_admin(update.effective_chat, user.id, context):
        await update.message.reply_text("Faqat admin!")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Format: /set param qiymat")
        return
    param = args[0].lower()
    value = args[1]
    setts = get_set(chat_id)
    if param == "min":
        try:
            v = int(value)
        except:
            await update.message.reply_text("Noto'g'ri!")
            return
        if 1 <= v <= MAX_PLAYERS:
            setts["min"] = v
            await update.message.reply_text(f"Min: {v}")
        else:
            await update.message.reply_text(f"1-{MAX_PLAYERS}")
    elif param == "night":
        try:
            v = int(value)
        except:
            await update.message.reply_text("Noto'g'ri!")
            return
        if 5 <= v <= 120:
            setts["night"] = v
            await update.message.reply_text(f"Tun: {v}s")
        else:
            await update.message.reply_text("5-120")
    elif param == "vote":
        try:
            v = int(value)
        except:
            await update.message.reply_text("Noto'g'ri!")
            return
        if 5 <= v <= 120:
            setts["vote"] = v
            await update.message.reply_text(f"Ovoz: {v}s")
        else:
            await update.message.reply_text("5-120")
    elif param == "mode":
        if value.lower() in GAME_MODES:
            setts["mode"] = value.lower()
            await update.message.reply_text(f"Mode: {GAME_MODES[value.lower()]}")
            if chat_id in games:
                games[chat_id].mode = value.lower()
        else:
            await update.message.reply_text("classic/full")
    else:
        await update.message.reply_text("Param: min, night, vote, mode")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prof = get_profile(user.id, user.first_name, user.username)
    await update.message.reply_text(f"📊 O'yinlar: {prof.get('games',0)} | G'alaba: {prof.get('wins',0)} | Mag'lubiyat: {prof.get('losses',0)}")


async def setimage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Faqat admin!")
        return
    awaiting_image.add(user.id)
    await update.message.reply_text("Rasm yuboring, men uni game rasmi qilib qo'yaman.")


# ────────── CALLBACK HANDLER ──────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if check_flood(user_id):
        await query.answer("Sekinroq!")
        return

    if data == "joingame":
        if chat_id not in games or games[chat_id].phase != "registration":
            await query.answer("O'yin mavjud emas yoki ro'yxat tugagan!", show_alert=True)
            return
        game = games[chat_id]
        if user_id in game.players:
            await query.answer("Siz allaqachon o'yindasiz!", show_alert=True)
            return
        if len(game.players) >= MAX_PLAYERS:
            await query.answer("O'yin to'liq!", show_alert=True)
            return
        user = query.from_user
        game.players[user_id] = Player(user_id, user.first_name, user.username)
        if chat_id not in ghosts:
            ghosts[chat_id] = set()
        ghosts[chat_id].add(user_id)
        await update_game_msg(context, game)
        await query.answer("✅ O'yinga qo'shildingiz!")
        return

    if data == "payment":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Pul tushdi", callback_data="check_paid")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_payment")]
        ])
        await query.edit_message_text(f"💳 To'lov\nKarta: {CARD_NUMBER}\n\nMin: 50 olmos, Max: 10000 olmos\n\nTo'lov qilib, chek rasm yuboring, so'ng 'Pul tushdi' ni bosing.", reply_markup=kb)
        return
    if data == "check_paid":
        await query.edit_message_text("Iltimos, avval chek rasmini yuboring!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📸 Chek", callback_data="send_check")]]))
        return
    if data == "send_check":
        pending_checks[user_id] = {"step": "waiting_photo"}
        await query.edit_message_text("Chek rasmini yuboring.")
        return
    if data == "cancel_payment":
        await query.edit_message_text("Bekor qilindi.")
        return
    if data.startswith("confirm_pay:"):
        if user_id != ADMIN_ID:
            await query.answer("Admin emas!", show_alert=True)
            return
        parts = data.split(":")
        if len(parts) >= 3:
            tuid = int(parts[1])
            amt = int(parts[2])
            add_olmos(tuid, amt)
            await query.edit_message_text(f"✅ {amt} olmos tasdiqlandi!")
            try:
                await context.bot.send_message(tuid, f"✅ {amt} olmos hisobga tushdi!")
            except:
                pass
        return
    if data.startswith("reject_pay:"):
        if user_id != ADMIN_ID:
            await query.answer("Admin emas!", show_alert=True)
            return
        parts = data.split(":")
        if len(parts) >= 2:
            tuid = int(parts[1])
            await query.edit_message_text("❌ To'lov rad etildi.")
            try:
                await context.bot.send_message(tuid, "❌ To'lov rad etildi.")
            except:
                pass
        return

    if data == "buyhero":
        prof = get_profile(user_id)
        if prof.get("hero"):
            await query.edit_message_text("Hero bor!")
            return
        if prof["olmos"] < 90:
            await query.edit_message_text("90 olmos kerak!")
            return
        prof["olmos"] -= 90
        prof["hero"] = True
        prof["hero_attack"] = random.randint(5, 15)
        prof["hero_defense"] = random.randint(5, 15)
        save_profile(user_id, prof)
        await query.edit_message_text(f"🎉 Hero sotib olindi!\n⚔ Hujum: +{prof['hero_attack']}\n🛡 Himoya: +{prof['hero_defense']}")
        return

    if data == "buyrole":
        kb = []
        prof = get_profile(user_id)
        for role, price in sorted(ROLE_PRICES.items(), key=lambda x: x[1]):
            kb.append([InlineKeyboardButton(f"{ROLE_ICON.get(role,'')} {ROLE_DISPLAY.get(role,role)} - {price} olmos", callback_data=f"buyrole:{role}")])
        await query.edit_message_text(f"🎭 Rol sotib olish\n💎 Sizda: {prof['olmos']} olmos", reply_markup=InlineKeyboardMarkup(kb))
        return
    if data.startswith("buyrole:"):
        role = data.split(":", 1)[1]
        prof = get_profile(user_id)
        price = ROLE_PRICES.get(role, 0)
        if prof["olmos"] < price:
            await query.edit_message_text(f"{price} olmos kerak!")
            return
        prof["olmos"] -= price
        prof["bought_role"] = role
        save_profile(user_id, prof)
        await query.edit_message_text(f"✅ {ROLE_ICON.get(role,'')} {ROLE_DISPLAY.get(role,role)} sotib olindi!")
        return

    if data.startswith("buy:"):
        item_id = data.split(":", 1)[1]
        prof = get_profile(user_id)
        price = ITEM_PRICES.get(item_id, 0)
        if prof["olmos"] < price:
            await query.edit_message_text(f"{price} olmos kerak!")
            return
        prof["olmos"] -= price
        if item_id not in prof["items"]:
            prof["items"][item_id] = {"count": 0, "active": True}
        prof["items"][item_id]["count"] += 1
        save_profile(user_id, prof)
        await query.edit_message_text(f"✅ {ITEM_NAMES.get(item_id, item_id)} (x{prof['items'][item_id]['count']})")
        return

    if data.startswith("nact:"):
        parts = data.split(":")
        if len(parts) < 3:
            return
        action_prefix = parts[1]
        day = parts[2]
        game = find_game(user_id, chat_id)
        if not game or game.phase != "night":
            await query.edit_message_text("Harakat vaqti emas!")
            return
        night_step[user_id] = {"action": action_prefix, "day": int(day)}
        alive_ids = [pl.user_id for pl in game.alive_players if pl.user_id != user_id]
        emoji_map = {"kom_check": "🔍", "kom_kill": "🗡"}
        em = emoji_map.get(action_prefix, "")
        kb = make_kb_for_game(game, alive_ids, f"ntarget:{action_prefix}", emoji=em)
        text = f"🌙 {game.day}-tun. " + ("Kimni tekshirasiz? 🔍" if "check" in action_prefix else "Kimni o'ldirasiz? 🗡")
        await query.edit_message_text(text, reply_markup=kb)
        return

    if data.startswith("ntarget:"):
        parts = data.split(":")
        if len(parts) < 3:
            return
        action_prefix = parts[1]
        target_id = int(parts[2])
        game = find_game(user_id, chat_id)
        if not game or game.phase != "night":
            await query.edit_message_text("Harakat vaqti emas!")
            return
        if user_id in game.actions:
            await query.edit_message_text("Allaqachon harakat qilgansiz!")
            return
        target_player = game.get_player(target_id)
        if not target_player or not target_player.alive:
            await query.edit_message_text("Tirik emas!")
            return
        action_map = {"kom_check": "kom_check", "kom_kill": "kom_kill"}
        game.actions[user_id] = {"type": action_map.get(action_prefix, "unknown"), "target": target_id}
        role = game.players[user_id].role
        msg = NIGHT_ATMOSPHERE.get(role, "🌙 Tun qorong'usida nimadir yuz berdi...")
        try:
            await context.bot.send_message(game.chat_id, msg)
        except:
            pass
        emoji_map = {"kom_check": "🔍", "kom_kill": "🗡"}
        em = emoji_map.get(action_prefix, "")
        await query.edit_message_text(f"{em} {target_player.display} " + ("tekshirilmoqda..." if "check" in action_prefix else "o'ldirilmoqda..."))
        if user_id in night_step:
            del night_step[user_id]
        return

    night_single = ("ndon_kill:", "nmafia_vote:", "ndoc:", "nmaniac:", "ndaydi:", "nadv:", "nguard:",
                    "noshik:", "nmashuqa:", "nafer:", "nsehr:", "ndonx:", "nkimyo:", "nsotuv:",
                    "ntentak:", "noqit:", "nmuxlis:", "nmergan:", "nmajnun:", "nubica:", "nserjant:")
    if data.startswith(night_single):
        prefix = data.split(":")[0]
        parts = data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("Xatolik!")
            return
        target_id = int(parts[2])
        game = find_game(user_id, chat_id)
        if not game:
            await query.edit_message_text("O'yinda emassiz!")
            return
        if game.phase != "night":
            await query.edit_message_text("Hozir tun emas!")
            return
        p = game.get_player(user_id)
        if not p or not p.alive:
            await query.edit_message_text("Siz o'lgansiz!")
            return
        if user_id in game.actions:
            await query.edit_message_text("Allaqachon harakat qilgansiz!")
            return
        target_player = game.get_player(target_id)
        if not target_player or not target_player.alive:
            await query.edit_message_text("Tirik emas!")
            return
        action_map = {
            "ndon_kill": "don_kill", "nmafia_vote": "mafia_vote", "ndoc": "doc_heal",
            "nmaniac": "maniac_kill", "ndaydi": "daydi_visit", "nadv": "adv_protect",
            "nguard": "guard_protect", "noshik": "oshik_visit", "nmashuqa": "mashuqa_visit",
            "nafer": "afer_blok", "nsehr": "sehr_magic", "ndonx": "donx_check",
            "nkimyo": "kimyo_poison", "nsotuv": "sotuv_sell", "ntentak": "tentak_stick",
            "noqit": "oqit_teach", "nmuxlis": "muxlis_watch", "nmergan": "mergan_shoot",
            "nmajnun": "majnun_bond", "nubica": "ubica_kill", "nserjant": "serjant_vote",
        }
        atype = action_map.get(prefix, "unknown")
        game.actions[user_id] = {"type": atype, "target": target_id}
        role = game.players[user_id].role
        msg = NIGHT_ATMOSPHERE.get(role, "🌙 Tun qorong'usida nimadir yuz berdi...")
        try:
            await context.bot.send_message(game.chat_id, msg)
        except:
            pass
        await query.edit_message_text(f"✅ {target_player.display} - harakat qabul qilindi!")
        return

    if data.startswith("vote:"):
        parts = data.split(":")
        if len(parts) >= 3:
            target_id = int(parts[2])
            game = find_game(user_id, chat_id)
            if not game:
                await query.edit_message_text("O'yinda emassiz!")
                return
            if game.phase != "day":
                await query.edit_message_text("Ovoz vaqti emas!")
                return
            p = game.get_player(user_id)
            if not p or not p.alive:
                await query.edit_message_text("Siz o'lgansiz!")
                return
            tp = game.get_player(target_id)
            if not tp or not tp.alive:
                await query.edit_message_text("Tirik emas!")
                return
            game.votes[user_id] = target_id
            await query.edit_message_text(f"Siz {tp.display} ga ovoz berdingiz!")
        return
    if data.startswith("vskip:"):
        game = find_game(user_id, chat_id)
        if game and game.phase == "day" and user_id not in game.votes:
            game.votes[user_id] = -1
        await query.edit_message_text("O'tkazib yuborildi.")
        return
    if data.startswith("wait:"):
        await query.edit_message_text("✅ Kutish.")


# ────────── PHOTO / TEXT HANDLERS ──────────


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_config(data):
    atomic_write(CONFIG_FILE, data)


cfg = load_config()
GAME_IMAGE = cfg.get("game_image")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id == ADMIN_ID and user.id in awaiting_image:
        photo = update.message.photo[-1]
        global GAME_IMAGE
        GAME_IMAGE = photo.file_id
        cfg = load_config()
        cfg["game_image"] = photo.file_id
        save_config(cfg)
        awaiting_image.discard(user.id)
        await update.message.reply_text("✅ Rasm saqlandi!")
        return
    elif user.id == ADMIN_ID:
        awaiting_image.discard(user.id)
        return

    if user.id not in pending_checks or pending_checks[user.id].get("step") != "waiting_photo":
        return
    photo = update.message.photo[-1]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_pay:{user.id}:100")], [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_pay:{user.id}")]])
    await context.bot.send_photo(ADMIN_ID, photo.file_id, caption=f"💳 Chek\n{user.first_name} (@{user.username or '-'})\nID: {user.id}", reply_markup=kb)
    pending_checks[user.id] = {"step": "waiting_amount", "photo_id": photo.file_id}
    await update.message.reply_text("✅ Chek qabul qilindi! Summani yozing (olmos 50-10000):\nMisol: 100")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in pending_checks:
        state = pending_checks[user.id]
        if state.get("step") == "waiting_amount":
            try:
                amount = int(update.message.text.strip())
                if amount < 50 or amount > 10000:
                    await update.message.reply_text("50-10000!")
                    return
                state["amount"] = amount
                state["step"] = "confirmed"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_pay:{user.id}:{amount}")], [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_pay:{user.id}")]])
                await context.bot.send_message(ADMIN_ID, f"💰 To'lov: {user.first_name} (@{user.username or ''}) - {amount} olmos", reply_markup=kb)
                await update.message.reply_text(f"✅ {amount} olmos so'rovi yuborildi. Kuting...")
                del pending_checks[user.id]
            except:
                await update.message.reply_text("Son yozing! Masalan: 100")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")


def main():
    app = Application.builder().token(TOKEN).build()
    cmds = [
        ("start", start), ("mafia", mafia), ("join", join), ("leave", leave), ("players", players),
        ("startgame", startgame), ("vote", vote), ("defend", defend), ("status", status), ("g", ghost),
        ("help", help_cmd), ("top", top), ("hafta", hafta), ("stats", stats),
        ("settings", settings_cmd), ("set", set_cmd), ("setimage", setimage),
        ("money", money), ("send", send), ("give", give), ("gsend", gsend), ("change", change),
        ("giveaway", giveaway), ("shop", shop), ("profile", profile), ("geroyinfo", geroyinfo),
    ]
    for n, h in cmds:
        app.add_handler(CommandHandler(n, h))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)
    print("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
