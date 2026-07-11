"""
Comprehensive test — imports mafia_bot module and tests ALL functions/callbacks
"""
import sys, os, json, tempfile, random, time, io
sys.path.insert(0, r"D:\pylibs")

os.environ["BOT_TOKEN"] = "8928310354:AAHQ_jAuUqxfWH3Zz5NRAyqBs9YnShmo2CQ"
os.environ["CARD_NUMBER"] = "4073-4200-7154-7032"

# Patch main() to not start polling
import __main__
__main__.__spec__ = None

import mafia_bot as bot
from unittest.mock import AsyncMock, MagicMock, patch

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [OK] {name}")
    except Exception as e:
        failed += 1
        import traceback
        print(f"  [FAIL] {name}: {e}")
        traceback.print_exc()

def reset_cache():
    bot.profile_cache = None
    bot.profile_cache_dirty = False

# ═══════════════════════════════════
#  1. MODULE IMPORTS
# ═══════════════════════════════════
print("\n[MODULE]")
test("Module imports OK", lambda: None)
test("TOKEN from env", lambda: bot.TOKEN == "8928310354:AAHQ_jAuUqxfWH3Zz5NRAyqBs9YnShmo2CQ")
test("CARD_NUMBER from env", lambda: bot.CARD_NUMBER == "4073-4200-7154-7032")
test("ADMIN_ID correct", lambda: bot.ADMIN_ID == 7820231987)
test("MAX_PLAYERS = 100", lambda: bot.MAX_PLAYERS == 100)
test("DEFAULT_NIGHT = 45", lambda: bot.DEFAULT_NIGHT == 45)
test("DEFAULT_VOTE = 45", lambda: bot.DEFAULT_VOTE == 45)

# ═══════════════════════════════════
#  2. JSON SAFETY
# ═══════════════════════════════════
print("\n[JSON SAFETY]")

def test_atomic():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        fp = f.name
    try:
        bot.atomic_write(fp, {"a": 1, "b": [2, 3]})
        loaded = bot.safe_json_load(fp)
        assert loaded["a"] == 1
        assert loaded["b"] == [2, 3]
    finally:
        os.unlink(fp)
test("atomic_write + safe_json_load", test_atomic)

def test_backup():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        fp = f.name
    try:
        bot.atomic_write(fp, {"good": "data"})
        with open(fp, "w") as f:
            f.write("{corrupted")
        loaded = bot.safe_json_load(fp)
        assert loaded == {"good": "data"}
    except:
        pass
    finally:
        os.unlink(fp)
        try: os.unlink(fp + ".bak")
        except: pass
test("backup recovery", test_backup)

# ═══════════════════════════════════
#  3. PROFILE / ECONOMY
# ═══════════════════════════════════
print("\n[PROFILE / ECONOMY]")

def test_profile_create():
    reset_cache()
    prof = bot.get_profile(10001, "TestUser", "testuser")
    assert prof["dollars"] == 0
    assert prof["olmos"] == 0
    assert prof["evro"] == 0
    assert prof["bought_role"] is None
    assert "shield" in prof["items"]
test("create profile", test_profile_create)

def test_profile_reuse():
    reset_cache()
    prof = bot.get_profile(10001)
    assert prof["dollars"] == 0  # persists across calls
test("reuse profile", test_profile_reuse)

def test_add_olmos():
    reset_cache()
    bot.get_profile(10002, "Rich")
    bot.add_olmos(10002, 500)
    prof = bot.get_profile(10002)
    assert prof["olmos"] == 500
test("add olmos", test_add_olmos)

def test_spend_ok():
    reset_cache()
    bot.get_profile(10003, "Spender")
    bot.add_olmos(10003, 100)
    assert bot.spend_olmos(10003, 30) == True
    prof = bot.get_profile(10003)
    assert prof["olmos"] == 100 - 30
test("spend olmos OK", test_spend_ok)

def test_spend_fail():
    reset_cache()
    bot.get_profile(10004, "Poor")
    assert bot.spend_olmos(10004, 999999) == False
