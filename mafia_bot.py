import os
import sys
sys.path.insert(0, r"D:\pylibs")
import random
import logging
import asyncio
from typing import Dict, Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN", "8388604050:AAFLH3sa6kIbg3YuuiLGMp1VBJT0JT2X9vg")
MIN_PLAYERS = 1
MAX_PLAYERS = 40
NIGHT_SEC = 30
VOTE_SEC = 30

NIGHT_GIF = "https://t.me/c/3615854881/765308"
DAY_GIF = "https://t.me/c/3615854881/765314"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

games: Dict[int, "MafiaGame"] = {}


class Player:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name
        self.role = None
        self.alive = True
        self.lover = None
        self.defended = False
        self.guard_target = None
        self.journal_target = None


class MafiaGame:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.players: Dict[int, Player] = {}
        self.phase = "registration"
        self.day = 0
        self.votes: Dict[int, int] = {}
        self.night_target = None
        self.save_target = None
        self.check_target = None
        self.check_result = None
        self.maniac_target = None
        self.journal_target = None
        self.mafia_ready = False
        self.doctor_ready = False
        self.sheriff_ready = False
        self.maniac_ready = False
        self.journalist_ready = False
        self.bodyguard_ready = False
        self.night_eliminated = []
        self.maniac_present = False

    @property
    def alive_players(self):
        return [p for p in self.players.values() if p.alive]

    @property
    def mafia_alive(self):
        return [p for p in self.players.values() if p.role in ("Mafia", "Don") and p.alive]

    @property
    def don_player(self):
        for p in self.players.values():
            if p.role == "Don" and p.alive:
                return p
        return None

    def get_player(self, user_id: int) -> Optional[Player]:
        return self.players.get(user_id)

    def alive_count(self):
        return len(self.alive_players)

    def mafia_count(self):
        return len(self.mafia_alive)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Mafia botga xush kelibsiz. Guruhga qo'shib, /mafia yozing.")


async def mafia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("Bu buyruq faqat guruhda ishlaydi!")
        return
    if chat.id in games:
        await update.message.reply_text("O'yin allaqachon boshlangan! /join orqali qo'shiling.")
        return
    games[chat.id] = MafiaGame(chat.id)
    await update.message.reply_text(
        "\U0001f3ad **Mafia o'yini boshlanadi!**\n\n"
        "Qo'shilish uchun /join bosing\n"
        "O'yinni boshlash uchun /startgame\n"
        f"Min: {MIN_PLAYERS} / Max: {MAX_PLAYERS} o'yinchi\n"
        "Rollar: Mafia, Don, Doctor, Sheriff, Manik, Jurnalist, Advokat, Bodyguard, Oshiq, Tinch aholi\n"
        "Chiqish uchun /leave"
    )


async def find_target(game: MafiaGame, args, update: Update):
    target_text = args[0].lstrip("@")
    for pl in game.alive_players:
        if pl.name.lower() == target_text.lower() or str(pl.user_id) == target_text:
            return pl
        if update.effective_message and update.effective_message.entities:
            for ent in update.effective_message.entities:
                if ent.type == "mention" and ent.user and ent.user.id == pl.user_id:
                    return pl
    return None


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        await update.message.reply_text("O'yin mavjud emas. /mafia yozing.")
        return
    game = games[chat.id]
    if game.phase != "registration":
        await update.message.reply_text("O'yin boshlangan, qo'shilish mumkin emas.")
        return
    user = update.effective_user
    if user.id in game.players:
        await update.message.reply_text("Siz allaqachon o'yinga qo'shilgansiz!")
        return
    if len(game.players) >= MAX_PLAYERS:
        await update.message.reply_text(f"Maksimal {MAX_PLAYERS} o'yinchi! To'liq.")
        return
    name = user.first_name or user.username or str(user.id)
    game.players[user.id] = Player(user.id, name)
    cnt = len(game.players)
    await update.message.reply_text(f"{name} o'yinga qo'shildi! ({cnt}/{MAX_PLAYERS})")


