"""Core game engine — phases, priority-based night/day resolution, win checks, UI"""

import asyncio
import logging
import random
from typing import Optional, List, Dict, Tuple

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import MafiaGame, Player, games, GamePhase
from .roles import (
    Role, ROLE_ICON, ROLE_DISPLAY, ROLE_DESC, ROLE_TEAM, IS_NIGHT_ACTIVE,
    ROLE_PRIORITY_MAP, ActionPriority,
)
from .config import NIGHT_TIME, DAY_TIME, MORNING_WAIT
from .db import (
    get_profile, save_profile, update_weekly_score,
    delete_active_game, get_chat_setting,
    update_elo, expected_score, unlock_achievement, log_anticheat,
)
from .economy import game_reward

log = logging.getLogger("MafiaBot.Game")


def safe(coro):
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
            role_icon = ROLE_ICON.get(p.role, "") if p.role and show_roles else ""
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


def make_game_banner(phase: GamePhase, day: int = 0) -> str:
    banners = {
        GamePhase.WAITING: ("═══════════════════════════════════\n"
                            "💀 <b>NIGHT KILLERS</b> 💀\n"
                            "═══════════════════════════════════"),
        GamePhase.NIGHT: ("╔══════════════════════════════════╗\n"
                          "║         🌙 TUN FAZASI 🌙          ║\n"
                          "╚══════════════════════════════════╝"),
        GamePhase.MORNING: ("╔══════════════════════════════════╗\n"
                            "║        🌅 TONG OTD! 🌅            ║\n"
                            "╚══════════════════════════════════╝"),
        GamePhase.VOTING: ("╔══════════════════════════════════╗\n"
                           "║       🗳 OVOZ BERISH 🗳           ║\n"
                           "╚══════════════════════════════════╝"),
        GamePhase.EXECUTION: ("╔══════════════════════════════════╗\n"
                              "║       ⚖️ NATIJA ⚖️              ║\n"
                              "╚══════════════════════════════════╝"),
        GamePhase.ENDED: ("╔══════════════════════════════════╗\n"
                          "║        🏆 O'YIN TUGADI 🏆        ║\n"
                          "╚══════════════════════════════════╝"),
        GamePhase.STARTING: ("╔══════════════════════════════════╗\n"
                             "║      🚀 O'YIN BOSHLANDI 🚀       ║\n"
                             "╚══════════════════════════════════╝"),
        GamePhase.ROLE_ASSIGN: ("╔══════════════════════════════════╗\n"
                                "║   🎭 ROLLAR TARQATILMOQDA 🎭    ║\n"
                                "╚══════════════════════════════════╝"),
    }
    banner = banners.get(phase, "═══════════════════════════════════")
    if day > 0:
        banner += f"\n📅 <b>{day}-kun / {day}-tun</b>"
    return banner


def make_player_card(player: Player, show_role: bool = False) -> str:
    team_icon = "🔪" if player.team == "mafia" else ""
    role_line = f"├ {player.role_display}\n" if show_role and player.role else ""
    return (
        f"{'🟢' if player.alive else '💀'} <b>{player.display}</b>\n"
        f"{role_line}"
        f"└ {'Tirik' if player.alive else 'O\'lgan'}"
    )


def check_winner(game: MafiaGame) -> Optional[str]:
    alive = game.alive_players
    mafia_alive = len([p for p in alive if p.team == "mafia"])
    town_alive = len([p for p in alive if p.team == "town"])
    neutral_alive = len([p for p in alive if p.team == "neutral"])
    if neutral_alive >= 1 and mafia_alive + town_alive == 0:
        return "neutral"
    if mafia_alive == 0:
        return "town"
    if mafia_alive >= town_alive + neutral_alive:
        return "mafia"
    return None


def validate_callback(
    callback: CallbackQuery, game: Optional[MafiaGame],
    allowed_phases: Optional[List[GamePhase]] = None,
    require_alive: bool = False,
) -> Optional[str]:
    if game is None:
        return "❌ O'yin topilmadi"
    if allowed_phases and game.phase not in allowed_phases:
        phase_name = getattr(game.phase, 'value', str(game.phase))
        return f"❌ Bu amal {phase_name} fazasida mumkin emas"
    if require_alive:
        player = game.get_player(callback.from_user.id)
        if not player:
            return "❌ Siz o'yinda emassiz"
        if not player.alive:
            return "💀 Siz o'lgansiz"
    return None


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