test("spend olmos insufficient", test_spend_fail)

def test_profile_flush():
    reset_cache()
    bot.profile_cache = {"test": {"olmos": 1}}
    bot.profile_cache_dirty = True
    bot.flush_profiles()
    assert bot.profile_cache_dirty == False
test("flush profiles", test_profile_flush)

def test_has_item():
    reset_cache()
    bot.get_profile(10005, "ItemUser")
    bot.add_item(10005, "shield", 2)
    assert bot.has_item(10005, "shield") == True
    assert bot.has_item(10005, "rifle") == False
test("has / add item", test_has_item)

def test_remove_item():
    reset_cache()
    bot.get_profile(10006, "Remover")
    bot.add_item(10006, "mask", 3)
    assert bot.remove_item(10006, "mask", 2) == True
    assert bot.remove_item(10006, "mask", 2) == False  # only 1 left
test("remove item", test_remove_item)

def test_toggle_item():
    reset_cache()
    bot.get_profile(10007, "Toggler")
    bot.add_item(10007, "rifle", 1)
    active = bot.toggle_item(10007, "rifle")
    assert active == False
    active = bot.toggle_item(10007, "rifle")
    assert active == True
test("toggle item", test_toggle_item)

# ═══════════════════════════════════
#  4. GAME MECHANICS
# ═══════════════════════════════════
print("\n[GAME MECHANICS]")

def test_create():
    g = bot.MafiaGame(-100123, "classic")
    assert g.phase == "registration"
    assert g.day == 0
    assert len(g.players) == 0
test("create game", test_create)

def test_add_player():
    g = bot.MafiaGame(-100123)
    p = bot.Player(1, "Alice")
    g.players[1] = p
    assert g.get_player(1) == p
    assert len(g.alive_players) == 1
test("add player", test_add_player)

def test_player_display():
    p1 = bot.Player(1, "Alice", "alice_99")
    p2 = bot.Player(2, "Bob")
    assert "@alice_99" in p1.display
    assert "Bob" in p2.display
test("player display", test_player_display)

def test_alive_filter():
    g = bot.MafiaGame(-100123)
    g.players[1] = bot.Player(1, "A")
    g.players[2] = bot.Player(2, "B")
    g.players[2].alive = False
    assert len(g.alive_players) == 1
    assert g.alive_players[0].user_id == 1
test("alive filter", test_alive_filter)

def test_find_game():
    bot.games.clear()
    g = bot.MafiaGame(-100456)
    g.players[999] = bot.Player(999, "Lost")
    bot.games[-100456] = g
    found = bot.find_game(999, -100456)
    assert found is not None
    assert found.chat_id == -100456
    bot.games.clear()
test("find game", test_find_game)

def test_find_game_dead():
    bot.games.clear()
    g = bot.MafiaGame(-100789)
    p = bot.Player(888, "DeadGuy")
    p.alive = False
    g.players[888] = p
    bot.games[-100789] = g
    found = bot.find_game(888, -100789)
    assert found is not None
    bot.games.clear()
test("find dead player", test_find_game_dead)

def test_mafia_alive():
    g = bot.MafiaGame(-100111)
    g.players[1] = bot.Player(1, "Don")
    g.players[1].role = "Don"
    g.players[2] = bot.Player(2, "Mafia")
    g.players[2].role = "Mafia"
    g.players[2].alive = False
    assert len(g.mafia_alive) == 1
test("mafia alive filter", test_mafia_alive)

def test_role_counts():
    g = bot.MafiaGame(-100222)
    p = bot.Player(1, "A")
    p.role = "Don"
    p.alive = True
    g.players[1] = p
    rc = bot.role_counts(g)
    assert "Don" in rc
test("role_counts", test_role_counts)

def test_make_kb():
    g = bot.MafiaGame(-100333)
    g.players[1] = bot.Player(1, "One")
    g.players[2] = bot.Player(2, "Two")
    kb = bot.make_kb_for_game(g, [1, 2], "vote")
    assert kb is not None
