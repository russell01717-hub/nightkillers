"""
Comprehensive tests for modular mafia_bot/ package (aiogram 3.x).
Tests all roles, game mechanics, economy, models, and night actions.
"""

import sys, os, random
sys.path.insert(0, r"D:\pylibs")
os.environ["BOT_TOKEN"] = "8928310354:AAHQ_jAuUqxfWH3Zz5NRAyqBs9YnShmo2CQ"

from mafia_bot.roles import (
    Role, ROLE_ICON, ROLE_TEAM, ROLE_DESC, ROLE_PRICES, IS_NIGHT_ACTIVE,
    distribute_roles, ActionPriority, TOWN_ROLES, MAFIA_ROLES, NEUTRAL_ROLES
)
from mafia_bot.models import MafiaGame, Player, games, GamePhase
from mafia_bot.db import get_db, init_db
from mafia_bot.economy import get_shop_text, buy_role, get_role_price
from mafia_bot.game_engine import check_winner, make_game_banner, make_player_card, validate_callback
from mafia_bot.config import MIN_PLAYERS, MAX_PLAYERS, NIGHT_TIME, DAY_TIME

passed = 0
failed = 0
errors = []

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [OK] {name}")
    except Exception as e:
        failed += 1
        import traceback
        tb = traceback.format_exc()
        errors.append(f"[FAIL] {name}: {e}")
        print(f"  [FAIL] {name}: {e}")
        # Print short traceback
        for line in tb.split("\n")[-4:]:
            if line.strip():
                print(f"         {line.strip()}")

def setup_game(player_count, phase=GamePhase.WAITING, day=0):
    game = MafiaGame(chat_id=-1000000 - player_count)
    game.phase = phase
    game.day = day
    for i in range(player_count):
        game.players[i] = Player(
            user_id=i, name=f"P{i}", username=f"user{i}"
        )
    return game


# ═══════════════════════════════════
print("=" * 60)
print("  MODULAR MAFIA BOT v5.0 - FULL TEST")
print("=" * 60)

# ── 1. ROLES ──
print("\n--- ROLES ---")

def test_all_roles_defined():
    assert len(Role) >= 40, f"Expected 40+ roles, got {len(Role)}"
test("40+ roles defined", test_all_roles_defined)

def test_all_roles_have_icon():
    missing = [r for r in Role if r not in ROLE_ICON]
    assert not missing, f"Missing icons: {missing}"
test("All roles have icons", test_all_roles_have_icon)

def test_all_roles_have_team():
    missing = [r for r in Role if r not in ROLE_TEAM]
    assert not missing, f"Missing teams: {missing}"
test("All roles have teams", test_all_roles_have_team)

def test_all_roles_have_desc():
    missing = [r for r in Role if r not in ROLE_DESC]
    assert not missing, f"Missing descriptions: {missing}"
test("All roles have descriptions", test_all_roles_have_desc)

def test_all_roles_have_price():
    missing = [r for r in Role if r not in ROLE_PRICES]
    assert not missing, f"Missing prices: {missing}"
test("All roles have prices", test_all_roles_have_price)

def test_all_roles_have_night_flag():
    missing = [r for r in Role if r not in IS_NIGHT_ACTIVE]
    assert not missing, f"Missing night flags: {missing}"
test("All roles have night-active flags", test_all_roles_have_night_flag)

def test_more_than_3_town_roles():
    assert len(TOWN_ROLES) >= 10, f"Expected 10+ town roles, got {len(TOWN_ROLES)}"
test("10+ town roles", test_more_than_3_town_roles)

def test_more_than_3_mafia_roles():
    assert len(MAFIA_ROLES) >= 5, f"Expected 5+ mafia roles, got {len(MAFIA_ROLES)}"
test("5+ mafia roles", test_more_than_3_mafia_roles)

def test_more_than_3_neutral_roles():
    assert len(NEUTRAL_ROLES) >= 5, f"Expected 5+ neutral roles, got {len(NEUTRAL_ROLES)}"
test("5+ neutral roles", test_more_than_3_neutral_roles)

def test_teams_are_correct():
    assert ROLE_TEAM[Role.MAFIA] == "mafia"
    assert ROLE_TEAM[Role.DON] == "mafia"
    assert ROLE_TEAM[Role.KOMISSAR] == "town"
    assert ROLE_TEAM[Role.DOKTOR] == "town"
    assert ROLE_TEAM[Role.TINCH] == "town"
    assert ROLE_TEAM[Role.MANIYAK] == "neutral"
    assert ROLE_TEAM[Role.JOKER] == "neutral"