# ── AFK Detection ──

async def check_afk(game: MafiaGame, bot: Bot):
    for player in game.alive_players:
        if player.is_bot:
            continue
        if player.last_action_round < game.day - 1:
            player.afk_rounds += 1
        if player.afk_rounds >= 2:
            player.alive = False
            await safe_send_message(
                bot, game.chat_id,
                f"💤 <b>{player.display}</b> uzoq vaqt harakatsizlik tufayli o'yindan chiqarildi!"
            )
            log_anticheat(game.chat_id, player.user_id, "AFK > 2 rounds")


# ── Achievements ──

async def check_achievements(game: MafiaGame, winner: str):
    for player in game.players.values():
        if player.is_bot:
            continue
        uid = player.user_id
        profile = get_profile(uid)
        games_count = profile.get("games", 0)
        if games_count == 1 and player.team == winner:
            unlock_achievement(uid, "first_win")
        if games_count == 10:
            unlock_achievement(uid, "arifmetist")
        if games_count == 50:
            unlock_achievement(uid, "veteran")
        if games_count == 100:
            unlock_achievement(uid, "legend")
        if winner == "mafia" and player.team == "mafia":
            unlock_achievement(uid, "mafia_win")
        if winner == "town" and player.team == "town":
            unlock_achievement(uid, "town_win")
        if player.role == Role.JOKER and winner == "neutral":
            unlock_achievement(uid, "joker_win")
        if player.role == Role.MANIYAK and winner == "neutral":
            unlock_achievement(uid, "maniyak_win")
        if player.role == Role.SURVIVOR and player.alive and winner != "neutral":
            unlock_achievement(uid, "survivor_win")


# ── Night Phase ──