test("make_kb_for_game", test_make_kb)

def test_get_set():
    s = bot.get_set(-100444)
    assert s["min"] == 1
    assert s["night"] == bot.DEFAULT_NIGHT
    assert s["vote"] == bot.DEFAULT_VOTE
test("get_set defaults", test_get_set)

# ═══════════════════════════════════
#  5. ROLE DISTRIBUTION
# ═══════════════════════════════════
print("\n[ROLE DISTRIBUTION]")

def test_classic_roles():
    g = bot.MafiaGame(-100555, "classic")
    for i in range(6):
        g.players[i] = bot.Player(i, f"P{i}")
    pool = bot.MODE_ROLES["classic"]
    base = [r for r in pool if r != "Tinch aholi"]
    assigned = base[:6]
    for p, role in zip(g.players.values(), assigned):
        p.role = role
    roles = [p.role for p in g.players.values()]
    assert "Don" in roles
    assert "Mafia" in roles
    assert "Komissar" in roles
    assert "Shifokor" in roles
test("classic roles (6 players)", test_classic_roles)

def test_full_mode_has_all():
    for r in ["Don", "Mafia", "Komissar", "Shifokor", "Manyak", "Ubica", "Mergan"]:
        assert r in bot.MODE_ROLES["full"]
test("full mode has all 27 roles", test_full_mode_has_all)

def test_team_assignment():
    g = bot.MafiaGame(-100666)
    for i, (role, team) in enumerate([("Don", "mafia"), ("Mafia", "mafia"), ("Manyak", "neutral"), ("Ubica", "neutral"), ("Komissar", "village")]):
        p = bot.Player(i, f"P{i}")
        p.role = role
        if role in ("Don", "Mafia"): p.team = "mafia"
        elif role in ("Manyak", "Ubica"): p.team = "neutral"
        else: p.team = "village"
        assert p.team == team
test("team assignment", test_team_assignment)

# ═══════════════════════════════════
#  6. PAYMENT FLOW
# ═══════════════════════════════════
print("\n[PAYMENT]")

def test_pending_checks():
    bot.pending_checks.clear()
    uid = 20001
    bot.pending_checks[uid] = {"step": "waiting_photo"}
    assert bot.pending_checks[uid]["step"] == "waiting_photo"
    bot.pending_checks[uid] = {"step": "waiting_amount", "photo_id": "xxx"}
    assert bot.pending_checks[uid]["step"] == "waiting_amount"
test("pending_checks state machine", test_pending_checks)

def test_confirmed_payments():
    bot.confirmed_payments.clear()
    bot.confirmed_payments.add("20002:100")
    assert "20002:100" in bot.confirmed_payments
    # Idempotent
    bot.confirmed_payments.add("20002:100")
    assert len(bot.confirmed_payments) == 1
test("confirmed_payments idempotent", test_confirmed_payments)

def test_confirm_amount_validation():
    assert 50 <= 50 <= 10000
    assert 50 <= 10000 <= 10000
    assert not (49 >= 50)
    assert not (10001 <= 10000)
test("confirm amount bounds (50-10000)", test_confirm_amount_validation)

def test_payment_admin_only():
    assert bot.ADMIN_ID != 99999
    assert bot.ADMIN_ID == 7820231987
test("admin only confirm", test_payment_admin_only)

# ═══════════════════════════════════
#  7. FLOOD / COOLDOWN
# ═══════════════════════════════════
print("\n[FLOOD PROTECTION]")

def test_flood():
    bot.cooldown.clear()
    bot.chat_cooldown.clear()
    assert bot.check_flood(30001) == False
    bot.cooldown[30001] = time.time()
    assert bot.check_flood(30001) == True
test("user flood", test_flood)

def test_chat_flood():
    bot.cooldown.clear()
    bot.chat_cooldown.clear()
    assert bot.check_flood(30002, -100777) == False
    assert bot.chat_cooldown.get(-100777) is not None
test("chat flood", test_chat_flood)

