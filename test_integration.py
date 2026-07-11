"""
Integration test: imports the module, creates mock update/context,
and simulates calling every handler to catch runtime errors.
"""
import sys, os, json
sys.path.insert(0, r"D:\pylibs")
os.environ["BOT_TOKEN"] = "8928310354:AAHQ_jAuUqxfWH3Zz5NRAyqBs9YnShmo2CQ"
os.environ["CARD_NUMBER"] = "4073-4200-7154-7032"

import mafia_bot as bot
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import traceback

errors = []

class FakeChat:
    def __init__(self, id=-100123):
        self.id = id
        self.type = "group"

class FakeUser:
    def __init__(self, id=100001, first_name="Test", username="tester", is_bot=False):
        self.id = id
        self.first_name = first_name
        self.username = username
        self.is_bot = is_bot
        self.full_name = first_name

class FakeMessage:
    def __init__(self, chat_id=-100123, text="", user_id=100001):
        self.chat_id = chat_id
        self.message_id = 42
        self.text = text
        self.from_user = FakeUser(id=user_id)
        self.effective_user = self.from_user
        self.chat = FakeChat(id=chat_id)
        self.photo = None
        self.caption = None

class FakeCallbackQuery:
    def __init__(self, data, user_id=100001, chat_id=-100123):
        self.data = data
        self.from_user = FakeUser(id=user_id)
        self.message = FakeMessage(chat_id=chat_id)
        self.message.reply_markup = None
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()
        self.edit_message_caption = AsyncMock()

class FakeUpdate:
    def __init__(self, data=None, user_id=100001, chat_id=-100123, text=""):
        self.callback_query = None
        self.effective_user = FakeUser(id=user_id)
        self.effective_chat = FakeChat(id=chat_id)
        self.message = FakeMessage(chat_id=chat_id, text=text, user_id=user_id)
        if data is not None:
            self.callback_query = FakeCallbackQuery(data=data, user_id=user_id, chat_id=chat_id)

class FakeContext:
    def __init__(self):
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.bot.send_photo = AsyncMock()
        self.bot.send_animation = AsyncMock()
        self.bot.get_me = AsyncMock()
        self.bot.get_me.return_value = MagicMock(username="NightKillersBot")
        self.bot.get_file = AsyncMock()
        self.job_queue = None
        self.args = []

def test_callback(data, user_id=100001, chat_id=-100123, desc=""):
    try:
        update = FakeUpdate(data=data, user_id=user_id, chat_id=chat_id)
        context = FakeContext()
        import asyncio
        asyncio.run(bot.button_handler(update, context))
        return True
    except Exception as e:
        errors.append(f"[FAIL] {desc or data}: {e}")
        traceback.print_exc()
        return False

# Reset state
bot.games.clear()
bot.pending_checks.clear()
bot.confirmed_payments.clear()
bot.cooldown.clear()
bot.chat_cooldown.clear()
bot.profile_cache = None
bot.profile_cache_dirty = False

print("Testing ALL callbacks...\n")

# ── Start menu callbacks ──
tests = [
    ("start_profile", "start_profile"),
    ("start_money", "start_money"),
    ("start_top", "start_top"),
    ("start_weekly", "start_weekly"),
    ("start_shop", "start_shop"),
    ("start_stats", "start_stats"),
    ("start_settings", "start_settings"),
    ("start_help", "start_help"),
    ("start_about", "start_about"),
    ("start_back", "start_back"),
]

for data, desc in tests:
    ok = test_callback(data, desc=desc)
    if ok:
        print(f"  [OK] {desc}")

# ── joingame callback ──
g = bot.MafiaGame(-100123, "classic")
for i in range(3):
    g.players[i] = bot.Player(i, f"Player{i}")
g.game_msg_id = 99
bot.games[-100123] = g
print(f"  {'[OK]' if test_callback('joingame', user_id=99999) else '[FAIL]'} joingame (new player)")
print(f"  {'[OK]' if test_callback('joingame', user_id=0) else '[FAIL]'} joingame (existing player)")

# ── Payment callbacks ──
print(f"  {'[OK]' if test_callback('payment') else '[FAIL]'} payment")
print(f"  {'[OK]' if test_callback('send_check') else '[FAIL]'} send_check")
print(f"  {'[OK]' if test_callback('cancel_payment') else '[FAIL]'} cancel_payment")
print(f"  {'[OK]' if test_callback('confirm_pay:100001:100', user_id=bot.ADMIN_ID) else '[FAIL]'} confirm_pay (admin)")
print(f"  {'[OK]' if test_callback('confirm_pay:100001:100', user_id=12345) else '[FAIL]'} confirm_pay (non-admin)")
print(f"  {'[OK]' if test_callback('reject_pay:100001', user_id=bot.ADMIN_ID) else '[FAIL]'} reject_pay")

# ── Shop callbacks ──
print(f"  {'[OK]' if test_callback('buyhero') else '[FAIL]'} buyhero")
print(f"  {'[OK]' if test_callback('buyrole') else '[FAIL]'} buyrole")
# Add olmos first
bot.add_olmos(100001, 99999)
print(f"  {'[OK]' if test_callback('buyhero') else '[FAIL]'} buyhero (afford)")
print(f"  {'[OK]' if test_callback('buyrole:Don') else '[FAIL]'} buyrole:Don")
print(f"  {'[OK]' if test_callback('buy:shield') else '[FAIL]'} buy:shield")

# ── Night actions ──
# Setup night game
gnight = bot.MafiaGame(-100200, "classic")
for i in range(5):
    p = bot.Player(i, f"P{i}")
    p.role = ["Don", "Mafia", "Komissar", "Shifokor", "Tinch aholi"][i]
    p.team = ["mafia", "mafia", "village", "village", "village"][i]
    p.alive = True
    gnight.players[i] = p
gnight.phase = "night"
gnight.day = 2
gnight.game_msg_id = 99
bot.games[-100200] = gnight

night_prefixes = ["ndon_kill", "nmafia_vote", "ndoc", "nmaniac", "ndaydi", "nadv",
    "nguard", "noshik", "nmashuqa", "nafer", "nsehr", "ndonx",
    "nkimyo", "nsotuv", "ntentak", "noqit", "nmuxlis", "nmergan",
    "nmajnun", "nubica", "nserjant"]

for prefix in night_prefixes:
    data = f"{prefix}:2:3"
    ok = test_callback(data, user_id=3, chat_id=-100200, desc=f"night:{prefix}")
    if not ok:
        pass  # already logged

# ── Vote callbacks ──
# Setup day game
gday = bot.MafiaGame(-100300, "classic")
for i in range(3):
    p2 = bot.Player(i, f"P{i}")
    p2.alive = True
    p2.role = "Tinch aholi"
    p2.team = "village"
    gday.players[i] = p2
gday.phase = "day"
gday.day = 1
gday.game_msg_id = 99
bot.games[-100300] = gday

print(f"  {'[OK]' if test_callback('vote:0:1', chat_id=-100300, desc='vote') else '[FAIL]'} vote")
print(f"  {'[OK]' if test_callback('vskip:0', chat_id=-100300, desc='vskip') else '[FAIL]'} vskip")

# ── nact / ntarget ──
print(f"  {'[OK]' if test_callback('nact:kom_check:2', user_id=2, chat_id=-100200, desc='nact') else '[FAIL]'} nact")

bot.games.clear()

print(f"\n{'='*50}")
print(f"Total errors: {len(errors)}")
for e in errors:
    print(f"  {e}")
print(f"{'='*50}")