async def start_night_phase(game: MafiaGame, bot: Bot):
    game.cancel_timers()
    game.phase = GamePhase.NIGHT
    game.day += 1
    game.reset_night()
    game.log("night_started", f"Day {game.day}")

    mafia_targets = [p for p in game.alive_players if p.team != "mafia"]
    cid = game.chat_id

    for player in game.alive_players:
        role = player.role
        if not role:
            game.action_ready[player.user_id] = True
            continue

        if role == Role.MAFIA and mafia_targets:
            kb = make_players_keyboard(mafia_targets, "nv_kill", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🌙 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.DON and mafia_targets:
            kb = make_players_keyboard(mafia_targets, "nv_don", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🌙 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz? (Sizning ovozingiz hal qiluvchi)",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.GODFATHER and mafia_targets:
            kb = make_players_keyboard(mafia_targets, "nv_kill", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🌙 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz? (Siz rahbarsiz)",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.KOMISSAR:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_check", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🌙 <b>{game.day}-tun</b>\n\nKimni tekshiramiz? 🔍",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.DOKTOR:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_heal", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🌙 <b>{game.day}-tun</b>\n\nKimni davolaymiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.HAMSHIRA:
            targets = [p for p in game.players.values() if not p.alive]
            if targets and game.day > 1:
                kb = make_players_keyboard(targets, "nv_revive", chat_id=cid)
                await safe_send_message(
                    bot, player.user_id,
                    f"🌙 <b>{game.day}-tun</b>\n\nKimni tiriltiramiz? (faqat 1 marta)",
                    reply_markup=kb
                )
                game.action_ready[player.user_id] = False
            else:
                await safe_send_message(bot, player.user_id, f"🌙 Hech kim o'lmagan.")
                game.action_ready[player.user_id] = True
        elif role == Role.MANIYAK:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_maniyak", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🪓 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.VIGILANTE:
            if game.vigilante_bullets <= 0:
                await safe_send_message(bot, player.user_id, f"🔫 O'qlar tugadi!")
                game.action_ready[player.user_id] = True
                continue
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_vigilante", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🔫 <b>{game.day}-tun</b>\n\nKimni otamiz? (Qolgan o'q: {game.vigilante_bullets})",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.TRANSPORTER:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_transport1", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🔄 <b>{game.day}-tun</b>\n\n1-o'yinchini tanlang:",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.SHERIF:
            await safe_send_message(
                bot, player.user_id,
                f"🛡 <b>{game.day}-tun</b>\n\nSiz himoyadasiz."
            )
            game.action_ready[player.user_id] = True
        elif role == Role.ADVOKAT:
            await safe_send_message(
                bot, player.user_id,
                f"⚖️ <b>{game.day}-tun</b>\n\nErtangi kunda himoya qilishingiz mumkin."
            )
            game.action_ready[player.user_id] = True
        elif role == Role.VETERAN:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_veteran", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🎖 <b>{game.day}-tun</b>\n\nHujum rejimiga o'tasizmi?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.QORIQCHI:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_protect", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🛡 <b>{game.day}-tun</b>\n\nKimni himoya qilamiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.JAILOR:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_jail", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"⛓ <b>{game.day}-tun</b>\n\nKimni qamoqqa tashlaymiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.SPY:
            await safe_send_message(
                bot, player.user_id,
                f"🕶 <b>{game.day}-tun</b>\n\nSiz mafiyani eshitasiz..."
            )
            game.action_ready[player.user_id] = True
        elif role in (Role.KUZATUVCHI, Role.IZQUVAR, Role.TERGOVCHI, Role.DETEKTIV,
                      Role.PSIXOLOG, Role.MUHANDIS, Role.ORACLE, Role.PRIEST,
                      Role.CONSIGLIERE):
            prefix_map = {
                Role.KUZATUVCHI: "nv_watch", Role.IZQUVAR: "nv_izquvar",
                Role.TERGOVCHI: "nv_investigate", Role.DETEKTIV: "nv_detective",
                Role.PSIXOLOG: "nv_psychologist", Role.MUHANDIS: "nv_engineer",
                Role.ORACLE: "nv_oracle", Role.PRIEST: "nv_priest",
                Role.CONSIGLIERE: "nv_consigliere",
            }
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, prefix_map[role], chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🌙 <b>{game.day}-tun</b>\n\nKimni tanlaysiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role in (Role.ARSONIST, Role.WITCH, Role.ASSASSIN, Role.BOMBER,
                      Role.POISONER, Role.PROFESSIONAL, Role.ROLEBLOCKER,
                      Role.SILENCER, Role.BLACKMAILER, Role.FRAMER):
            prefix_map2 = {
                Role.ARSONIST: "nv_arsonist", Role.WITCH: "nv_witch",
                Role.ASSASSIN: "nv_assassin", Role.BOMBER: "nv_bomber",
                Role.POISONER: "nv_poisoner", Role.PROFESSIONAL: "nv_professional",
                Role.ROLEBLOCKER: "nv_roleblock", Role.SILENCER: "nv_silence",
                Role.BLACKMAILER: "nv_blackmail", Role.FRAMER: "nv_framer",
            }
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, prefix_map2[role], chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🌙 <b>{game.day}-tun</b>\n\nKimni tanlaysiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.JANITOR:
            targets = [p for p in game.dead_players]
            if targets:
                kb = make_players_keyboard(targets, "nv_janitor", chat_id=cid)
                await safe_send_message(
                    bot, player.user_id,
                    f"🧹 <b>{game.day}-tun</b>\n\nKimning rolini yashiramiz?",
                    reply_markup=kb
                )
                game.action_ready[player.user_id] = False
            else:
                await safe_send_message(bot, player.user_id, f"🌙 Hech kim o'lmagan.")
                game.action_ready[player.user_id] = True
        elif role == Role.FORGER:
            targets = [p for p in game.dead_players]
            if targets:
                kb = make_players_keyboard(targets, "nv_forger", chat_id=cid)
                await safe_send_message(
                    bot, player.user_id,
                    f"✒️ <b>{game.day}-tun</b>\n\nKimning ma'lumotini o'zgartiramiz?",
                    reply_markup=kb
                )
                game.action_ready[player.user_id] = False
            else:
                await safe_send_message(bot, player.user_id, f"🌙 Hech kim o'lmagan.")
                game.action_ready[player.user_id] = True
        elif role == Role.MEDIUM:
            dead_list = "\n".join([f"💀 {p.display}" for p in game.dead_players]) if game.dead_players else "Hech kim o'lmagan"
            await safe_send_message(bot, player.user_id, f"🔮 <b>{game.day}-tun</b>\n\n{dead_list}")
            game.action_ready[player.user_id] = True
        elif role in (Role.JOKER, Role.SURVIVOR, Role.EXECUTIONER):
            msg = {
                Role.JOKER: "🃏 Maqsadingiz — ovoz berish orqali chiqarilish!",
                Role.SURVIVOR: "⛺ Maqsadingiz — tirik qolish!",
                Role.EXECUTIONER: "🪓 Maqsadingiz — bir o'yinchini chiqarilishiga erishish!",
            }[role]
            await safe_send_message(bot, player.user_id, f"🌙 <b>{game.day}-tun</b>\n\n{msg}")
            game.action_ready[player.user_id] = True
        elif role in (Role.TINCH, Role.MER, Role.AMNESIAC):
            await safe_send_message(bot, player.user_id, f"🌙 <b>{game.day}-tun</b>\n\nSiz uxlayapsiz...")
            game.action_ready[player.user_id] = True
        else:
            await safe_send_message(bot, player.user_id, f"🌙 <b>{game.day}-tun</b>\n\nKutib turing...")
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
        log.error(f"Night timer error: {e}")


# ── Priority-Based Night Resolution ──

async def end_night_phase(game: MafiaGame, bot: Bot):
    if game.phase != GamePhase.NIGHT:
        return
    game.log("night_ended", f"Day {game.day}")

    transport_map = {}
    if game.transporter_target1 and game.transporter_target2:
        transport_map[game.transporter_target1] = game.transporter_target2
        transport_map[game.transporter_target2] = game.transporter_target1

    def resolve_target(target: Optional[int]) -> Optional[int]:
        if target and target in transport_map:
            return transport_map[target]
        return target

    roleblocked = set()
    if game.roleblocker_target:
        roleblocked.add(game.roleblocker_target)

    results = {
        "killed": set(),
        "healed": set(),
        "protected": set(),
        "revived": set(),
        "sherif_vengeance": None,
        "investigator_results": [],
    }

    # ── STEP 1: Roleblock & Silence actions (PRIORITY 2-3) ──
    for p in game.players.values():
        if p.user_id in roleblocked:
            p.roleblocked = True
        if p.user_id == game.silencer_target:
            p.silenced = True
        if p.user_id == game.blackmailer_target:
            p.blackmailed = True
        if p.user_id == game.framer_target:
            p.framed = True

    # ── STEP 2: Investigate actions (PRIORITY 4) ──
    if game.komissar_target is not None and game.komissar_target not in roleblocked:
        checked = game.get_player(resolve_target(game.komissar_target))
        if checked:
            is_mafia = checked.team == "mafia"
            if checked.role in (Role.DON, Role.GODFATHER):
                is_mafia = False
            if checked.framed:
                is_mafia = True
            result = "🔴 MAFIA" if is_mafia else "🟢 Tinch aholi"
            for p in game.players.values():
                if p.role == Role.KOMISSAR and p.alive:
                    await safe_send_message(bot, p.user_id, f"🔍 <b>Natija:</b>\n{checked.display}: {result}")
                    unlock_achievement(p.user_id, "komissar_check")

    if game.detective_target is not None and game.detective_target not in roleblocked:
        det = game.get_player(resolve_target(game.detective_target))
        if det:
            is_suspicious = det.team == "mafia"
            if det.role in (Role.DON, Role.GODFATHER):
                is_suspicious = False
            if det.framed:
                is_suspicious = True
            result = "⚖️ Aybdor" if is_suspicious else "✅ Begunoh"
            for p in game.players.values():
                if p.role == Role.DETEKTIV and p.alive:
                    await safe_send_message(bot, p.user_id, f"🕵️ <b>Natija:</b>\n{det.display}: {result}")

    if game.tergovchi_target is not None and game.tergovchi_target not in roleblocked:
        inv = game.get_player(resolve_target(game.tergovchi_target))
        if inv:
            if inv.framed:
                role_info = "🔴 Mafia a'zosi"
            elif inv.team == "mafia":
                role_info = "🔴 Mafia a'zosi"
            elif inv.team == "neutral":
                role_info = "🟣 Mustaqil"
            else:
                role_info = "🟢 Shahar aholisi"
            for p in game.players.values():
                if p.role == Role.TERGOVCHI and p.alive:
                    await safe_send_message(bot, p.user_id, f"📋 <b>Natija:</b>\n{inv.display}: {role_info}")

    if game.consigliere_target is not None and game.consigliere_target not in roleblocked:
        consig = game.get_player(resolve_target(game.consigliere_target))
        if consig:
            for p in game.players.values():
                if p.role == Role.CONSIGLIERE and p.alive:
                    await safe_send_message(bot, p.user_id, f"📜 <b>Natija:</b>\n{consig.display} — {consig.role_display}")

    if game.izquvar_target is not None and game.izquvar_target not in roleblocked:
        izq = game.get_player(resolve_target(game.izquvar_target))
        if izq:
            visited = [p.display for p in game.players.values() if p.night_target == izq.user_id and p.user_id != izq.user_id]
            text = f"🔎 <b>Natija:</b>\n{izq.display} ga: " + (", ".join(visited) if visited else "Hech kim")
            for p in game.players.values():
                if p.role == Role.IZQUVAR and p.alive:
                    await safe_send_message(bot, p.user_id, text)

    if game.kuzatuvchi_target is not None and game.kuzatuvchi_target not in roleblocked:
        wat = game.get_player(resolve_target(game.kuzatuvchi_target))
        if wat:
            visited_by = [p.display for p in game.players.values() if p.night_target == wat.user_id and p.user_id != wat.user_id]
            text = f"👁 <b>Natija:</b>\n{wat.display} ga: " + (", ".join(visited_by) if visited_by else "Hech kim")
            for p in game.players.values():
                if p.role == Role.KUZATUVCHI and p.alive:
                    await safe_send_message(bot, p.user_id, text)

    # ── STEP 3: Protect actions (PRIORITY 5) ──
    if game.doktor_target is not None:
        dt = resolve_target(game.doktor_target)
        if dt not in roleblocked:
            results["healed"].add(dt)
            results["protected"].add(dt)
    if game.hamshira_target is not None:
        ht = resolve_target(game.hamshira_target)
        if ht not in roleblocked:
            results["protected"].add(ht)
    if game.priest_target is not None:
        pt = resolve_target(game.priest_target)
        if pt not in roleblocked:
            results["protected"].add(pt)
    if game.qoriqchi_target is not None:
        qt = resolve_target(game.qoriqchi_target)
        if qt not in roleblocked:
            results["protected"].add(qt)

    # ── STEP 4: Kill actions (PRIORITY 6) ──
    # Mafia kill
    mafia_votes = game.mafia_votes_received
    kill_target = None
    if mafia_votes:
        max_votes = max(mafia_votes.values())
        top_targets = [t for t, v in mafia_votes.items() if v == max_votes]
        kill_target = random.choice(top_targets)
    elif game.don_target is not None:
        kill_target = game.don_target
    elif game.consigliere_target is not None:
        kill_target = game.consigliere_target

    if kill_target is not None and kill_target not in roleblocked:
        kt = resolve_target(kill_target)
        target = game.get_player(kt)
        if target and target.alive:
            if kt in results["protected"]:
                if kt in results["healed"]:
                    results["killed"].discard(kt)
                    game.healed_player = kt
                else:
                    results["killed"].discard(kt)
            else:
                target.alive = False
                results["killed"].add(kt)

    # Maniyak kill
    if game.maniyak_target is not None and game.maniyak_target not in roleblocked:
        mt = resolve_target(game.maniyak_target)
        target = game.get_player(mt)
        if target and target.alive and mt not in results["protected"]:
            target.alive = False
            results["killed"].add(mt)

    # Vigilante kill
    if game.vigilante_target is not None and game.vigilante_target not in roleblocked:
        vt = resolve_target(game.vigilante_target)
        target = game.get_player(vt)
        if target and target.alive and vt not in results["protected"]:
            target.alive = False
            results["killed"].add(vt)
            if target.team != "mafia":
                for p in game.players.values():
                    if p.role == Role.VIGILANTE:
                        p.alive = False
                        unlock_achievement(p.user_id, "vigilante_kill")

    # Professional kill
    if game.professional_target is not None and game.professional_target not in roleblocked:
        pt = resolve_target(game.professional_target)
        target = game.get_player(pt)
        if target and target.alive and pt not in results["protected"]:
            target.alive = False
            results["killed"].add(pt)
            if target.team != "mafia":
                for p in game.players.values():
                    if p.role == Role.PROFESSIONAL:
                        p.alive = False

    # Assassin kill (odd days only)
    if game.assassin_target is not None and game.day % 2 == 1 and game.assassin_target not in roleblocked:
        at = resolve_target(game.assassin_target)
        target = game.get_player(at)
        if target and target.alive and at not in results["protected"]:
            target.alive = False
            results["killed"].add(at)

    # Bomber detonation
    if game.bomber_target is not None and game.bomber_target not in roleblocked:
        bt = resolve_target(game.bomber_target)
        target = game.get_player(bt)
        if target and target.alive and bt not in results["protected"]:
            target.alive = False
            results["killed"].add(bt)

    # Poisoner kill
    if game.poisoner_target is not None and game.poisoner_target not in roleblocked:
        pot = resolve_target(game.poisoner_target)
        target = game.get_player(pot)
        if target and target.alive and pot not in results["protected"]:
            target.alive = False
            results["killed"].add(pot)

    # Arsonist ignite
    if game.arsonist_ignite:
        for uid in game.arsonist_targets:
            target = game.get_player(uid)
            if target and target.alive and uid not in results["protected"]:
                target.alive = False
                results["killed"].add(uid)
        game.arsonist_targets = []

    # ── STEP 5: Vengeful (PRIORITY 7) ──
    sherif_killed = any(game.get_player(k) and game.get_player(k).role == Role.SHERIF for k in results["killed"])
    if sherif_killed:
        mafia_alive = game.mafia_players
        if mafia_alive:
            vengeance_target = random.choice(mafia_alive)
            vengeance_target.alive = False
            results["sherif_vengeance"] = vengeance_target
            for p in game.players.values():
                if p.role == Role.SHERIF:
                    unlock_achievement(p.user_id, "sherif_revenge")

    # Veteran retaliation
    if game.veteran_active:
        for k in list(results["killed"]):
            target = game.get_player(k)
            if target and target.role == Role.VETERAN:
                killer = None
                for p in game.alive_players:
                    if p.team == "mafia":
                        killer = p
                        break
                if killer:
                    killer.alive = False
                    results["killed"].add(killer.user_id)

    # ── STEP 6: Spy info (PRIORITY 4, but needs kill results) ──
    for p in game.players.values():
        if p.role == Role.SPY and p.alive:
            mafia_chat = []
            for mp in game.mafia_players:
                target_info = ""
                if game.mafia_votes.get(mp.user_id):
                    tgt = game.get_player(game.mafia_votes[mp.user_id])
                    if tgt:
                        target_info = f" -> {tgt.display}"
                mafia_chat.append(f"🔪 {mp.display}{target_info}")
            spy_text = "🕶 <b>Mafia:</b>\n" + "\n".join(mafia_chat) if mafia_chat else "Mafia hech narsa qilmadi."
            await safe_send_message(bot, p.user_id, spy_text)

    # Witch control (no-op for now)
    for witch_id, target_id in game.witch_control.items():
        pass

    # ── Morning broadcast ──
    game.phase = GamePhase.MORNING
    death_messages = []

    killed_players = [game.get_player(k) for k in results["killed"] if game.get_player(k)]
    for kp in killed_players:
        if kp:
            death_messages.append(
                f"💀 <b>{kp.display}</b> o'ldirildi! "
                f"({ROLE_ICON.get(kp.role, '❓')} {kp.role.value if kp.role else '?'})"
            )

    if results["sherif_vengeance"]:
        sv = results["sherif_vengeance"]
        death_messages.append(
            f"🛡 Sherif qasosi! <b>{sv.display}</b> o'ldirildi!"
        )

    if game.healed_player and not any(game.get_player(k).user_id == game.healed_player for k in results["killed"] if game.get_player(k)):
        healed = game.get_player(game.healed_player)
        if healed:
            death_messages.append(f"💊 Doktor {healed.display} ni davoladi!")

    if death_messages:
        text = f"{make_game_banner(GamePhase.MORNING, game.day)}\n\n" + "\n".join(death_messages) + "\n\n"
    else:
        text = f"{make_game_banner(GamePhase.MORNING, game.day)}\n\nBu tun hech kim o'lmadi...\n\n"

    alive_list = "\n".join([make_player_card(p) for p in game.alive_players])
    text += f"<b>Tirik ({len(game.alive_players)}):</b>\n{alive_list}\n\n"

    winner = check_winner(game)
    if winner:
        await end_game(game, bot, winner)
        return

    text += f"⏳ Ovoz berish {game.vote_time}s dan keyin..."
    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text)

    game.day_task = asyncio.create_task(morning_timer(game, bot))


async def morning_timer(game: MafiaGame, bot: Bot):
    try:
        await asyncio.sleep(MORNING_WAIT)
        await start_day_phase(game, bot)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"Morning timer error: {e}")


# ── Day Phase ──

async def start_day_phase(game: MafiaGame, bot: Bot):
    if game.phase != GamePhase.MORNING:
        return
    game.phase = GamePhase.VOTING
    game.reset_day()
    game.log("voting_started", f"Day {game.day}")

    await check_afk(game, bot)

    text = (
        f"{make_game_banner(GamePhase.VOTING, game.day)}\n\n"
        f"⏱ {game.vote_time}s\n\n"
        f"<b>Tirik ({len(game.alive_players)}):</b>\n" +
        "\n".join([make_player_card(p) for p in game.alive_players]) +
        "\n\n<b>Kimni chetlatamiz?</b>"
    )

    kb = make_players_keyboard(game.alive_players, "d_vote", chat_id=game.chat_id, columns=2)
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data=f"d_skip:{game.chat_id}")
    ])
    if game.vote_round > 1:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"🔄 Qayta ovoz ({game.vote_round}-tur)", callback_data=f"d_skip:{game.chat_id}")
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
        log.error(f"Day timer error: {e}")