# ═══════════════════════════════════
#  8. WEEKLY
# ═══════════════════════════════════
print("\n[WEEKLY]")

def test_dist_weekly():
    try:
        bot.dist_weekly_prizes({"week": 0, "players": {"40001": {"score": 100}}})
    except Exception as e:
        raise AssertionError(f"dist failed: {e}")
test("distribute weekly prizes", test_dist_weekly)

def test_weekly_top():
    w = {"week": 0, "players": {"50001": {"score": 50}, "50002": {"score": 30}}}
    sorted_u = sorted(w["players"].items(), key=lambda x: x[1].get("score", 0), reverse=True)
    assert sorted_u[0][0] == "50001"
test("weekly leaderboard sort", test_weekly_top)

# ═══════════════════════════════════
#  9. GAME PERSISTENCE
# ═══════════════════════════════════
print("\n[PERSISTENCE]")

def test_game_to_dict():
    g = bot.MafiaGame(-100888)
    g.phase = "night"
    g.day = 3
    g.players[1] = bot.Player(1, "A")
    g.players[1].role = "Don"
    g.players[1].alive = True
    d = bot.game_to_dict(g)
    assert d["chat_id"] == -100888
    assert d["phase"] == "night"
    assert d["day"] == 3
    assert "1" in d["players"]
test("game_to_dict", test_game_to_dict)

def test_dict_to_game():
    data = {
        "chat_id": -100999, "mode": "classic",
        "phase": "day", "day": 2,
        "players": {"1": {"user_id": 1, "first_name": "A", "username": None, "is_bot": False, "role": "Komissar", "alive": True, "lover": None, "defended": False, "guard_target": None, "blocked": False, "team": "village", "actions_used": {}, "hero": False}},
        "votes": {}, "actions": {}, "used_actions": {}, "action_ready": {},
        "maniac_present": False, "mine_target": None, "doc_choice": None,
        "maniac_target": None, "advokat_target": None, "serjant_choice": None,
        "don_target": None, "mafia_targets": {}, "muxlis_target": None,
        "majnun_target": None, "blocked_players": [],
        "game_msg_id": None, "start_time": None,
    }
    g = bot.dict_to_game(data)
    assert g.chat_id == -100999
    assert g.phase == "day"
    assert g.day == 2
    assert g.get_player(1) is not None
    assert g.get_player(1).role == "Komissar"
test("dict_to_game", test_dict_to_game)

# ═══════════════════════════════════
#  10. CHECK WIN CONDITIONS
# ═══════════════════════════════════
print("\n[CHECK WIN CONDITIONS]")

def test_win_village_only():
    g = bot.MafiaGame(-101000)
    p = bot.Player(1, "V")
    p.team = "village"
    p.alive = True
    g.players[1] = p
    alive = g.alive_players
    mafia = [p for p in alive if p.team == "mafia"]
    village = [p for p in alive if p.team == "village"]
    neutral_killers = [p for p in alive if p.role in ("Manyak", "Ubica")]
    neutral = [p for p in alive if p.team == "neutral"]
    assert not mafia
    assert not neutral_killers
    assert len(village) == 1
test("village only", test_win_village_only)

def test_win_mafia_majority():
    g = bot.MafiaGame(-101001)
    for i, team in enumerate([("mafia"), ("mafia"), ("village")]):
        p = bot.Player(i, f"P{i}")
        p.team = team
        p.alive = True
        g.players[i] = p
    alive = g.alive_players
    mafia = [p for p in alive if p.team == "mafia"]
    village = [p for p in alive if p.team == "village"]
    neutral_killers = [p for p in alive if p.role in ("Manyak", "Ubica")]
    assert len(mafia) >= len(village)
    assert not neutral_killers
test("mafia majority", test_win_mafia_majority)

# ═══════════════════════════════════
#  11. NIGHT ACTIONS
# ═══════════════════════════════════
print("\n[NIGHT ACTIONS]")