test("Teams correct for base roles", test_teams_are_correct)

def test_distribute_4_players():
    roles = distribute_roles(4)
    assert len(roles) == 4
    assert roles.count(Role.MAFIA) == 1
    assert Role.KOMISSAR in roles
test("distribute_roles(4) -> 1 mafia + komissar + tinch", test_distribute_4_players)

def test_distribute_6_players():
    roles = distribute_roles(6)
    assert len(roles) == 6
    mafia_count = sum(1 for r in roles if r in (Role.MAFIA, Role.DON))
    assert mafia_count >= 1
test("distribute_roles(6)", test_distribute_6_players)

def test_distribute_10_players():
    roles = distribute_roles(10)
    assert len(roles) == 10
    town = [r for r in roles if ROLE_TEAM[r] == "town"]
    mafia = [r for r in roles if ROLE_TEAM[r] == "mafia"]
    neut = [r for r in roles if ROLE_TEAM[r] == "neutral"]
    assert len(mafia) == 3, f"Expected 3 mafia (2 MAFIA + 1 DON), got {len(mafia)}"
    assert len(neut) == 1, f"Expected 1 neutral, got {len(neut)}"
    assert len(town) == 6, f"Expected 6 town, got {len(town)}"
test("distribute_roles(10) -> 3 mafia, 1 neutral, 6 town", test_distribute_10_players)

def test_distribute_16_players():
    roles = distribute_roles(16)
    assert len(roles) == 16
    mafia = [r for r in roles if ROLE_TEAM[r] == "mafia"]
    assert len(mafia) == 4, f"Expected 4 mafia (3 MAFIA + 1 DON), got {len(mafia)}"
test("distribute_roles(16) -> 4 mafia", test_distribute_16_players)

def test_distribute_with_pool():
    pool = [Role.KOMISSAR, Role.DOKTOR, Role.MAFIA, Role.TINCH]
    roles = distribute_roles(4, role_pool=pool)
    assert len(roles) == 4
    assert Role.KOMISSAR in roles
    assert Role.MAFIA in roles
test("distribute_roles with custom pool", test_distribute_with_pool)

def test_distribute_max():
    roles = distribute_roles(100)
    assert len(roles) == 100
test("distribute_roles(100)", test_distribute_max)

def test_action_priority_values():
    assert ActionPriority.TRANSPORT == 1
    assert ActionPriority.KILL == 6
    assert ActionPriority.LAST == 8
test("ActionPriority values", test_action_priority_values)

# ── 2. GAME MODEL ──
print("\n--- GAME MODEL ---")

def test_create_game():
    game = MafiaGame(-100001)
    assert game.phase == GamePhase.WAITING
    assert game.day == 0
    assert len(game.players) == 0
    assert game.chat_id == -100001
test("Create MafiaGame", test_create_game)

def test_add_player():
    game = setup_game(3)
    assert len(game.players) == 3
    assert len(game.alive_players) == 3
test("Add players + alive count", test_add_player)

def test_kill_player():
    game = setup_game(5)
    game.players[0].alive = False
    assert len(game.alive_players) == 4
    assert len(game.dead_players) == 1
test("Kill player, alive/dead counts", test_kill_player)

def test_mafia_players():
    game = setup_game(5)
    game.players[0].team = "mafia"
    game.players[1].team = "mafia"
    assert len(game.mafia_players) == 2
test("Mafia only list", test_mafia_players)

def test_player_display():
    p1 = Player(1, "Alice", "alice99")
    p2 = Player(2, "Bob")
    assert "alice99" in p1.display
    assert "Bob" in p2.display
test("Player display (username vs name)", test_player_display)

def test_player_status_icon():
    p = Player(1, "Test")
    assert p.status_icon() == "🟢"
    p.alive = False
    assert p.status_icon() == "💀"
test("Player status icon", test_player_status_icon)

def test_game_to_dict():
    game = setup_game(3, GamePhase.NIGHT, 2)
    d = game.to_dict()
    assert d["phase"] == GamePhase.NIGHT.value
    assert d["day"] == 2
    assert len(d["players"]) == 3
    assert "chat_id" not in d  # chat_id not serialized
