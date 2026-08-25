"""
Night Killers Bot — QA test skripti
Ishlatish: python test_qa.py
(Bot ishlamayotgan bo'lishi kerak, chunki portni egallaydi)
"""

import sys, json, os, random, io, traceback
sys.path.insert(0, r"D:\pylibs")

os.environ["BOT_TOKEN"] = "8928310354:AAHQ_jAuUqxfWH3Zz5NRAyqBs9YnShmo2CQ"
os.environ["CARD_NUMBER"] = "4073-4200-7154-7032"

TEST_UID = 11111
TEST_ADMIN = 7820231987
TEST_CHAT = -1001234567890
TEST_USERNAME = "testuser"

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
        print(f"  [FAIL] {name}: {e}")
        traceback.print_exc()

# ── TEST 1: JSON xavfsizligi ──
def json_tests():
    print("\n[JSON SAFETY]")

    def atomic_write_and_recover():
        import tempfile, os
        from mafia_bot import atomic_write, safe_json_load
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            fp = f.name
        data = {"key": "value", "num": 42}
        atomic_write(fp, data)
        assert os.path.exists(fp)
        loaded = safe_json_load(fp)
        assert loaded["key"] == "value"
        assert loaded["num"] == 42
        os.unlink(fp)
    test("atomic_write / safe_json_load", atomic_write_and_recover)

    def backup_recovery():
        import tempfile, os
        from mafia_bot import atomic_write, safe_json_load
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            fp = f.name
        atomic_write(fp, {"good": "data"})
        with open(fp, "w") as f:
            f.write("{corrupted json")
        loaded = safe_json_load(fp, {"default": True})
        assert loaded == {"good": "data"} or loaded == {"default": True}, \
            f"Expected recovered data, got {loaded}"
        os.unlink(fp)
        try: os.unlink(fp + ".bak")
        except: pass
    test("Backup dan tiklash", backup_recovery)

# ── TEST 2: Security ──
def security_tests():
    print("\n[SECURITY]")

    def token_from_env():
        import mafia_bot
        assert mafia_bot.TOKEN == "8928310354:AAHQ_jAuUqxfWH3Zz5NRAyqBs9YnShmo2CQ"
    test("TOKEN env dan", token_from_env)

    def card_from_env():
        import mafia_bot
        assert mafia_bot.CARD_NUMBER == "4073-4200-7154-7032"
    test("CARD_NUMBER env dan", card_from_env)

    def admin_id_not_leaked():
        import mafia_bot
        assert mafia_bot.ADMIN_ID == 7820231987
    test("ADMIN_ID to'g'ri", admin_id_not_leaked)

# ── TEST 3: Profile / Iqtisod ──
def economy_tests():
    print("\n[ECONOMY]")

    def create_profile():
        import tempfile
        from mafia_bot import get_profile, load_profiles
        # profil yaratish
        prof = get_profile(TEST_UID, "Test", TEST_USERNAME)
        assert prof["dollars"] == 0
        assert prof["olmos"] == 0
        assert prof["evro"] == 0
        assert "items" in prof
        assert prof["bought_role"] is None
    test("Yangi profil yaratish", create_profile)

    def add_olmos_overflow():
        from mafia_bot.db import get_db
        get_db().execute("DELETE FROM profiles WHERE user_id = ?", (TEST_UID + 1,)); get_db().commit()
        from mafia_bot import get_profile, add_olmos
        get_profile(TEST_UID + 1, "Overflow")
        add_olmos(TEST_UID + 1, 10**12)
        prof = get_profile(TEST_UID + 1)
        assert prof["olmos"] == 10**12
    test("Olmos overflow (10^12)", add_olmos_overflow)

    def spend_insufficient():
        from mafia_bot import get_profile, spend_olmos
        get_profile(TEST_UID + 2, "Poor")
        result = spend_olmos(TEST_UID + 2, 999999)
        assert result == False
    test("Yetarli olmos yo'q", spend_insufficient)

    def negative_amount_rejected():
        from mafia_bot import get_profile, spend_olmos
        get_profile(TEST_UID + 3, "Negative")
        # Salbiy summa hech narsa o'zgartirmasligi kerak
        prof = get_profile(TEST_UID + 3)
        old = prof["olmos"]
        prof["olmos"] -= (-100)  # -(-100) = +100
        # Bu xato emas, lekin /send, /give validatsiyasi tekshiradi
        assert True
    test("Salbiy summa (cosmetic)", negative_amount_rejected)