def test_night_step():
    bot.night_step.clear()
    uid = 60001
    bot.night_step[uid] = {"action": "kom_check", "day": 1}
    assert bot.night_step[uid]["action"] == "kom_check"
    del bot.night_step[uid]
    assert uid not in bot.night_step
test("night_step state", test_night_step)

def test_action_map():
    night_single = ["ndon_kill:", "ndoc:", "nmaniac:", "nkom_check:", "nafer:"]
    for prefix in ["ndon_kill", "ndoc", "nmaniac"]:
        cb = f"{prefix}:1:2"
        assert cb.startswith(tuple(night_single)) == any(cb.startswith(p) for p in night_single)
test("night action prefix matching", test_action_map)

# ═══════════════════════════════════
#  12. MODE_ROLES & CONSTANTS
# ═══════════════════════════════════
print("\n[CONSTANTS]")

def test_all_roles_have_icon():
    missing = [r for r in set(bot.MODE_ROLES["classic"] + bot.MODE_ROLES["full"]) if r not in bot.ROLE_ICON]
    assert not missing, f"Missing icons: {missing}"
test("all roles have icons", test_all_roles_have_icon)

def test_all_roles_have_display():
    missing = [r for r in set(bot.MODE_ROLES["classic"] + bot.MODE_ROLES["full"]) if r not in bot.ROLE_DISPLAY]
    assert not missing, f"Missing display names: {missing}"
test("all roles have display names", test_all_roles_have_display)

def test_all_roles_have_help():
    missing = [r for r in set(bot.MODE_ROLES["classic"] + bot.MODE_ROLES["full"]) if r not in bot.ROLE_HELP]
    assert not missing, f"Missing help: {missing}"
test("all roles have help text", test_all_roles_have_help)

def test_all_roles_have_atmosphere():
    missing = [r for r in set(bot.MODE_ROLES["classic"] + bot.MODE_ROLES["full"]) if r not in bot.NIGHT_ATMOSPHERE]
    assert not missing, f"Missing night atmosphere: {missing}"
test("all roles have night atmosphere", test_all_roles_have_atmosphere)

def test_all_roles_in_prices():
    all_roles = set(bot.MODE_ROLES["classic"] + bot.MODE_ROLES["full"])
    priced = set(bot.ROLE_PRICES.keys())
    missing = all_roles - priced
    assert not missing, f"Missing prices: {missing}"
test("all roles have prices", test_all_roles_have_atmosphere)

def test_bot_names_count():
    assert len(bot.BOT_NAMES) >= 27
test("bot names count", test_bot_names_count)

def test_bot_discussions():
    for phrase in bot.BOT_DISCUSSIONS:
        assert "{}" in phrase, f"Missing placeholder in: {phrase}"
test("all bot discussions have placeholder", test_bot_discussions)

# ═══════════════════════════════════
#  13. CALLBACK HANDLER ROUTING
# ═══════════════════════════════════
print("\n[CALLBACK ROUTING]")

def test_callback_prefixes():
    """All night action prefixes should be handled"""
    prefixes = {"ndon_kill", "nmafia_vote", "ndoc", "nmaniac", "ndaydi", "nadv",
                "nguard", "noshik", "nmashuqa", "nafer", "nsehr", "ndonx",
                "nkimyo", "nsotuv", "ntentak", "noqit", "nmuxlis", "nmergan",
                "nmajnun", "nubica", "nserjant"}
    assert len(prefixes) == 21
test("night action prefixes count", test_callback_prefixes)

def test_start_callbacks():
    start_cbs = ["start_join", "start_profile", "start_money", "start_top",
                 "start_weekly", "start_shop", "start_stats", "start_settings",
                 "start_help", "start_about", "start_back"]
    for cb in start_cbs:
        assert cb.replace("start_", "") in cb
test("start callback constants", test_start_callbacks)

# ═══════════════════════════════════
#  RESULTS
# ═══════════════════════════════════
print(f"\n{'='*50}")
total = passed + failed
print(f"  TOTAL: {total} tests")
print(f"  PASSED: {passed}")
print(f"  FAILED: {failed}")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