test("Game to_dict", test_game_to_dict)

def test_game_from_dict():
    game = setup_game(3, GamePhase.NIGHT, 2)
    game.players[0].role = Role.KOMISSAR
    d = game.to_dict()
    d["chat_id"] = -999999
    restored = MafiaGame.from_dict(d)
    assert restored.chat_id == -999999
    assert restored.phase == GamePhase.NIGHT
    assert restored.day == 2
    assert len(restored.players) == 3
    assert restored.players[0].role == Role.KOMISSAR
test("Game from_dict round-trip", test_game_from_dict)

def test_player_to_dict():
    p = Player(1, "Test", "testuser")
    p.role = Role.KOMISSAR
    p.team = "town"
    p.hero_attack = 5
    d = p.to_dict()
    assert d["user_id"] == 1
    assert d["role"] == Role.KOMISSAR.value
    assert d["hero_attack"] == 5
test("Player to_dict", test_player_to_dict)

def test_player_from_dict():
    data = {"user_id": 1, "name": "Test", "username": "test", "role": "Komissar",
            "team": "town", "alive": True, "hero_attack": 3, "hero_defense": 5}
    p = Player.from_dict(data)
    assert p.user_id == 1
    assert p.role == Role.KOMISSAR
    assert p.hero_attack == 3
    assert p.hero_defense == 5
test("Player from_dict", test_player_from_dict)

def test_reset_night():
    game = setup_game(3, GamePhase.NIGHT)
    game.mafia_votes = {1: 2}
    game.don_target = 2
    game.reset_night()
    assert game.don_target is None
    assert game.mafia_votes == {}
    for p in game.players.values():
        assert p.protected == False
        assert p.night_target is None
test("reset_night clears targets", test_reset_night)

def test_mafia_votes_received():
    game = setup_game(5, GamePhase.NIGHT)
    game.mafia_votes = {1: 3, 2: 3, 4: 5}
    votes = game.mafia_votes_received
    assert votes.get(3, 0) == 2
    assert votes.get(5, 0) == 1
test("mafia_votes_received count", test_mafia_votes_received)

def test_mafia_votes_with_don():
    game = setup_game(5, GamePhase.NIGHT)
    game.mafia_votes = {1: 3, 2: 5}
    game.don_target = 3
    votes = game.mafia_votes_received
    assert votes[3] == 3  # 1 regular + don double vote
test("mafia_votes_received with Don bonus", test_mafia_votes_with_don)

def test_cancel_timers():
    game = setup_game(5, GamePhase.NIGHT)
    assert game.night_task is None
    assert game.day_task is None
    # When tasks are None, cancel_timers should be a no-op
    game.cancel_timers()
    assert game.night_task is None
    assert game.day_task is None
test("cancel_timers no-op when no tasks", test_cancel_timers)

# ── 3. CHECK WINNER ──
print("\n--- WIN CONDITIONS ---")

def test_win_town():
    game = setup_game(3, GamePhase.MORNING)
    game.players[0].team = "town"
    game.players[1].team = "town"
    game.players[2].team = "town"
    assert check_winner(game) == "town"
test("Town wins (all town alive)", test_win_town)

def test_win_mafia():
    game = setup_game(3, GamePhase.MORNING)
    game.players[0].team = "mafia"
    game.players[1].team = "mafia"
    game.players[2].team = "town"
    assert check_winner(game) == "mafia"
test("Mafia wins (majority)", test_win_mafia)

def test_win_mafia_equal():
    game = setup_game(2, GamePhase.MORNING)
    game.players[0].team = "mafia"
    game.players[1].team = "town"
    assert check_winner(game) == "mafia"
test("Mafia wins (equal count)", test_win_mafia_equal)

def test_win_neutral_maniyak():
    game = setup_game(2, GamePhase.MORNING)
    game.players[0].team = "neutral"
    game.players[0].role = Role.MANIYAK
    game.players[1].team = "neutral"
    game.players[1].alive = False
    assert check_winner(game) == "neutral"
test("Neutral wins (Maniyak last alive)", test_win_neutral_maniyak)

def test_win_neutral_survivor():
    game = setup_game(2, GamePhase.MORNING)
    game.players[0].team = "neutral"
    game.players[0].role = Role.SURVIVOR
    game.players[1].team = "neutral"
    game.players[1].role = Role.JOKER
    game.players[1].alive = True
    assert check_winner(game) == "neutral"