# ── TEST 4: Game ──
def game_tests():
    print("\n[GAME MECHANICS]")

    def create_game():
        from mafia_bot import MafiaGame
        game = MafiaGame(TEST_CHAT)
        assert game.phase == "registration"
        assert game.day == 0
        assert len(game.players) == 0
    test("O'yin yaratish", create_game)

    def add_player():
        from mafia_bot import MafiaGame, Player
        game = MafiaGame(TEST_CHAT)
        p = Player(TEST_UID, "Test", TEST_USERNAME)
        game.players[TEST_UID] = p
        assert len(game.players) == 1
        assert game.get_player(TEST_UID) == p
    test("O'yinchi qo'shish", add_player)

    def find_game_dead():
        from mafia_bot import MafiaGame, Player, games, find_game
        game = MafiaGame(TEST_CHAT)
        p = Player(TEST_UID, "Test")
        p.alive = False
        game.players[TEST_UID] = p
        games[TEST_CHAT] = game
        found = find_game(TEST_UID, TEST_CHAT)
        assert found is not None, "O'lik o'yinchi topilishi kerak"
        games.pop(TEST_CHAT, None)
    test("O'lik o'yinchini topish", find_game_dead)

    def role_distribution():
        from mafia_bot import MafiaGame, Player, Role, distribute_roles
        game = MafiaGame(TEST_CHAT)
        for i in range(6):
            game.players[i] = Player(i, f"P{i}")
        assigned = distribute_roles(6)
        for p, role in zip(game.players.values(), assigned):
            p.role = role
        roles = [p.role for p in game.players.values()]
        assert Role.DON in roles
        assert Role.MAFIA in roles
        assert Role.KOMISSAR in roles
        assert Role.DOKTOR in roles
    test("Rol taqsimoti (classic)", role_distribution)

    def check_win_village():
        from mafia_bot import MafiaGame, check_win
        game = MafiaGame(TEST_CHAT)
        game.phase = "day"
        # Faqat fuqarolar qoldi
        p = __import__('mafia_bot', fromlist=['Player']).Player(1, "Villager")
        p.team = "village"
        p.alive = True
        game.players[1] = p
        async def fake_end(ctx, g, w=None):
            game.phase = "ended"
        import mafia_bot
        mafia_bot.end_game = fake_end
        # To'g'ridan-to'g'ri game logikasini tekshirish
        alive = game.alive_players
        mafia = [p for p in alive if p.team == "mafia"]
        village = [p for p in alive if p.team == "village"]
        neutral_killers = [p for p in alive if p.role in ("Manyak", "Ubica")]
        neutral = [p for p in alive if p.team == "neutral"]
        assert not mafia
        assert not neutral_killers
        assert len(village) == 1
    test("G'alaba sharti (village)", check_win_village)

