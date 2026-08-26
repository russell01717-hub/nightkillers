"""All callback query handlers — menus, join/leave, night actions, day votes"""

import asyncio
import logging
import random
from datetime import datetime

from aiogram import Bot, types, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.exceptions import TelegramForbiddenError

from ..models import MafiaGame, Player, games, GamePhase
from ..roles import Role, ROLE_ICON, ROLE_DISPLAY, ROLE_DESC, ROLE_TEAM, ROLE_PRICES, IS_NIGHT_ACTIVE
from ..config import ADMIN_ID, MAX_PLAYERS
from ..db import (
    get_profile, get_weekly_top, get_weekly_titles_dict, get_all_profiles,
)
from ..economy import get_shop_text, buy_role
from ..game_engine import (
    make_inline_keyboard, make_game_banner, make_player_card,
    safe_send_message, safe_edit_message, update_game_message,
    validate_callback, make_players_keyboard, end_night_phase,
)

log = logging.getLogger("MafiaBot.Callbacks")


def register(dp, bot: Bot):
    dp.callback_query.register(handle_join, F.data.startswith("join:"))
    dp.callback_query.register(handle_leave, F.data.startswith("leave:"))
    dp.callback_query.register(handle_night_kill, F.data.startswith("nv_kill:"))
    dp.callback_query.register(handle_night_don, F.data.startswith("nv_don:"))
    dp.callback_query.register(handle_night_check, F.data.startswith("nv_check:"))
    dp.callback_query.register(handle_night_heal, F.data.startswith("nv_heal:"))
    dp.callback_query.register(handle_night_maniyak, F.data.startswith("nv_maniyak:"))
    dp.callback_query.register(handle_night_revive, F.data.startswith("nv_revive:"))
    dp.callback_query.register(handle_night_veteran, F.data.startswith("nv_veteran:"))
    dp.callback_query.register(handle_night_protect, F.data.startswith("nv_protect:"))
    dp.callback_query.register(handle_night_jail, F.data.startswith("nv_jail:"))
    dp.callback_query.register(handle_night_vigilante, F.data.startswith("nv_vigilante:"))
    dp.callback_query.register(handle_night_transport1, F.data.startswith("nv_transport1:"))
    dp.callback_query.register(handle_night_transport2, F.data.startswith("nv_transport2:"))
    dp.callback_query.register(handle_night_consigliere, F.data.startswith("nv_consigliere:"))
    dp.callback_query.register(handle_night_izquvar, F.data.startswith("nv_izquvar:"))
    dp.callback_query.register(handle_night_amnesiac, F.data.startswith("nv_amnesiac:"))
    dp.callback_query.register(handle_night_watch, F.data.startswith("nv_watch:"))
    dp.callback_query.register(handle_night_investigate, F.data.startswith("nv_investigate:"))
    dp.callback_query.register(handle_night_detective, F.data.startswith("nv_detective:"))
    dp.callback_query.register(handle_night_psychologist, F.data.startswith("nv_psychologist:"))
    dp.callback_query.register(handle_night_engineer, F.data.startswith("nv_engineer:"))
    dp.callback_query.register(handle_night_oracle, F.data.startswith("nv_oracle:"))
    dp.callback_query.register(handle_night_priest, F.data.startswith("nv_priest:"))
    dp.callback_query.register(handle_night_arsonist, F.data.startswith("nv_arsonist:"))
    dp.callback_query.register(handle_night_witch, F.data.startswith("nv_witch:"))
    dp.callback_query.register(handle_night_assassin, F.data.startswith("nv_assassin:"))
    dp.callback_query.register(handle_night_bomber, F.data.startswith("nv_bomber:"))
    dp.callback_query.register(handle_night_poisoner, F.data.startswith("nv_poisoner:"))
    dp.callback_query.register(handle_night_professional, F.data.startswith("nv_professional:"))
    dp.callback_query.register(handle_night_roleblock, F.data.startswith("nv_roleblock:"))
    dp.callback_query.register(handle_night_silence, F.data.startswith("nv_silence:"))
    dp.callback_query.register(handle_night_blackmail, F.data.startswith("nv_blackmail:"))
    dp.callback_query.register(handle_night_framer, F.data.startswith("nv_framer:"))
    dp.callback_query.register(handle_night_janitor, F.data.startswith("nv_janitor:"))
    dp.callback_query.register(handle_night_forger, F.data.startswith("nv_forger:"))

    # Bloody Mode night handlers
    dp.callback_query.register(handle_night_mashuqa, F.data.startswith("nv_mashuqa:"))
    dp.callback_query.register(handle_night_kamikaze, F.data.startswith("nv_kamikaze:"))
    dp.callback_query.register(handle_night_buqalamun, F.data.startswith("nv_buqalamun:"))
    dp.callback_query.register(handle_night_suidsid, F.data.startswith("nv_suidsid:"))
    dp.callback_query.register(handle_night_kimyogar, F.data.startswith("nv_kimyogar:"))

    dp.callback_query.register(handle_day_vote, F.data.startswith("d_vote:"))
    dp.callback_query.register(handle_day_skip, F.data.startswith("d_skip:"))
    dp.callback_query.register(handle_day_advokat, F.data.startswith("d_advokat:"))
    dp.callback_query.register(handle_day_advokat_pick, F.data.startswith("d_advokat_pick:"))
    dp.callback_query.register(handle_shop_buy, F.data == "shop_buy")
    dp.callback_query.register(handle_confirm_pay, F.data.startswith("confirm_pay:"))
    dp.callback_query.register(handle_reject_pay, F.data.startswith("reject_pay:"))

    # Start menu handlers (specific first, generic last)
    dp.callback_query.register(show_profile, F.data == "start_profile")
    dp.callback_query.register(show_money, F.data == "start_money")
    dp.callback_query.register(show_top, F.data == "start_top")
    dp.callback_query.register(show_shop, F.data == "start_shop")
    dp.callback_query.register(show_stats_cb, F.data == "start_stats")
    dp.callback_query.register(show_help, F.data == "start_help")
    dp.callback_query.register(show_about, F.data == "start_about")
    dp.callback_query.register(show_weekly, F.data == "start_weekly")
    dp.callback_query.register(show_back, F.data == "start_back")

    # Fallback: acknowledge any unmatched start_* callback (registered LAST)
    dp.callback_query.register(handle_callback, F.data.startswith("start_"))