async def end_day_phase(game: MafiaGame, bot: Bot):
    if game.phase != GamePhase.VOTING:
        return
    game.log("voting_ended", f"Day {game.day}")

    votes = {}
    voter_count = 0
    for player in game.alive_players:
        if player.vote is not None and player.vote > 0:
            multiplier = 3 if player.role == Role.MER else 1
            votes[player.vote] = votes.get(player.vote, 0) + multiplier
            voter_count += 1

    # ── Anticheat: vote manipulation ──
    if votes and len(game.alive_players) > 3:
        max_votes = max(votes.values())
        total_voters = sum(1 for p in game.alive_players if p.vote is not None and p.vote > 0)
        if max_votes > total_voters:
            log_anticheat(game.chat_id, 0, f"Suspicious vote count: {max_votes} > {total_voters}")

    eliminated = None
    if votes:
        max_votes = max(votes.values())
        top_voted = [t for t, v in votes.items() if v == max_votes]

        # ── Tie handling ──
        if len(top_voted) > 1:
            if game.vote_round < 3:
                game.vote_round += 1
                text = (
                    f"{make_game_banner(GamePhase.VOTING, game.day)}\n\n"
                    f"⚖️ <b>Ovozlar teng!</b>\n"
                    f"Qayta ovoz berish ({game.vote_round}-tur)\n\n"
                    f"Nomzodlar:\n" +
                    "\n".join([f"• {game.get_player(t).display}" for t in top_voted if game.get_player(t)])
                )
                kb = make_players_keyboard(
                    [p for p in game.alive_players if p.user_id in top_voted],
                    "d_vote", chat_id=game.chat_id, columns=2
                )
                if game.game_msg_id:
                    await safe_edit_message(bot, game.chat_id, game.game_msg_id, text, reply_markup=kb)
                game.cancel_timers()
                game.day_task = asyncio.create_task(day_timer(game, bot))
                return
            else:
                elim_id = random.choice(top_voted)
                eliminated = game.get_player(elim_id)
        else:
            elim_id = top_voted[0]
            eliminated = game.get_player(elim_id)

        if eliminated:
            eliminated.alive = False

    # ── Execution Phase (last words) ──
    game.phase = GamePhase.EXECUTION
    text = f"{make_game_banner(GamePhase.EXECUTION, game.day)}\n\n"

    if eliminated:
        text += (
            f"🗳 <b>{eliminated.display}</b> eng ko'p ovoz oldi!\n"
            f"Rol: {eliminated.role_display}\n\n"
        )
        if eliminated.role == Role.JOKER:
            text += "🃏 Joker yutdi!\n\n"
        if game.advokat_protect == eliminated.user_id:
            eliminated.alive = True
            text += f"⚖️ Advokat {eliminated.display} ni himoya qildi!\n\n"
    else:
        text += "Hech kim chetlatilmadi.\n\n"

    alive_list = "\n".join([make_player_card(p) for p in game.alive_players])
    text += f"<b>Tirik ({len(game.alive_players)}):</b>\n{alive_list}\n\n"

    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text)

    winner = check_winner(game)
    if winner:
        await end_game(game, bot, winner)
        return

    # ── Last words ──
    if eliminated and eliminated.alive == False and eliminated.role != Role.JOKER:
        await safe_send_message(
            bot, eliminated.user_id,
            f"💬 Siz chiqarildingiz! So'nggi so'zingizni yozing (30 soniya):\n"
            f"/lastwords <matn>"
        )
        await asyncio.sleep(3)
        if eliminated.last_words:
            await safe_send_message(
                bot, game.chat_id,
                f"💬 <b>{eliminated.display}</b> ning so'nggi so'zlari:\n{eliminated.last_words}"
            )

    text2 = f"🌙 <b>{game.day + 1}-tun boshlandi!</b>\nMaxsus rollar PM dan harakat qiling."
    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text2)

    await start_night_phase(game, bot)