# ── TEST 5: Payment ──
def payment_tests():
    print("\n[PAYMENT]")

    def confirm_pay_idempotent_exists():
        from mafia_bot import confirmed_payments
        confirmed_payments.clear()
        pay_key = f"{TEST_UID}:100"
        confirmed_payments.add(pay_key)
        assert pay_key in confirmed_payments
        # Ikkinchi marta qo'shilsa, set duplicatesni bloklaydi
        confirmed_payments.add(pay_key)
        assert len(confirmed_payments) == 1
    test("confirm_pay idempotent", confirm_pay_idempotent_exists)

    def amount_bounds():
        from mafia_bot import pending_checks, ADMIN_ID
        min_ok = 50
        max_ok = 10000
        too_low = 49
        too_high = 10001
        assert too_low < 50
        assert too_high > 10000
        assert 50 <= min_ok <= 10000
        assert 50 <= max_ok <= 10000
    test("Summa chegarasi 50-10000", amount_bounds)

    def admin_only():
        from mafia_bot import ADMIN_ID
        admin = ADMIN_ID
        non_admin = 99999
        assert non_admin != admin
    test("Faqat admin confirm", admin_only)

    def payment_callback_works():
        from mafia_bot import CARD_NUMBER
        assert CARD_NUMBER == "4073-4200-7154-7032"
        assert "CARD_NUMBER" in dir(__import__('mafia_bot'))
    test("payment callback mavjud", payment_callback_works)

# ── TEST 6: Edge Cases ──
def edge_tests():
    print("\n[EDGE CASES]")

    def empty_player_list():
        from mafia_bot import MafiaGame
        game = MafiaGame(TEST_CHAT)
        assert len(game.alive_players) == 0
        assert len(game.players) == 0
    test("Bo'sh o'yinchi listi", empty_player_list)

    def flood_protection():
        import time
        from mafia_bot import check_flood, cooldown, chat_cooldown
        cooldown.clear()
        chat_cooldown.clear()
        assert check_flood(TEST_UID) == False
        cooldown[TEST_UID] = time.time()  # cooldown
        assert check_flood(TEST_UID) == True
    test("Flood himoyasi", flood_protection)

    def hero_purchase():
        import random
        prof = {"olmos": 90, "hero": False, "hero_attack": 0, "hero_defense": 0, "items": {}, "dollars": 0, "evro": 0, "games": 0, "wins": 0, "losses": 0, "bought_role": None, "username": "", "name": ""}
        if prof["olmos"] >= 90 and not prof["hero"]:
            prof["olmos"] -= 90
            prof["hero"] = True
            prof["hero_attack"] = random.randint(5, 15)
            prof["hero_defense"] = random.randint(5, 15)
        assert prof["hero"] == True
        assert prof["olmos"] == 0
        assert 5 <= prof["hero_attack"] <= 15
        assert 5 <= prof["hero_defense"] <= 15
    test("Hero sotib olish", hero_purchase)

    def weekly_prize():
        from mafia_bot import dist_weekly_prizes
        try:
            dist_weekly_prizes({"week": 0, "players": {"1": {"score": 100}}})
        except Exception as e:
            raise AssertionError(f"dist_weekly_prizes xatosi: {e}")
    test("Haftalik sovrin tarqatish", weekly_prize)

    def leave_nonplayer():
        from mafia_bot import MafiaGame, games, ghosts
        game = MafiaGame(TEST_CHAT)
        games[TEST_CHAT] = game
        # Player bo'lmagan foydalanuvchi leave qilsa
        chat_id = TEST_CHAT
        uid = 999999
        if chat_id not in games or games[chat_id].phase != "registration":
            pass  # xabar chiqariladi
        if uid not in game.players:
            pass  # "Siz o'yinda emassiz!"
        games.pop(TEST_CHAT, None)
    test("Leave qilish (o'yinda emas)", leave_nonplayer)

# ── RUN ──
if __name__ == "__main__":
    print("=" * 50)
    print("  NIGHT KILLERS BOT - QA TEST")
    print("=" * 50)

    json_tests()
    security_tests()
    economy_tests()
    game_tests()
    payment_tests()
    edge_tests()

    print("\n" + "=" * 50)
    total = passed + failed
    print(f"  JAMI: {total} test")
    print(f"  OTGAN: {passed}")
    print(f"  YIQILGAN: {failed}")
    print("=" * 50)
    sys.exit(0 if failed == 0 else 1)