async def handle_callback(callback: CallbackQuery, bot: Bot):
    try:
        await callback.answer()
    except:
        pass


async def handle_join(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 2:
        return
    chat_id = int(parts[1])
    user = callback.from_user
    if chat_id not in games:
        await callback.message.answer("❌ O'yin mavjud emas!")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await callback.message.answer("❌ O'yin boshlangan!")
        return
    if user.id in game.players:
        await callback.message.answer("❌ Siz allaqachon o'yindasiz!")
        return
    if len(game.players) >= MAX_PLAYERS:
        await callback.message.answer("❌ O'yin to'liq!")
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
            f"O'yin boshlanishini kuting."
        )
    except TelegramForbiddenError:
        pass


async def handle_leave(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 2:
        return
    chat_id = int(parts[1])
    user_id = callback.from_user.id
    if chat_id not in games:
        await callback.message.answer("❌ O'yin mavjud emas!")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await callback.message.answer("❌ Ro'yxatdan o'tish tugagan!")
        return
    if user_id not in game.players:
        await callback.message.answer("❌ Siz o'yinda emassiz!")
        return
    del game.players[user_id]
    game.log("player_left", f"{user_id}")
    await update_game_message(game, bot)


async def handle_night_kill(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    _, chat_id_str, target_str = parts[0], parts[1], parts[2]
    chat_id = int(chat_id_str)
    target_id = int(target_str)
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role not in (Role.MAFIA, Role.GODFATHER):
        await callback.message.answer("❌ Siz mafia a'zosi emassiz!")
        return

    game.action_ready[user_id] = True
    game.mafia_votes[user_id] = target_id
    await safe_send_message(
        bot, user_id,
        f"✅ Ovozingiz qabul qilindi! ({game.get_player(target_id).display})"
    )

    all_voted = all(
        game.action_ready.get(p.user_id, False)
        for p in game.alive_players
        if p.role in (Role.MAFIA, Role.DON, Role.GODFATHER) and p.team == "mafia"
    )
    if all_voted:
        game.night_task.cancel()
        await end_night_phase(game, bot)


async def handle_night_don(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.DON:
        await callback.message.answer("❌ Siz Don emassiz!")
        return

    game.action_ready[user_id] = True
    game.don_target = target_id
    game.mafia_votes[user_id] = target_id
    await safe_send_message(
        bot, user_id,
        f"✅ Ovozingiz qabul qilindi! (Don: {game.get_player(target_id).display})"
    )

    all_voted = all(
        game.action_ready.get(p.user_id, False)
        for p in game.alive_players
        if p.role in (Role.MAFIA, Role.DON, Role.GODFATHER) and p.team == "mafia"
    )
    if all_voted:
        game.night_task.cancel()
        await end_night_phase(game, bot)


async def handle_night_check(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.KOMISSAR:
        await callback.message.answer("❌ Siz Komissar emassiz!")
        return

    game.komissar_target = target_id
    game.action_ready[user_id] = True
    await safe_send_message(
        bot, user_id,
        f"🔍 Tekshiruv natijasi tongda ma'lum bo'ladi... ({game.get_player(target_id).display})"
    )


async def handle_night_heal(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.DOKTOR:
        await callback.message.answer("❌ Siz Doktor emassiz!")
        return

    game.doktor_target = target_id
    game.action_ready[user_id] = True
    await safe_send_message(
        bot, user_id,
        f"💊 {game.get_player(target_id).display} ni davolash uchun tanlandi."
    )


async def handle_night_maniyak(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.MANIYAK:
        await callback.message.answer("❌ Siz Maniyak emassiz!")
        return

    game.maniyak_target = target_id
    game.action_ready[user_id] = True
    await safe_send_message(
        bot, user_id,
        f"🪓 {game.get_player(target_id).display} nishonga olindi!"
    )


async def handle_night_revive(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.HAMSHIRA:
        await callback.message.answer("❌ Siz Hamshira emassiz!")
        return

    target = game.get_player(target_id)
    if target and not target.alive:
        target.alive = True
        game.hamshira_target = target_id
        game.action_ready[user_id] = True
        await safe_send_message(
            bot, user_id,
            f"🏥 {target.display} tiriltirildi!"
        )
        await safe_send_message(
            bot, target_id,
            f"🏥 Siz Hamshira tomonidan tiriltirildingiz!"
        )


async def handle_night_veteran(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    choice = parts[1]
    user_id = callback.from_user.id
    game = games.get(int(parts[2]))
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return
    if choice == "yes":
        game.veteran_active = True
        await safe_send_message(bot, user_id, "🎖 Hujum rejimi faollashtirildi! Sizga hujum qilgan o'ladi.")
    else:
        await safe_send_message(bot, user_id, "🎖 Hujum rejimisiz.")
    game.action_ready[user_id] = True


async def handle_night_protect(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.QORIQCHI:
        await callback.message.answer("❌ Siz Qo'riqchi emassiz!")
        return

    game.qoriqchi_target = target_id
    game.action_ready[user_id] = True
    await safe_send_message(bot, user_id, f"🛡 {game.get_player(target_id).display} himoya qilinadi!")


async def handle_night_jail(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.JAILOR:
        await callback.message.answer("❌ Siz Jailor emassiz!")
        return

    game.jailor_target = target_id
    game.action_ready[user_id] = True
    target = game.get_player(target_id)
    target.jailed = True
    await safe_send_message(bot, user_id, f"⛓ {target.display} qamoqqa tashlandi!")
    await safe_send_message(bot, target_id, f"⛓ Siz qamoqqa tashlandingiz! Bu tun harakat qila olmaysiz.")


async def handle_night_vigilante(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.VIGILANTE:
        await callback.message.answer("❌ Siz Vigilante emassiz!")
        return

    if game.vigilante_bullets <= 0:
        await callback.message.answer("❌ O'qlar tugadi!")
        return
    game.vigilante_target = target_id
    game.vigilante_bullets -= 1
    game.action_ready[user_id] = True
    await safe_send_message(bot, user_id, f"🔫 {game.get_player(target_id).display} nishonga olindi! (Qolgan o'q: {game.vigilante_bullets})")


async def handle_night_transport1(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != Role.TRANSPORTER:
        await callback.message.answer("❌ Siz Transporter emassiz!")
        return

    game.transporter_target1 = target_id
    targets = [p for p in game.alive_players if p.user_id not in (user_id, target_id)]
    if targets:
        kb = make_players_keyboard(targets, "nv_transport2", chat_id=chat_id)
        await safe_send_message(
            bot, user_id,
            f"🔄 1-o'yinchi: {game.get_player(target_id).display}\n"
            f"Endi 2-o'yinchini tanlang:",
            reply_markup=kb
        )
    else:
        await safe_send_message(bot, user_id, "❌ O'rin almashtirish uchun yetarli o'yinchi yo'q!")
        game.transporter_target1 = None


async def handle_night_transport2(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        return

    if game.transporter_target1 is None:
        await safe_send_message(bot, user_id, "❌ Avval 1-o'yinchini tanlang!")
        return

    game.transporter_target2 = target_id
    game.action_ready[user_id] = True
    t1 = game.get_player(game.transporter_target1)
    t2 = game.get_player(target_id)
    await safe_send_message(
        bot, user_id,
        f"🔄 {t1.display} va {t2.display} o'rinlari almashtirildi!"
    )


async def handle_night_consigliere(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        return

    player = game.get_player(user_id)
    if player.role != Role.CONSIGLIERE:
        await callback.message.answer("❌ Siz Consigliere emassiz!")
        return

    game.consigliere_target = target_id
    game.action_ready[user_id] = True
    await safe_send_message(bot, user_id, f"📜 Ma'lumot tongda beriladi.")


async def handle_night_izquvar(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        return

    player = game.get_player(user_id)
    if player.role != Role.IZQUVAR:
        await callback.message.answer("❌ Siz Izquvar emassiz!")
        return

    game.izquvar_target = target_id
    game.action_ready[user_id] = True
    await safe_send_message(bot, user_id, f"🔎 Kuzatuv natijasi tongda beriladi.")


# ── Generic night action handlers ──

async def _night_target_handler(
    callback: CallbackQuery, bot: Bot,
    required_role: Role, game_attr: str
):
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    player = game.get_player(user_id)
    if player.role != required_role:
        await callback.message.answer(f"❌ Siz {required_role.value} emassiz!")
        return

    setattr(game, game_attr, target_id)
    game.action_ready[user_id] = True
    await safe_send_message(
        bot, user_id,
        f"✅ Tanlandi: {game.get_player(target_id).display}"
    )


async def handle_night_watch(callback, bot): await _night_target_handler(callback, bot, Role.KUZATUVCHI, "kuzatuvchi_target")
async def handle_night_amnesiac(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id
    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return
    player = game.get_player(user_id)
    if player.role != Role.AMNESIAC:
        await callback.message.answer("❌ Siz Amnesiac emassiz!")
        return
    target = game.get_player(target_id)
    if not target or not target.role:
        await callback.message.answer("❌ Bu o'yinchining roli yo'q.")
        game.action_ready[user_id] = True
        return
    adopted_role = target.role.value
    player.amnesiac_adopted_role = adopted_role
    player.role = target.role
    player.team = target.team
    game.action_ready[user_id] = True
    await safe_send_message(bot, user_id, f"❓ Siz {target.role_display} rolini esladingiz! Endi siz {target.team} tomonidasiz!")

async def handle_night_investigate(callback, bot): await _night_target_handler(callback, bot, Role.TERGOVCHI, "tergovchi_target")
async def handle_night_detective(callback, bot): await _night_target_handler(callback, bot, Role.DETEKTIV, "detective_target")
async def handle_night_psychologist(callback, bot): await _night_target_handler(callback, bot, Role.PSIXOLOG, "psychologist_target")
async def handle_night_engineer(callback, bot): await _night_target_handler(callback, bot, Role.MUHANDIS, "engineer_target")
async def handle_night_oracle(callback, bot): await _night_target_handler(callback, bot, Role.ORACLE, "oracle_target")
async def handle_night_priest(callback, bot): await _night_target_handler(callback, bot, Role.PRIEST, "priest_target")
async def handle_night_arsonist(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    sub = parts[1]
    chat_id = int(parts[2])
    user_id = callback.from_user.id
    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return
    player = game.get_player(user_id)
    if player.role != Role.ARSONIST:
        await callback.message.answer("❌ Siz Arsonist emassiz!")
        return
    if sub == "ignite":
        game.arsonist_ignite = True
        game.action_ready[user_id] = True
        await safe_send_message(bot, user_id, "🔥 Barcha doused o'yinchilar yoqib yuborildi!")
        return
    target_id = int(sub)
    if target_id not in game.arsonist_targets:
        game.arsonist_targets.append(target_id)
    game.action_ready[user_id] = True
    target = game.get_player(target_id)
    target.doused = True
    await safe_send_message(bot, user_id, f"⛽ {target.display} benzin bilan sepildi!")

async def handle_night_witch(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id
    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.NIGHT], require_alive=True)
    if err:
        await callback.message.answer(err)
        return
    player = game.get_player(user_id)
    if player.role != Role.WITCH:
        await callback.message.answer("❌ Siz Witch emassiz!")
        return
    game.witch_control[user_id] = target_id
    game.action_ready[user_id] = True
    target = game.get_player(target_id)
    await safe_send_message(bot, user_id, f"🧙 {target.display} boshqaruvga olindi!")
async def handle_night_assassin(callback, bot): await _night_target_handler(callback, bot, Role.ASSASSIN, "assassin_target")
async def handle_night_bomber(callback, bot): await _night_target_handler(callback, bot, Role.BOMBER, "bomber_target")
async def handle_night_poisoner(callback, bot): await _night_target_handler(callback, bot, Role.POISONER, "poisoner_target")
async def handle_night_professional(callback, bot): await _night_target_handler(callback, bot, Role.PROFESSIONAL, "professional_target")
async def handle_night_roleblock(callback, bot): await _night_target_handler(callback, bot, Role.ROLEBLOCKER, "roleblocker_target")
async def handle_night_silence(callback, bot): await _night_target_handler(callback, bot, Role.SILENCER, "silencer_target")
async def handle_night_blackmail(callback, bot): await _night_target_handler(callback, bot, Role.BLACKMAILER, "blackmailer_target")
async def handle_night_framer(callback, bot): await _night_target_handler(callback, bot, Role.FRAMER, "framer_target")
async def handle_night_janitor(callback, bot): await _night_target_handler(callback, bot, Role.JANITOR, "janitor_target")
async def handle_night_forger(callback, bot): await _night_target_handler(callback, bot, Role.FORGER, "forger_target")


# Bloody Mode night handlers
async def handle_night_mashuqa(callback: CallbackQuery, bot: Bot):
    await _night_target_handler(callback, bot, Role.MASHUQA, "mashuqa_target")

async def handle_night_kamikaze(callback: CallbackQuery, bot: Bot):
    await _night_target_handler(callback, bot, Role.KAMIKAZE, "kamikaze_target")

async def handle_night_buqalamun(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    team = parts[1]
    chat_id = int(parts[2])
    user_id = callback.from_user.id
    if chat_id not in games:
        return
    game = games[chat_id]
    if game.phase != GamePhase.NIGHT:
        return
    player = game.get_player(user_id)
    if not player or player.role != Role.BUQALAMUN or not player.alive:
        return
    player.buqalamun_team = team
    await callback.answer(f"✅ Jamoangiz: {team}", show_alert=True)
    game.action_ready[user_id] = True

async def handle_night_suidsid(callback: CallbackQuery, bot: Bot):
    await _night_target_handler(callback, bot, Role.SUIDSID, "suidsid_target")

async def handle_night_kimyogar(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 4:
        return
    action = parts[1]
    target_id = int(parts[2])
    chat_id = int(parts[3])
    user_id = callback.from_user.id
    if chat_id not in games:
        return
    game = games[chat_id]
    if game.phase != GamePhase.NIGHT:
        return
    player = game.get_player(user_id)
    if not player or player.role != Role.KIMYOGAR or not player.alive:
        return
    target = game.get_player(target_id)
    if not target or not target.alive:
        return
    if action == "poison":
        player.kimyogar_poison = target_id
        await callback.answer(f"☠️ {target.display} ga zahar berildi!")
    else:
        player.kimyogar_heal = target_id
        await callback.answer(f"💊 {target.display} ga dori berildi!")
    game.action_ready[user_id] = True

async def handle_day_vote(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.VOTING], require_alive=True)
    if err:
        await callback.message.answer(err)
        return

    voter = game.get_player(user_id)
    if voter.silenced or voter.blackmailed:
        await callback.message.answer("🤐 Siz ovoz bera olmaysiz (ovozsiz qoldirilgansiz)!")
        return

    voter.vote = target_id
    target = game.get_player(target_id)
    await safe_send_message(bot, user_id, f"🗳 Ovozingiz {target.display} ga berildi!")


async def handle_day_skip(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 2:
        return
    chat_id = int(parts[1])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.VOTING], require_alive=True)
    if err:
        return

    voter = game.get_player(user_id)
    voter.vote = -1
    await safe_send_message(bot, user_id, f"⏭ Ovoz berishni o'tkazib yubordingiz.")


async def handle_day_advokat(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 2:
        return
    chat_id = int(parts[1])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.VOTING], require_alive=True)
    if err:
        return

    player = game.get_player(user_id)
    if player.role != Role.ADVOKAT:
        await callback.message.answer("❌ Siz Advokat emassiz!")
        return

    # Show player list to choose who to protect
    kb = make_players_keyboard(game.alive_players, "d_advokat_pick", chat_id=chat_id, columns=2)
    await callback.message.edit_text(
        f"⚖️ Kimni himoya qilamiz?\nOvoz berish natijasida u himoya qilinadi.",
        reply_markup=kb
    )


async def handle_day_advokat_pick(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    data = callback.data
    parts = data.split(":")
    if len(parts) < 3:
        return
    chat_id = int(parts[1])
    target_id = int(parts[2])
    user_id = callback.from_user.id

    game = games.get(chat_id)
    err = validate_callback(callback, game, [GamePhase.VOTING], require_alive=True)
    if err:
        return

    player = game.get_player(user_id)
    if player.role != Role.ADVOKAT:
        await callback.message.answer("❌ Siz Advokat emassiz!")
        return

    game.advokat_protect = target_id
    target = game.get_player(target_id)
    await safe_send_message(bot, user_id, f"⚖️ {target.display} himoya qilinadi!")
    # Restore original voting UI
    await callback.message.edit_text(f"⚖️ Nimoyadagi: {target.display} ({game.day}-kun ovozida himoyalanadi)")


# ── Shop ──

async def handle_shop_buy(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id
    profile = get_profile(user_id)
    text = get_shop_text(user_id)
    roles_text = "\n".join([
        f"• /buy {r.value} — {ROLE_PRICES.get(r, 30)}💶"
        for r in Role
    ])
    await callback.message.edit_text(
        f"{text}\n\nRol sotib olish:\n{roles_text}",
        reply_markup=make_inline_keyboard([
            [InlineKeyboardButton(text="◀️ Ortga", callback_data="start_shop")],
        ]),
        parse_mode="HTML"
    )


# ── Payment ──

async def handle_confirm_pay(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[1])
    amount = int(parts[2]) if len(parts) > 2 else 50
    from ..economy import add_olmos
    add_olmos(user_id, amount)
    prev = getattr(callback.message, "caption", None) or getattr(callback.message, "html_text", None) or getattr(callback.message, "text", None) or ""
    text = f"{prev}\n\n✅ To'lov tasdiqlandi! +{amount}💎"
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text)
    await bot.send_message(user_id, f"✅ To'lovingiz tasdiqlandi! +{amount}💎 hisobingizga tushdi.")


async def handle_reject_pay(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    parts = callback.data.split(":")
    user_id = int(parts[1])
    amount = int(parts[2]) if len(parts) > 2 else 50
    prev = getattr(callback.message, "caption", None) or getattr(callback.message, "html_text", None) or getattr(callback.message, "text", None) or ""
    text = f"{prev}\n\n❌ To'lov rad etildi."
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text)
    await bot.send_message(user_id, f"❌ {amount}💎 to'lovingiz rad etildi. Admin bilan bog'lanib ko'ring.")


# ── Start menu callbacks ──

async def show_profile(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user = callback.from_user
    profile = get_profile(user.id)
    olmos = profile.get("olmos", 0)
    evro = profile.get("evro", 0)
    games_count = profile.get("games", 0)
    wins = profile.get("wins", 0)
    losses = profile.get("losses", 0)
    winrate = round(wins / games_count * 100, 1) if games_count else 0
    bought = profile.get("bought_role", "")
    hero = profile.get("hero", 0)

    text = (
        f"👤 <b>{user.first_name}</b>\n"
        f"├ ID: <code>{user.id}</code>\n"
        f"├ 💎 Olmos: {olmos}\n"
        f"├ 💶 Evro: {evro}\n"
        f"├ 🎮 O'yinlar: {games_count}\n"
        f"├ 🏆 G'alabalar: {wins}\n"
        f"├ 💀 Mag'lubiyat: {losses}\n"
        f"├ 📊 Winrate: {winrate}%\n"
        f"├ 🎭 Rol: {bought if bought else 'Yo\'q'}\n"
        f"└ 🦸 Hero: {'✅' if hero else '❌'}"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="🏆 Haftalik", callback_data="start_weekly"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="start_stats")],
        [InlineKeyboardButton(text="◀️ Ortga", callback_data="start_back")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)


async def show_money(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user = callback.from_user
    profile = get_profile(user.id)
    text = (
        f"💰 <b>Hisob</b>\n\n"
        f"💎 Olmos: {profile.get('olmos', 0)}\n"
        f"💶 Evro: {profile.get('evro', 0)}\n\n"
        f"<b>Qanday olish mumkin:</b>\n"
        f"• /daily — har kuni 25💎 + 2💶\n"
        f"• O'yin yutish — 15💎, 3💶\n"
        f"• O'yin uchun — 5💎, 1💶\n"
        f"• /pay — to'lov qilish (+50💎)"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="📅 Daily bonus", callback_data="start_back")],
        [InlineKeyboardButton(text="◀️ Ortga", callback_data="start_back")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)


async def show_top(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    await show_weekly(callback, bot)


async def show_shop(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id
    text = get_shop_text(user_id)
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="🛒 Sotib olish", callback_data="shop_buy")],
        [InlineKeyboardButton(text="⭐ Stars bilan to'lov", callback_data="pay_stars")],
        [InlineKeyboardButton(text="◀️ Ortga", callback_data="start_back")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)


async def show_stats_cb(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user = callback.from_user
    profile = get_profile(user.id)
    g = profile.get("games", 0)
    w = profile.get("wins", 0)
    l = profile.get("losses", 0)
    wr = round(w / g * 100, 1) if g else 0
    text = (
        f"📊 <b>Statistika</b>\n\n"
        f"👤 {user.first_name}\n"
        f"├ 🎮 O'yinlar: {g}\n"
        f"├ 🏆 G'alaba: {w}\n"
        f"├ 💀 Mag'lubiyat: {l}\n"
        f"├ 📊 Winrate: {wr}%\n"
        f"└ 💰 {profile.get('olmos', 0)}💎 | {profile.get('evro', 0)}💶"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="◀️ Ortga", callback_data="start_back")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)


async def show_settings(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    text = (
        "⚙️ <b>Sozlamalar</b>\n\n"
        "Bu yerda o'yin sozlamalarini o'zgartirishingiz mumkin:\n\n"
        "🔧 <b>Mavjud sozlamalar:</b>\n"
        "• Til: O'zbekcha (standart)\n"
        "• Xabarnomalar: Yoqilgan\n"
        "• Ovoz berish vaqti: 45 soniya\n"
        "• Tungi vaqti: 45 soniya\n\n"
        "<i>Admin buyruqlari: /admin</i>"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="◀️ Ortga", callback_data="start_back")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)


async def show_help(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    text = (
        "📖 <b>Buyruqlar:</b>\n\n"
        "/mafia — O'yin yaratish\n"
        "/join — Qo'shilish\n"
        "/leave — Chiqish\n"
        "/startgame — Boshlash\n"
        "/cancel — Bekor qilish\n"
        "/profile — Profil\n"
        "/daily — Bonus\n"
        "/shop — Do'kon\n"
        "/send — Olmos yuborish\n"
        "/hafta — Reyting\n"
        "/pay — To'lov"
    )
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text)


async def show_about(callback: CallbackQuery, bot: Bot):
    from mafia_bot.roles import Role, TOWN_ROLES, MAFIA_ROLES, NEUTRAL_ROLES, ROLE_ICON
    await callback.answer()
    town_list = ", ".join(f"{ROLE_ICON[r]} {r.value}" for r in TOWN_ROLES)
    mafia_list = ", ".join(f"{ROLE_ICON[r]} {r.value}" for r in MAFIA_ROLES)
    neutral_list = ", ".join(f"{ROLE_ICON[r]} {r.value}" for r in NEUTRAL_ROLES)
    text = (
        f"🌙 <b>Versiya: 5.0 (aiogram 3.x)</b>\n\n"
        f"🎭 <b>Rollar: {len(Role)} xil</b>\n"
        f"🟢 Shahar ({len(TOWN_ROLES)}): {town_list}\n\n"
        f"🔴 Mafia ({len(MAFIA_ROLES)}): {mafia_list}\n\n"
        f"🟣 Mustaqil ({len(NEUTRAL_ROLES)}): {neutral_list}\n\n"
        f"👥 Maks: 100 o'yinchi\n"
        f"💎 Iqtisod: Olmos va Evro\n"
        f"🦸 Hero maxsus tizimi\n"
        f"📅 Haftalik bonus va sovrinlar\n\n"
        f"👨‍💻 Dasturchi: @shohnurrajabov\n"
        f"📢 Kanal: https://t.me/+HpBlh_qPFZVkMzhi\n\n"
        f"Powered by aiogram 3.x"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="◀️ Ortga", callback_data="start_back")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)


async def show_weekly(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    top = get_weekly_top(20)
    if not top:
        await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, "🏆 Hali ma'lumot yo'q.")
        return

    titles = get_weekly_titles_dict()
    current_week = datetime.now().isocalendar()[1]
    lines = ["🏆 <b>Haftalik reyting</b>\n"]
    for i, entry in enumerate(top, 1):
        name = entry.get("name", "Noma'lum")
        score = entry.get("score", 0)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        title_info = ""
        uid = entry["user_id"]
        if uid in titles and titles[uid].get("week") == current_week:
            title_info = f" [{titles[uid]['title']}]"
        lines.append(f"{medal} {name} — {score} ball{title_info}")
    await safe_edit_message(
        bot, callback.message.chat.id, callback.message.message_id,
        "\n".join(lines), parse_mode="HTML"
    )


async def show_back(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    from mafia_bot.config import BOT_NAMES
    import random
    bot_name = random.choice(BOT_NAMES)
    text = (
        f"🌙 <b>Night Killers</b> — Mafia o'yini\n\n"
        f"Salom, {callback.from_user.first_name}!\n\n"
        f"👤 <b>Profil:</b> /profil\n"
        f"💰 <b>Hisob:</b> /money\n"
        f"🏆 <b>Reyting:</b> /hafta\n"
        f"🛒 <b>Do'kon:</b> /shop\n"
        f"📊 <b>Statistika:</b> /stats\n"
        f"❓ <b>Yordam:</b> /help\n\n"
        f"O'yin yaratish: /mafia\n"
        f"Qatnashish: /join"
    )
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="👤 Profil", callback_data="start_profile"),
         InlineKeyboardButton(text="💰 Hisob", callback_data="start_money")],
        [InlineKeyboardButton(text="🏆 Reyting", callback_data="start_top"),
         InlineKeyboardButton(text="📊 Statistika", callback_data="start_stats")],
        [InlineKeyboardButton(text="🛒 Do'kon", callback_data="start_shop"),
         InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="start_settings")],
        [InlineKeyboardButton(text="❓ Yordam", callback_data="start_help"),
         InlineKeyboardButton(text="ℹ️ Haqida", callback_data="start_about")],
        [InlineKeyboardButton(text="🏆 Haftalik", callback_data="start_weekly")],
    ])
    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb)