# ── ELO Rating ──

async def update_elo_ratings(game: MafiaGame, winner: str):
    players = [p for p in game.players.values() if not p.is_bot]
    ratings = {p.user_id: get_profile(p.user_id).get("elo", 1000) for p in players}
    for player in players:
        for opponent in players:
            if opponent.user_id == player.user_id:
                continue
            expected = expected_score(ratings[player.user_id], ratings[opponent.user_id])
            score = 1.0 if player.team == winner else 0.0
            delta = round(game.elo_k * (score - expected) / (len(players) - 1))
            update_elo(player.user_id, delta)


# ── End Game ──

async def end_game(game: MafiaGame, bot: Bot, winner: str):
    game.phase = GamePhase.ENDED
    game.winner = winner
    game.cancel_timers()
    game.log("game_ended", f"Winner: {winner}")

    for player in game.players.values():
        if player.is_bot:
            continue
        won = winner == player.team
        game_reward(player.user_id, won, player.name, player.username)
        update_weekly_score(player.user_id, 3 if won else 1)

    await update_elo_ratings(game, winner)
    await check_achievements(game, winner)

    winner_labels = {
        "town": "👤 <b>SHAHAR AHOLISI</b>",
        "mafia": "🔪 <b>MAFIA</b>",
        "neutral": "🟣 <b>MUSTAQIL</b>",
    }
    winner_text = winner_labels.get(winner, f"<b>{winner.upper()}</b>")

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
        await bot.send_message(chat_id, f"{phase_banner}\n\n🌅 Ertalab...")
    elif game.phase == GamePhase.VOTING:
        await bot.send_message(chat_id, f"{phase_banner}\n\n🗳 Ovoz berish...")
    elif game.phase == GamePhase.WAITING:
        await bot.send_message(chat_id, "🔄 Bot qayta ishga tushdi.")
        await update_game_message(game, bot)