"""Core game engine — phases, night/day resolution, win checks, UI"""

import asyncio
import logging
import random
from typing import Optional, List, Dict

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .models import MafiaGame, Player, games, GamePhase
from .roles import Role, ROLE_ICON, ROLE_DISPLAY, ROLE_DESC, ROLE_TEAM, IS_NIGHT_ACTIVE
from .config import NIGHT_TIME, DAY_TIME, MORNING_WAIT
from .db import (
    get_profile, save_profile, update_weekly_score,
    delete_active_game, get_chat_setting
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
    team_icon = "🔪" if player.team == "mafia" else "👤"
    role_line = f"├ Role: {player.role_display}\n" if show_role and player.role else ""
    return (
        f"{'🟢' if player.alive else '💀'} <b>{player.display}</b>\n"
        f"{role_line}"
        f"└ Status: {'Alive ✅' if player.alive else 'Dead ❌'}"
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
                await safe_send_message(bot, player.user_id, f"🌙 <b>{game.day}-tun</b>\n\nHech kim o'lmagan.")
                game.action_ready[player.user_id] = True
        elif role == Role.MANIYAK:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_maniyak", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🪓 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz? (Mustaqil harakat)",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.SHERIF:
            await safe_send_message(
                bot, player.user_id,
                f"🛡 <b>{game.day}-tun</b>\n\nSiz himoyadasiz. Mafiya sizni otmoqchi bo'lsa, ulardan biri o'ladi."
            )
            game.action_ready[player.user_id] = True
        elif role == Role.ADVOKAT:
            await safe_send_message(
                bot, player.user_id,
                f"⚖️ <b>{game.day}-tun</b>\n\nErtangi kunda bir o'yinchini himoya qilishingiz mumkin."
            )
            game.action_ready[player.user_id] = True
        elif role == Role.VETERAN:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_veteran", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🎖 <b>{game.day}-tun</b>\n\nHujum rejimiga o'tasizmi? Kimnidir otasizmi?",
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
        elif role == Role.VIGILANTE:
            if game.vigilante_bullets <= 0:
                await safe_send_message(bot, player.user_id, f"🔫 O'qlar tugadi! Siz otolmaysiz.")
                game.action_ready[player.user_id] = True
                continue
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_vigilante", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🔫 <b>{game.day}-tun</b>\n\nKimni otamiz? (Agar begunoh bo'lsa, o'zingiz o'lasiz)\nQolgan o'q: {game.vigilante_bullets}",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.TRANSPORTER:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_transport1", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🔄 <b>{game.day}-tun</b>\n\n1-o'yinchini tanlang (o'rin almashtirish):",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.SPY:
            await safe_send_message(
                bot, player.user_id,
                f"🕶 <b>{game.day}-tun</b>\n\nSiz mafiya a'zolarining muhokamasini eshitasiz..."
            )
            game.action_ready[player.user_id] = True
        elif role == Role.CONSIGLIERE:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_consigliere", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"📜 <b>{game.day}-tun</b>\n\nKimning rolini bilmoqchisiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.IZQUVAR:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_izquvar", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🔎 <b>{game.day}-tun</b>\n\nKimni kuzatamiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.KUZATUVCHI:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_watch", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"👁 <b>{game.day}-tun</b>\n\nKimni kuzatamiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.TERGOVCHI:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_investigate", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"📋 <b>{game.day}-tun</b>\n\nKimni tergov qilamiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.DETEKTIV:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_detective", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🕵️ <b>{game.day}-tun</b>\n\nKimni tekshiramiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.PSIXOLOG:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_psychologist", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🧠 <b>{game.day}-tun</b>\n\nKimning psixologik holatini tekshiramiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.ORACLE:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_oracle", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🔯 <b>{game.day}-tun</b>\n\nKimning o'limi haqida ma'lumot olamiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.PRIEST:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_priest", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"✝️ <b>{game.day}-tun</b>\n\nKimni himoya qilamiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.MUHANDIS:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_engineer", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"⚙️ <b>{game.day}-tun</b>\n\nKimning uyiga kuzatuv qurilmasini o'rnatamiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.MEDIUM:
            dead_list = "\n".join([f"💀 {p.display}" for p in game.dead_players]) if game.dead_players else "Hech kim o'lmagan"
            await safe_send_message(
                bot, player.user_id,
                f"🔮 <b>{game.day}-tun</b>\n\nO'lgan ruhlar bilan bog'lanasiz...\n\n{dead_list}"
            )
            game.action_ready[player.user_id] = True
        elif role == Role.ARSONIST:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_arsonist", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🔥 <b>{game.day}-tun</b>\n\nKimni benzin bilan sepamiz?\n"
                f"Yoki yoqish uchun /ignite yozing.",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.WITCH:
            target_list = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(target_list, "nv_witch", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🧙 <b>{game.day}-tun</b>\n\nKimni boshqaramiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.ASSASSIN and game.day % 2 == 1:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_assassin", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🗡 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz? (Har 2 tunda 1 marta)",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.BOMBER:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_bomber", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"💣 <b>{game.day}-tun</b>\n\nKimning uyiga bomba o'rnatamiz? (Keyingi tun portlaydi)",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.POISONER:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_poisoner", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"☠️ <b>{game.day}-tun</b>\n\nKimni zaharlaymiz? (Ertasi kuni o'ladi)",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.PROFESSIONAL:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_professional", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🎯 <b>{game.day}-tun</b>\n\nKimni o'ldiramiz? (Noto'g'ri o'ldirsangiz, o'zingiz o'lasiz)",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.ROLEBLOCKER:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_roleblock", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🔒 <b>{game.day}-tun</b>\n\nKimni bloklaymiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.SILENCER:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_silence", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🤐 <b>{game.day}-tun</b>\n\nKimni ovozsiz qoldiramiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.BLACKMAILER:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_blackmail", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"📨 <b>{game.day}-tun</b>\n\nKimni shantaj qilamiz?",
                reply_markup=kb
            )
            game.action_ready[player.user_id] = False
        elif role == Role.FRAMER:
            targets = [p for p in game.alive_players if p.user_id != player.user_id]
            kb = make_players_keyboard(targets, "nv_framer", chat_id=cid)
            await safe_send_message(
                bot, player.user_id,
                f"🎭 <b>{game.day}-tun</b>\n\nKimni framer qilamiz?",
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
                    f"✒️ <b>{game.day}-tun</b>\n\nKimning rol ma'lumotini o'zgartiramiz?",
                    reply_markup=kb
                )
                game.action_ready[player.user_id] = False
            else:
                await safe_send_message(bot, player.user_id, f"🌙 Hech kim o'lmagan.")
                game.action_ready[player.user_id] = True
        elif role == Role.JOKER:
            await safe_send_message(
                bot, player.user_id,
                f"🃏 <b>{game.day}-tun</b>\n\nSizning maqsadingiz — ovoz berish orqali chiqarilish!"
            )
            game.action_ready[player.user_id] = True
        elif role == Role.SURVIVOR:
            await safe_send_message(
                bot, player.user_id,
                f"⛺ <b>{game.day}-tun</b>\n\nSizning maqsadingiz — tirik qolish!"
            )
            game.action_ready[player.user_id] = True
        elif role == Role.EXECUTIONER:
            await safe_send_message(
                bot, player.user_id,
                f"🪓 <b>{game.day}-tun</b>\n\nSizning maqsadingiz — bir o'yinchini chiqarilishiga erishish!"
            )
            game.action_ready[player.user_id] = True
        elif role in (Role.MER, Role.AMNESIAC):
            await safe_send_message(bot, player.user_id, f"🌙 <b>{game.day}-tun</b>\n\nSiz uxlayapsiz...")
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

    # Transport resolution
    transport_map = {}
    if game.transporter_target1 and game.transporter_target2:
        transport_map[game.transporter_target1] = game.transporter_target2
        transport_map[game.transporter_target2] = game.transporter_target1

    def resolve_target(target: Optional[int]) -> Optional[int]:
        if target and target in transport_map:
            return transport_map[target]
        return target

    # Roleblock resolution
    roleblocked = set()
    if game.roleblocker_target:
        roleblocked.add(game.roleblocker_target)

    # Mafia kill vote resolution
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

    # Resolve mafia kill
    kill_target = resolve_target(kill_target)
    killed_player = None
    if kill_target is not None and kill_target in game.players:
        target = game.get_player(kill_target)
        if target and target.alive and kill_target not in roleblocked:
            if kill_target == game.doktor_target or kill_target == game.hamshira_target or kill_target == game.priest_target:
                heal_role = "Doktor" if kill_target == game.doktor_target else "Hamshira" if kill_target == game.hamshira_target else "Priest"
                game.healed_player = kill_target
                target.protected = True
            elif game.veteran_active and kill_target in [p.user_id for p in game.alive_players if p.role == Role.VETERAN]:
                attacker = None
                for p in game.players.values():
                    if p.role in (Role.MAFIA, Role.DON, Role.GODFATHER):
                        attacker = p
                        break
                if attacker:
                    attacker.alive = False
            else:
                target.alive = False
                killed_player = target

    # Resolve Vigilante kill
    vigilante_killed = None
    if game.vigilante_target is not None:
        vig_target = resolve_target(game.vigilante_target)
        target = game.get_player(vig_target)
        if target and target.alive and vig_target not in roleblocked:
            target.alive = False
            vigilante_killed = target
            if target.team != "mafia":
                for p in game.players.values():
                    if p.role == Role.VIGILANTE:
                        p.alive = False

    # Resolve Maniyak kill
    maniyak_killed = None
    if game.maniyak_target is not None:
        m_target = resolve_target(game.maniyak_target)
        target = game.get_player(m_target)
        if target and target.alive and m_target not in roleblocked:
            target.alive = False
            maniyak_killed = target

    # Resolve Professional kill
    professional_killed = None
    if game.professional_target is not None:
        p_target = resolve_target(game.professional_target)
        target = game.get_player(p_target)
        if target and target.alive and p_target not in roleblocked:
            target.alive = False
            professional_killed = target
            if target.team != "mafia":
                for pl in game.players.values():
                    if pl.role == Role.PROFESSIONAL:
                        pl.alive = False

    # Resolve Assassin kill
    if game.assassin_target is not None and game.day % 2 == 1:
        a_target = resolve_target(game.assassin_target)
        target = game.get_player(a_target)
        if target and target.alive and a_target not in roleblocked:
            target.alive = False

    # Bomber detonation
    bomber_exploded = None
    if game.bomber_target is not None:
        b_target = resolve_target(game.bomber_target)
        target = game.get_player(b_target)
        if target and target.alive and b_target not in roleblocked:
            target.alive = False
            bomber_exploded = target

    # Poisoner kill
    if game.poisoner_target is not None:
        po_target = resolve_target(game.poisoner_target)
        target = game.get_player(po_target)
        if target and target.alive and po_target not in roleblocked:
            target.alive = False

    # Arsonist ignite
    arsonist_killed = []
    if game.arsonist_ignite:
        for uid in game.arsonist_targets:
            target = game.get_player(uid)
            if target and target.alive:
                target.alive = False
                arsonist_killed.append(target)
        game.arsonist_targets = []

    # Investigator results
    if game.komissar_target is not None:
        checked = game.get_player(resolve_target(game.komissar_target))
        if checked:
            is_mafia = checked.team == "mafia"
            if checked.role in (Role.DON, Role.GODFATHER):
                is_mafia = False
            result = "🔴 MAFIA" if is_mafia else "🟢 Tinch aholi"
            for p in game.players.values():
                if p.role == Role.KOMISSAR and p.alive:
                    await safe_send_message(
                        bot, p.user_id,
                        f"🔍 <b>Tekshiruv natijasi:</b>\n{checked.display}: {result}"
                    )

    if game.detective_target is not None:
        det = game.get_player(resolve_target(game.detective_target))
        if det:
            is_suspicious = det.team == "mafia"
            if det.role in (Role.DON, Role.GODFATHER):
                is_suspicious = False
            result = "⚖️ Aybdor" if is_suspicious else "✅ Begunoh"
            for p in game.players.values():
                if p.role == Role.DETEKTIV and p.alive:
                    await safe_send_message(
                        bot, p.user_id,
                        f"🕵️ <b>Detektiv natijasi:</b>\n{det.display}: {result}"
                    )

    if game.tergovchi_target is not None:
        inv = game.get_player(resolve_target(game.tergovchi_target))
        if inv:
            ter_results = ["🔴 Mafia a'zosi", "🟢 Shahar aholisi", "🟣 Mustaqil"]
            if inv.team == "mafia":
                role_info = ter_results[0]
            elif inv.team == "neutral":
                role_info = ter_results[2]
            else:
                role_info = ter_results[1]
            for p in game.players.values():
                if p.role == Role.TERGOVCHI and p.alive:
                    await safe_send_message(
                        bot, p.user_id,
                        f"📋 <b>Tergov natijasi:</b>\n{inv.display}: {role_info}"
                    )

    if game.izquvar_target is not None:
        izq_target = resolve_target(game.izquvar_target)
        izq = game.get_player(izq_target)
        if izq and izq.alive:
            visited = []
            for p in game.players.values():
                if p.night_target == izq_target and p.user_id != izq_target:
                    visited.append(p.display)
            text = f"🔎 <b>Kuzatuv natijasi:</b>\n{izq.display} ga tashrif buyurganlar: "
            text += ", ".join(visited) if visited else "Hech kim"
            for p in game.players.values():
                if p.role == Role.IZQUVAR and p.alive:
                    await safe_send_message(bot, p.user_id, text)

    # Consigliere result
    if game.consigliere_target is not None:
        consig = game.get_player(resolve_target(game.consigliere_target))
        if consig:
            result = f"📜 <b>Consigliere natijasi:</b>\n{consig.display} — {consig.role_display}"
            for p in game.players.values():
                if p.role == Role.CONSIGLIERE and p.alive:
                    await safe_send_message(bot, p.user_id, result)

    # Spy info
    for p in game.players.values():
        if p.role == Role.SPY and p.alive:
            mafia_chat = []
            for mp in game.mafia_players:
                if mp.user_id != p.user_id:
                    target_info = ""
                    if game.mafia_votes.get(mp.user_id):
                        target_info = f" -> {game.get_player(game.mafia_votes[mp.user_id]).display}"
                    mafia_chat.append(f"🔪 {mp.display}{target_info}")
            spy_text = f"🕶 <b>Mafia muhokamasi:</b>\n" + "\n".join(mafia_chat) if mafia_chat else "Mafia hech narsa muhokama qilmadi."
            await safe_send_message(bot, p.user_id, spy_text)

    # Witch control
    for witch_id, target_id in game.witch_control.items():
        pass

    # Sherif vengeance
    sherif_vengeance = None
    if killed_player and killed_player.role == Role.SHERIF:
        mafia_alive = game.mafia_players
        if mafia_alive:
            vengeance_target = random.choice(mafia_alive)
            vengeance_target.alive = False
            sherif_vengeance = vengeance_target

    # ── Morning message ──
    game.phase = GamePhase.MORNING
    death_messages = []
    if killed_player:
        death_messages.append(
            f"💀 <b>{killed_player.display}</b> o'ldirildi! "
            f"({ROLE_ICON.get(killed_player.role, '❓')} {killed_player.role.value if killed_player.role else '?'})"
        )
    if sherif_vengeance:
        death_messages.append(
            f"🛡 Sherif qasosi! <b>{sherif_vengeance.display}</b> otib o'ldirildi! "
            f"({ROLE_ICON.get(sherif_vengeance.role, '❓')} {sherif_vengeance.role.value if sherif_vengeance.role else '?'})"
        )
    if maniyak_killed and maniyak_killed != killed_player:
        death_messages.append(
            f"🪓 <b>{maniyak_killed.display}</b> Maniyak tomonidan o'ldirildi! "
            f"({ROLE_ICON.get(maniyak_killed.role, '❓')} {maniyak_killed.role.value if maniyak_killed.role else '?'})"
        )
    if vigilante_killed:
        death_messages.append(f"🔫 <b>{vigilante_killed.display}</b> Vigilante tomonidan otildi!")
    for ak in arsonist_killed:
        death_messages.append(f"🔥 <b>{ak.display}</b> yonib o'ldi!")
    if game.healed_player and not killed_player:
        healed = game.get_player(game.healed_player)
        if healed:
            death_messages.append(f"💊 Doktor {healed.display} ni davoladi! Hech kim o'lmadi!")

    if death_messages:
        text = f"{make_game_banner(GamePhase.MORNING, game.day)}\n\n" + "\n".join(death_messages) + "\n\n"
    else:
        text = f"{make_game_banner(GamePhase.MORNING, game.day)}\n\nBu tun hech kim o'lmadi...\n\n"

    alive_list = "\n".join([make_player_card(p) for p in game.alive_players])
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
        await asyncio.sleep(MORNING_WAIT)
        await start_day_phase(game, bot)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"Morning timer error for {game.chat_id}: {e}")


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

    votes = {}
    for player in game.alive_players:
        if player.vote is not None and player.vote > 0:
            multiplier = 3 if player.role == Role.MER else 1
            votes[player.vote] = votes.get(player.vote, 0) + multiplier

    eliminated = None
    if votes:
        max_votes = max(votes.values())
        top_voted = [t for t, v in votes.items() if v == max_votes]
        elim_id = random.choice(top_voted)
        eliminated = game.get_player(elim_id)
        if eliminated:
            eliminated.alive = False

    text = f"{make_game_banner(GamePhase.EXECUTION, game.day)}\n\n"
    if eliminated:
        text += (
            f"🗳 <b>{eliminated.display}</b> eng ko'p ovoz oldi!\n"
            f"Role: {ROLE_ICON.get(eliminated.role, '❓')} <b>{eliminated.role.value if eliminated.role else '?'}</b>\n\n"
        )
        if eliminated.role == Role.JOKER:
            text += "🃏 Joker o'z maqsadiga erishdi! U yutdi!\n\n"
        if game.advokat_protect == eliminated.user_id:
            eliminated.alive = True
            text += f"⚖️ Advokat {eliminated.display} ni himoya qildi! U tirik qoldi!\n\n"
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
        if player.is_bot:
            continue
        won = winner == player.team
        game_reward(player.user_id, won, player.name, player.username)
        update_weekly_score(player.user_id, 3 if won else 1)
        profile = get_profile(player.user_id)
        profile["games"] = profile.get("games", 0) + 1
        if won:
            profile["wins"] = profile.get("wins", 0) + 1
        else:
            profile["losses"] = profile.get("losses", 0) + 1
        save_profile(player.user_id, profile)

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
        await bot.send_message(chat_id, f"{phase_banner}\n\n🌅 Ertalab... Natijalar kutilmoqda.")
    elif game.phase == GamePhase.VOTING:
        await bot.send_message(chat_id, f"{phase_banner}\n\n🗳 Ovoz berish davom etmoqda.")
        game.day_task = asyncio.create_task(day_timer(game, bot))
    elif game.phase == GamePhase.WAITING:
        await bot.send_message(chat_id, "🔄 Bot qayta ishga tushdi. Lobby saqlanib qoldi.")
        await update_game_message(game, bot)