test("Neutral wins (Survivor+Joker)", test_win_neutral_survivor)

def test_no_winner_midgame():
    game = setup_game(4, GamePhase.NIGHT)
    game.players[0].team = "mafia"
    game.players[1].team = "town"
    game.players[2].team = "town"
    game.players[3].team = "neutral"
    assert check_winner(game) is None
test("No winner mid-game", test_no_winner_midgame)

def test_mafia_wins_over_neutral():
    game = setup_game(3, GamePhase.MORNING)
    game.players[0].team = "mafia"
    game.players[1].team = "mafia"
    game.players[2].team = "neutral"
    assert check_winner(game) == "mafia"
test("Mafia wins over neutral", test_mafia_wins_over_neutral)

# ── 4. GAME PHASE TRANSITIONS ──
print("\n--- PHASE TRANSITIONS ---")

def test_phase_values():
    assert GamePhase.WAITING.value == "registration"
    assert GamePhase.NIGHT.value == "night"
    assert GamePhase.VOTING.value == "voting"
    assert GamePhase.ENDED.value == "ended"
test("Phase enum values", test_phase_values)

def test_game_banner_non_empty():
    for phase in GamePhase:
        banner = make_game_banner(phase)
        assert len(banner) > 10, f"Banner empty for {phase}"
test("All phases have banners", test_game_banner_non_empty)

def test_game_banner_with_day():
    banner = make_game_banner(GamePhase.NIGHT, 3)
    assert "3" in banner
test("Banner includes day number", test_game_banner_with_day)

def test_player_card():
    p = Player(1, "Alice")
    card = make_player_card(p)
    assert "Alice" in card
    assert "Alive" in card or "🟢" in card
test("Player card creation", test_player_card)

def test_player_card_dead():
    p = Player(1, "Bob")
    p.alive = False
    card = make_player_card(p)
    assert "💀" in card
test("Player card dead status", test_player_card_dead)

def test_validate_callback_no_game():
    result = validate_callback(None, None)
    assert result is not None
    assert "O'yin topilmadi" in result
test("validate_callback: no game", test_validate_callback_no_game)

def test_validate_callback_wrong_phase():
    game = setup_game(3, GamePhase.WAITING)
    from unittest.mock import MagicMock
    cb = MagicMock()
    cb.from_user.id = 0
    result = validate_callback(cb, game, [GamePhase.NIGHT])
    assert result is not None
test("validate_callback: wrong phase", test_validate_callback_wrong_phase)

def test_validate_callback_not_in_game():
    game = setup_game(3, GamePhase.VOTING)
    from unittest.mock import MagicMock
    cb = MagicMock()
    cb.from_user.id = 999
    result = validate_callback(cb, game, [GamePhase.VOTING], require_alive=True)
    assert result is not None
test("validate_callback: not in game", test_validate_callback_not_in_game)

def test_validate_callback_ok():
    game = setup_game(3, GamePhase.VOTING)
    from unittest.mock import MagicMock
    cb = MagicMock()
    cb.from_user.id = 0
    result = validate_callback(cb, game, [GamePhase.VOTING], require_alive=True)
    assert result is None
test("validate_callback: valid", test_validate_callback_ok)

# ── 5. ECONOMY ──
print("\n--- ECONOMY ---")

def test_get_role_price():
    price = get_role_price(Role.KOMISSAR)
    assert price == 60
test("Komissar price = 60", test_get_role_price)

def test_get_role_price_default():
    price = get_role_price(Role.TINCH)
    assert price == 5
test("Tinch aholi price = 5", test_get_role_price_default)

def test_shop_text_not_empty():
    # This just tests the function doesn't crash
    text = get_shop_text(999999)
    assert len(text) > 20
test("get_shop_text generates output", test_shop_text_not_empty)

# ── 6. ROLE METADATA ──
print("\n--- ROLE METADATA ---")

def test_every_role_icon_unique():
    icons = list(ROLE_ICON.values())
    # Some roles can share icons (e.g. multiple town)
    assert len(set(icons)) >= 20
test("20+ unique role icons", test_every_role_icon_unique)

def test_all_role_names_uzbek():
    names = [r.value for r in Role]
    for name in names:
        assert len(name) > 0
test("All role names non-empty", test_all_role_names_uzbek)