async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "registration":
        return
    user = update.effective_user
    if user.id in game.players:
        del game.players[user.id]
        await update.message.reply_text(f"{update.effective_user.first_name} o'yinni tark etdi.")


def assign_roles(game: MafiaGame):
    players = list(game.players.keys())
    random.shuffle(players)
    n = len(players)
    roles = []
    mafia_count = max(1, n // 5)
    roles.extend(["Mafia"] * (mafia_count - 1))
    roles.append("Don")
    if n >= 4:
        roles.append("Doctor")
    if n >= 5:
        roles.append("Sheriff")
    if n >= 8:
        roles.append("Manik")
        game.maniac_present = True
    if n >= 10:
        roles.append("Jurnalist")
    if n >= 12:
        roles.append("Advokat")
    if n >= 15:
        roles.append("Bodyguard")
    if n >= 18:
        roles.extend(["Oshiq", "Oshiq"])
    if n >= 22:
        roles.append("Doctor")
    if n >= 25:
        roles.append("Mafia")
        mafia_count += 1
    if n >= 30:
        roles.append("Sheriff")
    if n >= 35:
        roles.append("Mafia")
        mafia_count += 1
    if n >= 38:
        roles.append("Bodyguard")
    remaining = n - len(roles)
    roles.extend(["Tinch aholi"] * remaining)
    random.shuffle(roles)
    for uid, role in zip(players, roles):
        game.players[uid].role = role
        game.players[uid].alive = True
    return mafia_count, n


async def send_role_messages(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    mafia_names = [p.name for p in game.mafia_alive]
    lovers = [p for p in game.players.values() if p.role == "Oshiq"]
    if len(lovers) >= 2:
        lovers[0].lover = lovers[1].user_id
        lovers[1].lover = lovers[0].user_id
    role_icons = {
        "Don": "Don", "Mafia": "Mafia", "Doctor": "Doctor",
        "Sheriff": "Sheriff", "Manik": "Manik", "Jurnalist": "Jurnalist",
        "Advokat": "Advokat", "Bodyguard": "Bodyguard",
        "Oshiq": "Oshiq", "Tinch aholi": "Tinch aholi"
    }
    for uid, p in game.players.items():
        try:
            text = f"Sizning rolingiz: **{role_icons[p.role]}**\n\n"
            if p.role == "Don":
                text += f"Mafia: {', '.join(mafia_names)}\nSheriff sizni ko'rmaydi.\n/kill @user"
            elif p.role == "Mafia":
                text += f"Mafia: {', '.join(mafia_names)}\n/kill @user"
            elif p.role == "Doctor":
                text += "/save @user"
            elif p.role == "Sheriff":
                text += "/check @user (Donni topolmaysiz)"
            elif p.role == "Manik":
                text += "Yolg'iz qotil! /kill @user"
            elif p.role == "Jurnalist":
                text += "/jurnal @user"
            elif p.role == "Advokat":
                text += "/defend @user (1 marta, kunduzi)"
            elif p.role == "Bodyguard":
                text += "/guard @user (o'zingiz o'lasiz)"
            elif p.role == "Oshiq":
                lover = [x for x in game.players.values() if x.user_id != uid and x.role == "Oshiq"]
                text += f"Sevgingiz: {lover[0].name if lover else '?'}\nBiringiz o'lsangiz, ikkalangiz o'lasiz!"
            else:
                text += "Oddiy fuqaro. Ovoz berib mafiani toping!"
            await context.bot.send_message(chat_id=uid, text=text)
        except Exception as e:
            logging.warning(f"Could not send to {uid}: {e}")


async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        await update.message.reply_text("O'yin mavjud emas. /mafia yozing.")
        return
    game = games[chat.id]
    if game.phase != "registration":
        await update.message.reply_text("O'yin allaqachon boshlangan!")
        return
    if len(game.players) < MIN_PLAYERS:
        await update.message.reply_text(f"Kamida {MIN_PLAYERS} o'yinchi kerak! Hozir: {len(game.players)}")
        return
    mafia_count, total = assign_roles(game)
    await send_role_messages(game, context)
    mafia_names = ", ".join([p.name for p in game.mafia_alive])
    await update.message.reply_text(
        f"\U0001f3ad **O'yin boshlandi!**\n\n"
        f"Jami: {total} o'yinchi\nMafia: {mafia_count} ta\n\n"
        f"\U0001f303 **1-tun** – {NIGHT_SEC} soniya"
    )
    game.phase = "night"
    game.day = 1
    game.maniac_present = any(p.role == "Manik" and p.alive for p in game.players.values())
    reset_night_state(game)
    await send_night_animation(game, context)
    asyncio.create_task(night_timer(game, context))


def reset_night_state(game: MafiaGame):
    game.night_target = None
    game.save_target = None
    game.check_target = None
    game.check_result = None
    game.maniac_target = None
    game.journal_target = None
    game.mafia_ready = False
    game.doctor_ready = False
    game.sheriff_ready = False
    game.maniac_ready = False
    game.journalist_ready = False
    game.bodyguard_ready = False
    game.night_eliminated = []


async def send_night_animation(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_animation(chat_id=game.chat_id, animation=NIGHT_GIF)
    except Exception:
        pass
    await context.bot.send_message(
        game.chat_id,
        f"\U0001f319 **{game.day}-tun** ({NIGHT_SEC} soniya)\nMafia, Manik, Doctor, Sheriff, Jurnalist, Bodyguard harakat qilsin!"
    )
    for p in game.alive_players:
        try:
            if p.role in ("Don", "Mafia"):
                await context.bot.send_message(p.user_id, "/kill @user")
            elif p.role == "Doctor":
                await context.bot.send_message(p.user_id, "/save @user")
            elif p.role == "Sheriff":
                await context.bot.send_message(p.user_id, "/check @user")
            elif p.role == "Manik":
                await context.bot.send_message(p.user_id, "/kill @user (Manik)")
            elif p.role == "Jurnalist":
                await context.bot.send_message(p.user_id, "/jurnal @user")
            elif p.role == "Bodyguard":
                await context.bot.send_message(p.user_id, "/guard @user")
        except Exception as e:
            logging.warning(f"Night msg error for {p.user_id}: {e}")


async def send_day_animation(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_animation(chat_id=game.chat_id, animation=DAY_GIF)
    except Exception:
        pass


async def night_timer(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(NIGHT_SEC)
    if game.chat_id in games and game.phase == "night":
        await resolve_night(game, context)


async def vote_timer(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(VOTE_SEC)
    if game.chat_id in games and game.phase == "vote":
        await resolve_vote(game, context)


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "night":
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or not p.alive or p.role not in ("Mafia", "Don", "Manik"):
        await update.message.reply_text("Siz mafia/manik emassiz yoki tirik emassiz!")
        return
    if not context.args:
        await update.message.reply_text("Masalan: /kill @username")
        return
    target = await find_target(game, context.args, update)
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    if target.user_id == user.id:
        await update.message.reply_text("O'zingizni o'ldira olmaysiz!")
        return
    if p.role in ("Mafia", "Don"):
        if target.role in ("Mafia", "Don"):
            await update.message.reply_text("Mafia a'zosini o'ldira olmaysiz!")
            return
        game.night_target = target.user_id
        game.mafia_ready = True
        await update.message.reply_text(f"Kill: {target.name}")
    elif p.role == "Manik":
        game.maniac_target = target.user_id
        game.maniac_ready = True
        await update.message.reply_text(f"Manik kill: {target.name}")
    await check_night_ready(game, context)


async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "night":
        await update.message.reply_text("Hozir tun emas!")
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or p.role != "Doctor" or not p.alive:
        return
    if not context.args:
        await update.message.reply_text("Masalan: /save @username")
        return
    target = await find_target(game, context.args, update)
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    game.save_target = target.user_id
    game.doctor_ready = True
    await update.message.reply_text(f"Save: {target.name}")
    await check_night_ready(game, context)


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "night":
        await update.message.reply_text("Hozir tun emas!")
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or p.role != "Sheriff" or not p.alive:
        return
    if not context.args:
        await update.message.reply_text("Masalan: /check @username")
        return
    target = await find_target(game, context.args, update)
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    if target.user_id == user.id:
        await update.message.reply_text("O'zingizni tekshira olmaysiz!")
        return
    game.check_target = target.user_id
    is_mafia = target.role in ("Mafia", "Manik")
    if target.role == "Don":
        is_mafia = False
    game.check_result = is_mafia
    game.sheriff_ready = True
    result_text = "Mafia" if is_mafia else "Mafia emas"
    await update.message.reply_text(f"{target.name}: {result_text}")
    await check_night_ready(game, context)


async def journal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "night":
        await update.message.reply_text("Hozir tun emas!")
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or p.role != "Jurnalist" or not p.alive:
        return
    if not context.args:
        await update.message.reply_text("Masalan: /jurnal @username")
        return
    target = await find_target(game, context.args, update)
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    if target.user_id == user.id:
        await update.message.reply_text("O'zingizni tekshira olmaysiz!")
        return
    game.journal_target = target.user_id
    game.journalist_ready = True
    role_names = {
        "Don": "Don (Mafia boshlig'i)", "Mafia": "Mafia", "Doctor": "Doctor",
        "Sheriff": "Sheriff", "Manik": "Manik (Yolg'iz qotil)", "Jurnalist": "Jurnalist",
        "Advokat": "Advokat", "Bodyguard": "Bodyguard", "Oshiq": "Oshiq", "Tinch aholi": "Fuqaro"
    }
    await update.message.reply_text(f"{target.name}: {role_names.get(target.role, target.role)}")
    await check_night_ready(game, context)


async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "night":
        await update.message.reply_text("Hozir tun emas!")
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or p.role != "Bodyguard" or not p.alive:
        return
    if not context.args:
        await update.message.reply_text("Masalan: /guard @username")
        return
    target = await find_target(game, context.args, update)
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    game.bodyguard_ready = True
    p.guard_target = target.user_id
    await update.message.reply_text(f"Guard: {target.name}")
    await check_night_ready(game, context)


async def defend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "vote":
        await update.message.reply_text("Hozir ovoz berish vaqti emas!")
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or p.role != "Advokat" or not p.alive:
        return
    if p.defended:
        await update.message.reply_text("Himoyangizni ishlatgansiz!")
        return
    if not context.args:
        await update.message.reply_text("Masalan: /defend @username")
        return
    target = await find_target(game, context.args, update)
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    p.defended = True
    target.defended = True
    await update.message.reply_text(f"{target.name} himoya qilindi!")


async def check_night_ready(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    has_mafia = game.mafia_count() > 0
    has_doctor = any(p.role == "Doctor" and p.alive for p in game.players.values())
    has_sheriff = any(p.role == "Sheriff" and p.alive for p in game.players.values())
    has_maniac = any(p.role == "Manik" and p.alive for p in game.players.values())
    has_journalist = any(p.role == "Jurnalist" and p.alive for p in game.players.values())
    has_bodyguard = any(p.role == "Bodyguard" and p.alive for p in game.players.values())

    if (not has_mafia or game.mafia_ready) and (not has_doctor or game.doctor_ready) and \
       (not has_sheriff or game.sheriff_ready) and (not has_maniac or game.maniac_ready) and \
       (not has_journalist or game.journalist_ready) and (not has_bodyguard or game.bodyguard_ready):
        await resolve_night(game, context)


async def resolve_night(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    if game.phase != "night":
        return
    game.phase = "resolving"
    await send_day_animation(game, context)
    msg = f"\U0001f306 **{game.day}-kun**\n\n"
    eliminated = []

    mafia_target = game.players.get(game.night_target) if game.night_target else None
    save_target = game.players.get(game.save_target) if game.save_target else None
    maniac_target = game.players.get(game.maniac_target) if game.maniac_target else None

    bodyguard_client = None
    for p in game.players.values():
        if p.role == "Bodyguard" and p.alive and p.guard_target:
            bodyguard_client = p.guard_target
            break

    if mafia_target:
        if save_target and save_target.user_id == mafia_target.user_id:
            msg += f"Doctor qutqardi! {mafia_target.name} omon qoldi.\n"
        elif bodyguard_client == mafia_target.user_id:
            bg = next((p for p in game.players.values() if p.role == "Bodyguard" and p.alive and p.guard_target == mafia_target.user_id), None)
            if bg:
                bg.alive = False
                eliminated.append(bg)
                msg += f"Bodyguard {mafia_target.name} ni qo'riqlab o'ldi!\n"
        else:
            mafia_target.alive = False
            eliminated.append(mafia_target)
            msg += f"Mafia {mafia_target.name} ni o'ldirdi ({mafia_target.role})\n"

    if maniac_target and maniac_target.alive:
        if bodyguard_client == maniac_target.user_id:
            bg = next((p for p in game.players.values() if p.role == "Bodyguard" and p.alive and p.guard_target == maniac_target.user_id), None)
            if bg and bg not in eliminated:
                bg.alive = False
                eliminated.append(bg)
                msg += f"Bodyguard Manikdan qo'riqlab o'ldi!\n"
        else:
            maniac_target.alive = False
            if maniac_target not in eliminated:
                eliminated.append(maniac_target)
                msg += f"Manik {maniac_target.name} ni o'ldirdi ({maniac_target.role})\n"

    for p in eliminated[:]:
        if p.lover:
            lover = game.players.get(p.lover)
            if lover and lover.alive and lover not in eliminated:
                lover.alive = False
                eliminated.append(lover)
                msg += f"Oshiq {p.name} bilan {lover.name} ham o'ldi!\n"

    for p in eliminated[:]:
        if p.role == "Bomba":
            alive_list = [x for x in game.alive_players if x.user_id != p.user_id]
            if alive_list:
                bt = random.choice(alive_list)
                bt.alive = False
                eliminated.append(bt)
                msg += f"Bomba portladi! {bt.name} ham o'ldi!\n"

    if game.check_result is not None and game.check_target:
        checked = game.players.get(game.check_target)
        if checked:
            msg += f"Sheriff: {checked.name} - {'Mafia' if game.check_result else 'Mafia emas'}\n"

    if game.journal_target:
        je = game.players.get(game.journal_target)
        if je:
            msg += f"Jurnalist: {je.name} = {je.role}\n"

    if not eliminated:
        msg += "Tinch tun, hech kim o'lmadi.\n"

    winner = check_winner(game)
    if winner:
        msg += f"\nO'yin tugadi! {winner}"
        await context.bot.send_message(game.chat_id, msg)
        game.phase = "ended"
        if game.chat_id in games:
            del games[game.chat_id]
        return

    alive_list = "\n".join([f"{i+1}. {p.name} ({p.role})" for i, p in enumerate(game.alive_players)])
    msg += f"\n**Tirik ({game.alive_count()}):**\n{alive_list}"
    msg += f"\n\nOvoz berish ({VOTE_SEC} soniya): /vote @user"
    if any(p.role == "Advokat" and p.alive and not p.defended for p in game.players.values()):
        msg += "\nAdvokat: /defend @user"
    game.phase = "vote"
    game.votes = {}
    await context.bot.send_message(game.chat_id, msg)
    asyncio.create_task(vote_timer(game, context))


async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "vote":
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or not p.alive:
        return
    if not context.args:
        await update.message.reply_text("Masalan: /vote @username")
        return
    target = await find_target(game, context.args, update)
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    if target.user_id == user.id:
        await update.message.reply_text("O'zingizga ovoz bera olmaysiz!")
        return
    game.votes[user.id] = target.user_id
    voted = len(game.votes)
    total = game.alive_count()
    await update.message.reply_text(f"{target.name} ga ovoz berdingiz ({voted}/{total})")
    if voted >= total:
        await resolve_vote(game, context)


async def resolve_vote(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    if game.phase != "vote":
        return
    game.phase = "resolving"
    vote_count = {}
    for uid, target_id in game.votes.items():
        vote_count[target_id] = vote_count.get(target_id, 0) + 1
    if not vote_count:
        await context.bot.send_message(game.chat_id, "Hech kim ovoz bermadi.")
        await start_night(game, context)
        return
    max_votes = max(vote_count.values())
    max_voted = [uid for uid, cnt in vote_count.items() if cnt == max_votes]
    msg = "**Ovoz natijalari:**\n"
    for uid, cnt in sorted(vote_count.items(), key=lambda x: -x[1]):
        pl = game.players.get(uid)
        if pl:
            msg += f"{pl.name}: {cnt} ovoz\n"
    if len(max_voted) == 1:
        eliminated = game.players.get(max_voted[0])
        if eliminated:
            if eliminated.defended:
                msg += f"Advokat {eliminated.name} ni himoya qildi! Haydalmadi!"
                eliminated.defended = False
            else:
                eliminated.alive = False
                msg += f"{eliminated.name} haydaldi ({eliminated.role})"
                if eliminated.lover:
                    lover = game.players.get(eliminated.lover)
                    if lover and lover.alive:
                        lover.alive = False
                        msg += f"\nOshiq {eliminated.name} bilan {lover.name} ham o'ldi!"
                if eliminated.role == "Bomba":
                    alive_list = [p for p in game.alive_players if p.user_id != eliminated.user_id]
                    if alive_list:
                        bomb_target = random.choice(alive_list)
                        bomb_target.alive = False
                        msg += f"\nBomba portladi! {bomb_target.name} ham o'ldi!"
    else:
        msg += "Ovozlar teng, hech kim haydalmadi."
    winner = check_winner(game)
    if winner:
        msg += f"\n\nO'yin tugadi! {winner}"
        await context.bot.send_message(game.chat_id, msg)
        game.phase = "ended"
        if game.chat_id in games:
            del games[game.chat_id]
        return
    alive_list = "\n".join([f"{i+1}. {p.name} ({p.role})" for i, p in enumerate(game.alive_players)])
    msg += f"\n\n**Tirik ({game.alive_count()}):**\n{alive_list}"
    await context.bot.send_message(game.chat_id, msg)
    await start_night(game, context)


async def start_night(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    game.day += 1
    game.phase = "night"
    for p in game.players.values():
        p.guard_target = None
    game.maniac_present = any(p.role == "Manik" and p.alive for p in game.players.values())
    reset_night_state(game)
    game.votes = {}
    await send_night_animation(game, context)
    asyncio.create_task(night_timer(game, context))


def check_winner(game: MafiaGame):
    alive = game.alive_players
    mafia_alive = len([p for p in alive if p.role in ("Mafia", "Don")])
    maniac_alive = len([p for p in alive if p.role == "Manik"])
    village_alive = len([p for p in alive if p.role not in ("Mafia", "Don", "Manik")])
    roles_left = {p.role for p in alive}
    if maniac_alive > 0 and len(roles_left) == 1:
        return "Manik yutdi!"
    if not mafia_alive and not maniac_alive:
        return "Tinch aholi yutdi!"
    if mafia_alive >= village_alive + maniac_alive:
        return "Mafia yutdi!"
    return None


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        await update.message.reply_text("O'yin mavjud emas.")
        return
    game = games[chat.id]
    items = []
    for p in game.players.values():
        icon = "\U0001f7e2" if p.alive else "\U0001f480"
        items.append(f"{icon} {p.name} ({p.role})")
    await update.message.reply_text(
        f"**O'yin holati**\nFaza: {game.phase}\nKun: {game.day}\n"
        f"O'yinchilar: {len(game.players)} (tirik: {game.alive_count()})\n\n" + "\n".join(items)
    )


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mafia", mafia))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("leave", leave))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("kill", kill))
    app.add_handler(CommandHandler("save", save))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("jurnal", journal))
    app.add_handler(CommandHandler("guard", guard))
    app.add_handler(CommandHandler("defend", defend))
    app.add_handler(CommandHandler("vote", vote))
    app.add_handler(CommandHandler("status", status))
    logging.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
