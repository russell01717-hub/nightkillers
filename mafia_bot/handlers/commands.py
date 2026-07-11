"""All /command handlers"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    CallbackQuery, Message, ErrorEvent
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from ..models import MafiaGame, Player, games, GamePhase
from ..roles import (
    Role, ROLE_ICON, ROLE_DISPLAY, ROLE_DESC, ROLE_TEAM, ROLE_PRICES,
    distribute_roles, IS_NIGHT_ACTIVE
)
from ..config import ADMIN_ID, CARD_NUMBER, MAX_PLAYERS, BOT_NAMES
from ..db import (
    get_profile, save_profile, get_chat_setting, set_chat_setting,
    get_weekly_top, get_weekly_titles_dict, save_weekly_title,
    get_all_profiles, delete_active_game
)
from ..economy import (
    add_olmos, spend_olmos, spend_evro, transfer_olmos,
    can_claim_daily, claim_daily, buy_role, get_shop_text,
    WEEKLY_TOP1_OLMOS, WEEKLY_TOP2_OLMOS,
)
from ..game_engine import (
    make_inline_keyboard, make_game_banner, make_player_card,
    safe_send_message, safe_edit_message, update_game_message,
    start_night_phase, end_game, make_players_keyboard,
)

log = logging.getLogger("MafiaBot.Commands")


def register(dp, bot: Bot):
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_mafia, Command("mafia"))
    dp.message.register(cmd_join, Command("join"))
    dp.message.register(cmd_leave, Command("leave"))
    dp.message.register(cmd_startgame, Command("startgame"))
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(cmd_give, Command("give"))
    dp.message.register(cmd_giveaway, Command("giveaway"))
    dp.message.register(cmd_settings, Command("settings"))
    dp.message.register(cmd_set, Command("set"))
    dp.message.register(cmd_profile, Command("profile"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(cmd_hafta, Command("hafta"))
    dp.message.register(cmd_change, Command("change"))
    dp.message.register(cmd_geroyinfo, Command("geroyinfo"))
    dp.message.register(cmd_send, Command("send"))
    dp.message.register(cmd_addbot, Command("addbot"))
    dp.message.register(cmd_daily, Command("daily"))
    dp.message.register(cmd_pay, Command("pay"))
    dp.message.register(cmd_shop, Command("shop"))
    dp.message.register(cmd_buy, Command("buy"))
    dp.message.register(cmd_about, Command("about"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_rating, Command("rating"))
    dp.message.register(cmd_mystats, Command("stats"))


async def is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except:
        return False


def admin_only(handler):
    async def wrapper(message: Message, bot: Bot):
        user_id = message.from_user.id
        chat_id = message.chat.id
        if user_id == ADMIN_ID:
            return await handler(message, bot)
        if message.chat.type != "private":
            if await is_group_admin(bot, chat_id, user_id):
                return await handler(message, bot)
        await message.answer("❌ Sizda bu buyruqni bajarish huquqi yo'q!")
        return None
    return wrapper


async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    get_profile(user.id, user.first_name, user.username or "")
    try:
        bot_user = await bot.get_me()
        bot_username = bot_user.username
    except:
        bot_username = "Nightkillersbot"

    text = (
        f"<b>🌙 NIGHT KILLERS</b>\n"
        f"<i>Zulmatda hech kim begunoh emas...</i>\n\n"
        f"👤 <b>{user.first_name}</b>, xush kelibsiz!\n\n"
        f"<b>Nega aynan biz?</b>\n"
        f"🌙 40+ xil rol bilan qiziqarli o'yin\n"
        f"🏆 Haftalik reyting va noyob unvonlar\n"
        f"💎 Olmos va 💶 Evro — iqtisod tizimi\n"
        f"🦸 Hero va maxsus imkoniyatlar\n\n"
        f"<b>O'ynash uchun:</b>\n"
        f"1️⃣ Guruhga @{bot_username} qo'shing\n"
        f"2️⃣ /mafia yozib o'yin yarating\n"
        f"3️⃣ /join yoki tugmani bosing\n"
        f"4️⃣ Admin /startgame bilan boshlaydi"
    )

    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="🎮 O'yin yaratish", url=f"https://t.me/{bot_username}?startgroup=new"),
         InlineKeyboardButton(text="➕ Qo'shilish", callback_data="start_join")],
        [InlineKeyboardButton(text="👤 Profil", callback_data="start_profile"),
         InlineKeyboardButton(text="💰 Hisob", callback_data="start_money")],
        [InlineKeyboardButton(text="🏆 Reyting", callback_data="start_top"),
         InlineKeyboardButton(text="🛒 Do'kon", callback_data="start_shop")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="start_stats"),
         InlineKeyboardButton(text="📖 Yordam", callback_data="start_help")],
        [InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="start_about")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def cmd_mafia(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        await message.answer("❌ Bu buyruq faqat guruhlarda ishlaydi!")
        return
    if chat_id in games:
        existing = games[chat_id]
        if existing.phase != GamePhase.ENDED:
            display_name = getattr(existing.phase, 'value', str(existing.phase))
            await message.answer(
                f"❌ Bu guruhda allaqachon o'yin davom etmoqda.\n"
                f"Faza: {display_name}\n"
                f"Avval mavjud o'yinni tugating."
            )
            return

    game = MafiaGame(chat_id)
    games[chat_id] = game
    game.log("game_created", f"by {message.from_user.id}")

    text = (
        f"{make_game_banner(GamePhase.WAITING)}\n\n"
        f"<b>O'yin yaratildi!</b>\n"
        f"Ro'yxatdan o'tish boshlandi.\n\n"
        f"➕ Qo'shilish uchun /join bosing\n"
        f"👥 Minimal: {game.min_players} o'yinchi\n\n"
        f"<b>O'yinchilar:</b>\n"
        f"Hali hech kim qo'shilgani yo'q."
    )

    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="➕ Qo'shilish", callback_data=f"join:{chat_id}")],
        [InlineKeyboardButton(text="❌ Chiqish", callback_data=f"leave:{chat_id}")],
    ])

    sent = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    game.game_msg_id = sent.message_id


async def cmd_join(message: Message, bot: Bot):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas! /mafia yozib o'yin yarating.")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await message.answer("❌ O'yin boshlangan. Yangi o'yinchi qo'shila olmaydi.")
        return
    if user.id in game.players:
        await message.answer("❌ Siz allaqachon o'yindasiz!")
        return
    if len(game.players) >= MAX_PLAYERS:
        await message.answer("❌ O'yin to'liq!")
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
            f"Guruh: {message.chat.title}\n"
            f"O'yin boshlanishini kuting."
        )
    except TelegramForbiddenError:
        pass


async def cmd_leave(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await message.answer("❌ Ro'yxatdan o'tish tugagan!")
        return
    if user_id not in game.players:
        await message.answer("❌ Siz o'yinda emassiz!")
        return
    del game.players[user_id]
    game.log("player_left", f"{user_id}")
    await update_game_message(game, bot)
    await message.answer("✅ O'yindan chiqdingiz.")


async def cmd_startgame(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await message.answer("❌ O'yin allaqachon boshlangan!")
        return
    if user_id != ADMIN_ID:
        if not await is_group_admin(bot, chat_id, user_id):
            await message.answer("❌ Faqat admin o'yinni boshlashi mumkin!")
            return

    player_count = len(game.players)
    if player_count < game.min_players:
        await message.answer(f"❌ Kamida {game.min_players} o'yinchi kerak! Hozir: {player_count}")
        return

    game.phase = GamePhase.STARTING
    game.log("game_starting", f"{player_count} players")

    # Role assignment
    game.phase = GamePhase.ROLE_ASSIGN
    role_pool = distribute_roles(player_count)
    assigned_role_names = set()
    for player in game.players.values():
        profile = get_profile(player.user_id)
        bought = profile.get("bought_role")
        if bought:
            try:
                preferred = Role(bought)
                if preferred in role_pool and preferred.value not in assigned_role_names:
                    player.role = preferred
                    player.team = ROLE_TEAM.get(preferred, "town")
                    role_pool.remove(preferred)
                    assigned_role_names.add(preferred.value)
                    if profile.get("hero"):
                        player.hero_attack = profile.get("hero_attack", 0)
                        player.hero_defense = profile.get("hero_defense", 0)
            except ValueError:
                pass
    for player in game.players.values():
        if player.role is not None:
            continue
        if role_pool:
            role = role_pool.pop(0)
            player.role = role
            player.team = ROLE_TEAM.get(role, "town")
        profile = get_profile(player.user_id)
        if profile.get("hero"):
            player.hero_attack = profile.get("hero_attack", 0)
            player.hero_defense = profile.get("hero_defense", 0)

    game.log("roles_assigned", f"{player_count} roles distributed")

    player_list = "\n".join([f"• {p.display}" for p in game.players.values()])
    text = (
        f"{make_game_banner(GamePhase.STARTING)}\n\n"
        f"<b>O'yinchilar ({player_count}):</b>\n{player_list}\n\n"
        f"{make_game_banner(GamePhase.NIGHT, 1)}"
    )
    if game.game_msg_id:
        await safe_edit_message(bot, game.chat_id, game.game_msg_id, text)

    try:
        bot_user = await bot.get_me()
        bot_username = bot_user.username
    except:
        bot_username = "Nightkillersbot"

    blocked_users = []
    for player in game.players.values():
        role_text = (
            f"🌙 <b>NIGHT KILLERS</b>\n\n"
            f"Sizning rolingiz: <b>{ROLE_DISPLAY.get(player.role, player.role.value if player.role else '?')}</b>\n\n"
            f"{ROLE_DESC.get(player.role, '')}\n\n"
        )
        if player.role and player.team == "mafia":
            teammates = [p for p in game.players.values() if p.team == "mafia" and p.user_id != player.user_id]
            if teammates:
                role_text += "👥 <b>Sizning mafia guruingiz:</b>\n"
                for t in teammates:
                    role_text += f"• {t.display} ({ROLE_ICON.get(t.role, '❓')} {t.role.value if t.role else '?'})\n"
        if player.role == Role.DON:
            role_text += "\n👑 Siz Don sifatida Komissar tekshiruvida begunoh ko'rinasiz!"
        if player.role == Role.GODFATHER:
            role_text += "\n💀 Siz Godfather sifatida tergovda begunoh ko'rinasiz!"
        result = await safe_send_message(bot, player.user_id, role_text)
        if result is None:
            blocked_users.append(player.display)
        await asyncio.sleep(0.05)

    if blocked_users:
        await message.answer(
            f"⚠️ <b>Ogohlantirish:</b>\n"
            f"Quyidagi o'yinchilar botni shaxsiy xabarda ishga tushirmagan:\n"
            f"{chr(10).join('• ' + u for u in blocked_users)}\n\n"
            f"Ular <b>@{bot_username}</b> ga yozib /start bosmagani uchun\n"
            f"rol va tungi tugmalarni ololmaydi!\n"
            f"Iltimos, ularga botga yozishni ayting.",
            parse_mode="HTML"
        )

    await message.answer(
        f"🌙 <b>1-tun boshlandi!</b>\n"
        f"Tun davomiyligi: {game.night_time} soniya\n\n"
        f"Maxsus rollar PM dan harakat qiling."
    )

    await start_night_phase(game, bot)


async def cmd_cancel(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!")
        return

    if user_id != ADMIN_ID and not await is_group_admin(bot, chat_id, user_id):
        await message.answer("❌ Faqat guruh admini o'yinni bekor qilishi mumkin!")
        return

    game = games[chat_id]
    game.cancel_timers()
    game.phase = GamePhase.ENDED
    game.log("game_cancelled", f"by {user_id}")
    del games[chat_id]
    delete_active_game(chat_id)
    await message.answer("❌ O'yin bekor qilindi.")


@admin_only
async def cmd_give(message: Message, bot: Bot):
    chat_id = message.chat.id
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "📝 <b>Farmat:</b> /give @username|user_id olmos [evro]\n"
            "Namuna: /give @user 100 yoki /give 123456789 50 10",
            parse_mode="HTML"
        )
        return

    identifier = args[1].lstrip("@")
    olmos_amount = int(args[2]) if len(args) > 2 else 0
    evro_amount = int(args[3]) if len(args) > 3 else 0

    target_id = None
    target_name = ""
    target_username = ""

    if identifier.isdigit():
        target_id = int(identifier)
        profile = get_profile(target_id)
        target_name = profile.get("name", "")
        target_username = profile.get("username", "")
    else:
        for uid, p in get_all_profiles().items():
            if p.get("username", "").lower() == identifier.lower():
                target_id = uid
                target_name = p.get("name", "")
                target_username = p.get("username", "")
                break

    if not target_id:
        await message.answer(f"❌ Foydalanuvchi @{identifier} topilmadi!")
        return

    if olmos_amount > 0:
        add_olmos(target_id, olmos_amount, target_name, target_username)
    if evro_amount > 0:
        add_olmos(target_id, evro_amount, target_name, target_username)

    await message.answer(
        f"✅ <b>Berildi:</b>\n"
        f"👤 {target_name}\n"
        f"{'💎 ' + str(olmos_amount) if olmos_amount else ''}"
        f"{'💶 ' + str(evro_amount) if evro_amount else ''}",
        parse_mode="HTML"
    )


@admin_only
async def cmd_giveaway(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type == "private":
        await message.answer("❌ Bu buyruq faqat guruhlarda ishlaydi!")
        return
    args = message.text.split()
    if len(args) < 2:
        await message.answer("📝 Farmat: /giveaway <olmos>")
        return
    try:
        amount = int(args[1])
    except ValueError:
        await message.answer("❌ Noto'g'ri miqdor!")
        return
    if amount < 10 or amount > 500:
        await message.answer("❌ Miqdor 10-500 oralig'ida bo'lishi kerak!")
        return

    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!")
        return

    game = games[chat_id]
    participants = [p.display for p in game.players.values() if p.alive]
    if not participants:
        await message.answer("❌ Tirik o'yinchilar yo'q!")
        return

    winner_display = random.choice(participants)
    winner_id = None
    for pid, p in game.players.items():
        if p.display == winner_display and p.alive:
            winner_id = pid
            break

    if winner_id:
        add_olmos(winner_id, amount)
        await message.answer(
            f"🎉 <b>Giveaway!</b>\n\n"
            f"G'olib: {winner_display}\n"
            f"Sovrin: {amount}💎",
            parse_mode="HTML"
        )


async def cmd_settings(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if user_id != ADMIN_ID and not await is_group_admin(bot, chat_id, user_id):
        await message.answer("❌ Faqat admin sozlamalarni ko'ra oladi!")
        return

    night_time = get_chat_setting(chat_id, "night_time", 45)
    vote_time = get_chat_setting(chat_id, "vote_time", 45)
    min_players = get_chat_setting(chat_id, "min_players", 4)
    mode = get_chat_setting(chat_id, "mode", "classic")

    await message.answer(
        f"⚙️ <b>Guruh sozlamalari</b>\n\n"
        f"🌙 Tun davomiyligi: {night_time}s\n"
        f"🗳 Ovoz berish vaqti: {vote_time}s\n"
        f"👥 Minimal o'yinchilar: {min_players}\n"
        f"🎮 Rejim: {mode}\n\n"
        f"/set night <soniya> — tun vaqti\n"
        f"/set vote <soniya> — ovoz vaqti\n"
        f"/set min <son> — minimal o'yinchilar",
        parse_mode="HTML"
    )


@admin_only
async def cmd_set(message: Message, bot: Bot):
    chat_id = message.chat.id
    args = message.text.split()
    if len(args) < 3:
        await message.answer("📝 Farmat: /set <param> <value>")
        return

    param = args[1].lower()
    try:
        value = int(args[2])
    except ValueError:
        await message.answer("❌ Noto'g'ri qiymat!")
        return

    if param == "night":
        if 20 <= value <= 180:
            set_chat_setting(chat_id, "night_time", value)
            await message.answer(f"✅ Tun vaqti {value}s ga o'rnatildi!")
        else:
            await message.answer("❌ 20-120 oralig'ida bo'lishi kerak!")
    elif param == "vote":
        if 20 <= value <= 180:
            set_chat_setting(chat_id, "vote_time", value)
            await message.answer(f"✅ Ovoz berish vaqti {value}s ga o'rnatildi!")
        else:
            await message.answer("❌ 20-120 oralig'ida bo'lishi kerak!")
    elif param == "min":
        if 4 <= value <= 100:
            set_chat_setting(chat_id, "min_players", value)
            await message.answer(f"✅ Minimal o'yinchilar {value} ga o'rnatildi!")
        else:
            await message.answer("❌ 4-100 oralig'ida bo'lishi kerak!")
    else:
        await message.answer("❌ Noma'lum parametr! night | vote | min")


async def cmd_profile(message: Message, bot: Bot):
    user = message.from_user
    args = message.text.split()
    target_id = user.id
    if len(args) > 1:
        identifier = args[1].lstrip("@")
        if identifier.isdigit():
            target_id = int(identifier)
        else:
            for uid, p in get_all_profiles().items():
                if p.get("username", "").lower() == identifier.lower():
                    target_id = uid
                    break

    profile = get_profile(target_id)
    name = profile.get("name", "Noma'lum")
    username = profile.get("username", "")
    olmos = profile.get("olmos", 0)
    evro = profile.get("evro", 0)
    games_count = profile.get("games", 0)
    wins = profile.get("wins", 0)
    losses = profile.get("losses", 0)
    bought = profile.get("bought_role", "")
    hero = profile.get("hero", 0)

    winrate = round(wins / games_count * 100, 1) if games_count else 0
    username_line = f" @{username}" if username else ""

    await message.answer(
        f"👤 <b>{name}</b>{username_line}\n"
        f"├ ID: <code>{target_id}</code>\n"
        f"├ 💎 Olmos: {olmos}\n"
        f"├ 💶 Evro: {evro}\n"
        f"├ 🎮 O'yinlar: {games_count}\n"
        f"├ 🏆 G'alabalar: {wins}\n"
        f"├ 💀 Mag'lubiyatlar: {losses}\n"
        f"├ 📊 Winrate: {winrate}%\n"
        f"├ 🎭 Sotib olingan rol: {bought if bought else 'Yoq'}\n"
        f"└ 🦸 Hero: {'✅' if hero else '❌'}",
        parse_mode="HTML"
    )


async def cmd_status(message: Message, bot: Bot):
    chat_id = message.chat.id
    if chat_id not in games:
        await message.answer("❌ Bu guruhda o'yin mavjud emas!")
        return
    game = games[chat_id]
    phase_name = getattr(game.phase, 'value', str(game.phase))
    text = (
        f"<b>O'yin statusi</b>\n\n"
        f"Faza: {phase_name}\n"
        f"Kun: {game.day}\n"
        f"Jami o'yinchilar: {len(game.players)}\n"
        f"Tirik: {len(game.alive_players)}\n"
        f"O'lgan: {len(game.dead_players)}\n\n"
        f"<b>Jonli:</b>\n" + "\n".join([make_player_card(p) for p in game.alive_players])
    )
    await message.answer(text, parse_mode="HTML")


async def cmd_hafta(message: Message, bot: Bot):
    top = get_weekly_top(20)
    if not top:
        await message.answer("🏆 <b>Haftalik reyting:</b>\n\nHali hech qanday ma'lumot yo'q.", parse_mode="HTML")
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
    lines.append(f"\n🏅 Top 1: {WEEKLY_TOP1_OLMOS}💎 | Top 2: {WEEKLY_TOP2_OLMOS}💎")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def cmd_change(message: Message, bot: Bot):
    user = message.from_user
    user_id = user.id
    profile = get_profile(user_id)
    bought = profile.get("bought_role")
    if not bought:
        await message.answer("❌ Siz hech qanday rol sotib olmagansiz! /shop orqali rol oling.")
        return
    try:
        role = Role(bought)
        await message.answer(
            f"🎭 Sizning sotib olingan rolingiz: <b>{ROLE_ICON.get(role, '❓')} {role.value}</b>\n"
            f"Rol haqida: {ROLE_DESC.get(role, '')}",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(f"❌ Xatolik: noto'g'ri rol ma'lumoti.")


async def cmd_geroyinfo(message: Message, bot: Bot):
    await message.answer(
        "🦸 <b>HERO TIZIMI</b>\n\n"
        "Hero — bu o'yinchiga qo'shimcha kuch beradi.\n\n"
        "Qanday olish mumkin:\n"
        "• Yuqori haftalik reytingda 1-o'rin: +1 Hero\n"
        "• Maxsus tadbirlarda yutish\n"
        "• Premium do'kondan sotib olish\n\n"
        "Hero xususiyatlari:\n"
        "• Hujum (Attack): tungi hujumda qo'shimcha kuch\n"
        "• Himoya (Defense): tungi hujumdan himoya qiladi\n\n"
        "Har bir Hero darajasi bilan kuch oshadi.",
        parse_mode="HTML"
    )


async def cmd_send(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) < 3:
        await message.answer("📝 Farmat: /send @username|user_id <olmos>")
        return

    identifier = args[1].lstrip("@")
    try:
        amount = int(args[2])
    except ValueError:
        await message.answer("❌ Noto'g'ri miqdor!")
        return

    if amount < 1:
        await message.answer("❌ Miqdor 1 dan kichik bo'lishi mumkin emas!")
        return

    target_id = None
    target_name = ""
    target_username = ""

    if identifier.isdigit():
        target_id = int(identifier)
        profile = get_profile(target_id)
        target_name = profile.get("name", "")
        target_username = profile.get("username", "")
    else:
        for uid, p in get_all_profiles().items():
            if p.get("username", "").lower() == identifier.lower():
                target_id = uid
                target_name = p.get("name", "")
                target_username = p.get("username", "")
                break

    if not target_id:
        await message.answer(f"❌ Foydalanuvchi @{identifier} topilmadi!")
        return
    if target_id == user_id:
        await message.answer("❌ O'zingizga o'zingiz yubora olmaysiz!")
        return

    user_profile = get_profile(user_id, message.from_user.first_name, message.from_user.username or "")
    if user_profile.get("olmos", 0) < amount:
        await message.answer(f"❌ Sizda yetarli olmos yo'q! ({user_profile.get('olmos', 0)}💎)")
        return

    if transfer_olmos(user_id, target_id, amount):
        await message.answer(f"✅ {amount}💎 {target_name} ga yuborildi!", parse_mode="HTML")
        try:
            await bot.send_message(
                target_id,
                f"💎 Sizga {amount} olmos keldi!\n"
                f"Kimdan: {message.from_user.first_name}"
            )
        except:
            pass
    else:
        await message.answer("❌ Xatolik yuz berdi!")


@admin_only
async def cmd_addbot(message: Message, bot: Bot):
    chat_id = message.chat.id
    if chat_id not in games:
        await message.answer("❌ O'yin mavjud emas!")
        return
    game = games[chat_id]
    if game.phase != GamePhase.WAITING:
        await message.answer("❌ O'yin boshlangan!")
        return
    if len(game.players) >= MAX_PLAYERS:
        await message.answer("❌ O'yin to'liq!")
        return

    bot_name = random.choice(BOT_NAMES)
    fake_id = random.randint(10**9, 10**10 - 1)
    while fake_id in game.players:
        fake_id = random.randint(10**9, 10**10 - 1)

    game.players[fake_id] = Player(
        user_id=fake_id, name=bot_name, username="", is_bot=True
    )
    game.log("bot_added", f"{bot_name} ({fake_id})")
    await update_game_message(game, bot)
    await message.answer(f"🤖 Bot qo'shildi: {bot_name}")


async def cmd_daily(message: Message, bot: Bot):
    user = message.from_user
    can_claim, remaining = can_claim_daily(user.id)
    if not can_claim:
        hours, mins = divmod(remaining // 60, 60)
        await message.answer(
            f"⏳ Keyingi daily bonus: {hours}h {mins}m dan keyin",
            parse_mode="HTML"
        )
        return

    olmos, evro = claim_daily(user.id, user.first_name, user.username or "")
    await message.answer(
        f"✅ <b>Kunlik bonus!</b>\n\n"
        f"+{olmos}💎 Olmos\n"
        f"+{evro}💶 Evro\n\n"
        f"Ertaga yana keling!",
        parse_mode="HTML"
    )


async def cmd_pay(message: Message, bot: Bot):
    user = message.from_user
    if message.chat.type == "private":
        await message.answer(
            f"💳 <b>To'lov</b>\n\n"
            f"Karta: <code>{CARD_NUMBER}</code>\n"
            f"Summa: 50💎\n\n"
            f"To'lov qilgach, chekni rasm sifatida yuboring.\n"
            f"Admin tasdiqlagach +50💎 hisobingizga tushadi.",
            parse_mode="HTML"
        )
    else:
        await message.answer("ℹ️ To'lov uchun botga yozing: @Nightkillersbot")


async def cmd_shop(message: Message, bot: Bot):
    user = message.from_user
    text = get_shop_text(user.id)
    kb = make_inline_keyboard([
        [InlineKeyboardButton(text="🔄 Sotib olish", callback_data="shop_buy")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def cmd_buy(message: Message, bot: Bot):
    user = message.from_user
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "📝 Farmat: /buy <rol nomi>\n"
            "Rollar ro'yxati: /shop",
            parse_mode="HTML"
        )
        return
    role_name = " ".join(args[1:])
    for role in Role:
        if role.value.lower() == role_name.lower():
            success, msg = buy_role(user.id, role)
            await message.answer(f"{'✅' if success else '❌'} {msg}", parse_mode="HTML")
            return
    await message.answer(f"❌ '{role_name}' roli topilmadi! /shop ga qarang.")


async def cmd_about(message: Message, bot: Bot):
    from mafia_bot.roles import Role, TOWN_ROLES, MAFIA_ROLES, NEUTRAL_ROLES, ROLE_ICON
    town_list = ", ".join(f"{ROLE_ICON[r]} {r.value}" for r in TOWN_ROLES)
    mafia_list = ", ".join(f"{ROLE_ICON[r]} {r.value}" for r in MAFIA_ROLES)
    neutral_list = ", ".join(f"{ROLE_ICON[r]} {r.value}" for r in NEUTRAL_ROLES)
    await message.answer(
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
        f"Powered by aiogram 3.x",
        parse_mode="HTML"
    )


async def cmd_help(message: Message, bot: Bot):
    text = (
        "📖 <b>Buyruqlar ro'yxati:</b>\n\n"
        "<b>O'yin:</b>\n"
        "/mafia — O'yin yaratish\n"
        "/join — O'yinga qo'shilish\n"
        "/leave — O'yindan chiqish\n"
        "/startgame — O'yinni boshlash (admin)\n"
        "/cancel — O'yinni bekor qilish (admin)\n"
        "/status — O'yin statusi\n"
        "/addbot — Bot qo'shish (admin)\n\n"
        "<b>Profil va Iqtisod:</b>\n"
        "/profile — Profilingiz\n"
        "/send — Olmos yuborish\n"
        "/daily — Kunlik bonus\n"
        "/shop — Rollar do'koni\n"
        "/buy — Rol sotib olish\n"
        "/pay — To'lov qilish\n"
        "/change — Sotib olingan rol\n\n"
        "<b>Reyting:</b>\n"
        "/hafta — Haftalik reyting\n"
        "/stats — Shaxsiy statistika\n"
        "/rating — Umumiy reyting\n\n"
        "<b>Ma'lumot:</b>\n"
        "/geroyinfo — Hero tizimi\n"
        "/about — Bot haqida\n"
        "/help — Yordam"
    )
    await message.answer(text, parse_mode="HTML")


async def cmd_rating(message: Message, bot: Bot):
    profiles = get_all_profiles()
    sorted_profiles = sorted(
        profiles.values(),
        key=lambda p: p.get("wins", 0) + p.get("olmos", 0),
        reverse=True
    )[:20]
    lines = ["🏆 <b>Global reyting</b>\n"]
    for i, p in enumerate(sorted_profiles, 1):
        name = p.get("name", "Noma'lum")
        score = p.get("wins", 0) + p.get("olmos", 0)
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        lines.append(f"{medal} {name} — {score}")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def cmd_mystats(message: Message, bot: Bot):
    user = message.from_user
    profile = get_profile(user.id)
    g = profile.get("games", 0)
    w = profile.get("wins", 0)
    l = profile.get("losses", 0)
    wr = round(w / g * 100, 1) if g else 0
    await message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👤 {user.first_name}\n"
        f"├ 🎮 O'yinlar: {g}\n"
        f"├ 🏆 G'alaba: {w}\n"
        f"├ 💀 Mag'lubiyat: {l}\n"
        f"├ 📊 Winrate: {wr}%\n"
        f"└ 💰 {profile.get('olmos', 0)}💎 | {profile.get('evro', 0)}💶",
        parse_mode="HTML"
    )