def test_mafia_team_roles():
    for r in Role:
        if ROLE_TEAM[r] == "mafia":
            assert IS_NIGHT_ACTIVE[r] == True or r in (Role.BLACKMAILER, Role.SILENCER, Role.FRAMER, Role.FORGER, Role.JANITOR)
test("Mafia roles are night-active", test_mafia_team_roles)

def test_town_roles_night_active():
    night_town = [r for r in Role if ROLE_TEAM[r] == "town" and IS_NIGHT_ACTIVE[r]]
    assert len(night_town) >= 10
test("10+ town roles have night actions", test_town_roles_night_active)

# ── 7. NIGHT ACTION MODEL ──
print("\n--- NIGHT ACTION MODEL ---")

def test_night_action_fields():
    game = setup_game(5, GamePhase.NIGHT)
    game.mafia_votes = {1: 2}
    game.don_target = 3
    game.komissar_target = 4
    game.doktor_target = 5
    game.maniyak_target = 1
    game.vigilante_target = 2
    game.roleblocker_target = 3
    game.transporter_target1 = 4
    game.transporter_target2 = 5
    game.veteran_active = True
    game.arsonist_targets = [1, 2]
    game.witch_control = {3: 4}
    assert game.maniyak_target == 1
    assert game.vigilante_target == 2
    assert game.veteran_active == True
    assert 1 in game.arsonist_targets
test("All night action fields set/get", test_night_action_fields)

def test_reset_night_clears_all():
    game = setup_game(5, GamePhase.NIGHT)
    game.maniyak_target = 1
    game.vigilante_target = 2
    game.roleblocker_target = 3
    game.transporter_target1 = 4
    game.transporter_target2 = 5
    game.veteran_active = True
    game.arsonist_targets = [1, 2]
    game.witch_control = {3: 4}
    game.reset_night()
    assert game.maniyak_target is None
    assert game.vigilante_target is None
    assert game.roleblocker_target is None
    assert game.transporter_target1 is None
    assert game.transporter_target2 is None
    assert game.veteran_active == False
    assert game.arsonist_targets == []
    assert game.witch_control == {}
test("reset_night clears all night fields", test_reset_night_clears_all)

def test_night_action_serialization():
    game = setup_game(5, GamePhase.NIGHT)
    game.mafia_votes = {1: 2}
    game.don_target = 3
    game.maniyak_target = 4
    game.arsonist_targets = [1, 2, 3]
    game.witch_control = {5: 6}
    d = game.to_dict()
    assert "maniyak_target" in d
    assert d["maniyak_target"] == 4
    assert 1 in d["arsonist_targets"]
    assert "5" in d["witch_control"]
    restored = MafiaGame.from_dict(d)
    assert restored.maniyak_target == 4
    assert restored.arsonist_targets == [1, 2, 3]
    assert restored.witch_control.get(5) == 6
test("Night action serialization round-trip", test_night_action_serialization)

# ── 8. EDGE CASES ──
print("\n--- EDGE CASES ---")

def test_empty_player_list():
    game = MafiaGame(-100000)
    assert len(game.alive_players) == 0
    assert len(game.dead_players) == 0
test("Empty game: alive/dead empty", test_empty_player_list)

def test_get_player_nonexistent():
    game = setup_game(3)
    assert game.get_player(999) is None
test("get_player non-existent returns None", test_get_player_nonexistent)

def test_distribute_min_players():
    roles = distribute_roles(MIN_PLAYERS)
    assert len(roles) == MIN_PLAYERS
test(f"distribute_roles({MIN_PLAYERS})", test_distribute_min_players)

def test_distribute_max_players():
    roles = distribute_roles(MAX_PLAYERS)
    assert len(roles) == MAX_PLAYERS
test(f"distribute_roles({MAX_PLAYERS})", test_distribute_max_players)

def test_mafia_votes_empty():
    game = setup_game(5, GamePhase.NIGHT)
    assert game.mafia_votes_received == {}
test("mafia_votes_received when no votes", test_mafia_votes_empty)

# ── RESULTS ──
print(f"\n{'='*60}")
total = passed + failed
print(f"  TOTAL: {total} tests")
print(f"  PASSED: {passed}")
print(f"  FAILED: {failed}")
if errors:
    print(f"\n  ERRORS:")
    for e in errors:
        print(f"    {e}")
print(f"{'='*60}")

sys.exit(0 if failed == 0 else 1)
