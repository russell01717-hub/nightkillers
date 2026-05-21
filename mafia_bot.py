import os
import random
import logging
from typing import Dict, Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN", "8388604050:AAFLH3sa6kIbg3YuuiLGMp1VBJT0JT2X9vg")
MIN_PLAYERS = 1
MAX_PLAYERS = 40

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

games: Dict[int, "MafiaGame"] = {}


class Player:
    def __init__(self, user_id: int, name: str):
        self.user_id = user_id
        self.name = name
        self.role = None
        self.alive = True


class MafiaGame:
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.players: Dict[int, Player] = {}
        self.phase = "registration"
        self.day = 0
        self.night_target = None
        self.save_target = None
        self.check_target = None
        self.check_result = None
        self.votes: Dict[int, int] = {}
        self.mafia_ready = False
        self.doctor_ready = False
        self.sheriff_ready = False

    @property
    def alive_players(self):
        return [p for p in self.players.values() if p.alive]

    @property
    def mafia_players(self):
        return [p for p in self.players.values() if p.role == "Mafia" and p.alive]

    def get_player(self, user_id: int) -> Optional[Player]:
        return self.players.get(user_id)

    def alive_count(self):
        return len(self.alive_players)

    def mafia_alive_count(self):
        return len(self.mafia_players)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Mafia botga xush kelibsiz.\nGuruhga qo'shib, /mafia yozing.")


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
        "Chiqish uchun /leave"
    )


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

    players = list(game.players.keys())
    random.shuffle(players)
    n = len(players)

    mafia_count = max(1, n // 4)
    roles = ["Mafia"] * mafia_count
    if n >= 4 and "Doctor" not in roles:
        roles.append("Doctor")
    if n >= 5:
        roles.append("Sheriff")
    while len(roles) < n:
        roles.append("Tinch aholi")
    random.shuffle(roles)

    for uid, role in zip(players, roles):
        game.players[uid].role = role
        game.players[uid].alive = True

    role_names = {"Mafia": "\U0001f47e Mafia", "Doctor": "\U0001fa7a Doctor", "Sheriff": "\U0001f50d Sheriff", "Tinch aholi": "\U0001f9cd Tinch aholi"}
    mafia_list = [p.name for p in game.mafia_players]

    for uid, p in game.players.items():
        try:
            text = f"Sizning rolingiz: **{role_names[p.role]}**\n\n"
            if p.role == "Mafia":
                text += f"Mafia jamoadoshlaringiz: {', '.join(mafia_list)}\n\nKechasi /kill @user orqali odam o'ldirasiz."
            elif p.role == "Doctor":
                text += "Kechasi /save @user orqali odam qutqarasiz."
            elif p.role == "Sheriff":
                text += "Kechasi /check @user orqali odamni tekshirasiz (Mafia yoki yo'q)."
            else:
                text += "Siz oddiy fuqarosiz. Kunduzi ovoz berib mafiani toping!"
            await context.bot.send_message(chat_id=uid, text=text)
        except Exception as e:
            logging.warning(f"Could not send to {uid}: {e}")

    mafia_names = ", ".join(mafia_list)
    await update.message.reply_text(
        f"\U0001f3ad **O'yin boshlandi!**\n\n"
        f"Jami: {n} o'yinchi\n"
        f"Mafia a'zolari: {mafia_names}\n\n"
        f"\U0001f303 **1-tun** – Mafia uxlang, Doctor va Sheriff uyg'oq!"
    )
    game.phase = "night"
    game.day = 1
    game.mafia_ready = False
    game.doctor_ready = False
    game.sheriff_ready = False
    game.night_target = None
    game.save_target = None
    game.check_target = None
    await context.bot.send_message(chat.id, "\U0001f319 Tun boshlandi! Mafia, Doctor va Sheriff o'z harakatlarini qilsin.")


async def kill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "night":
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or p.role != "Mafia" or not p.alive:
        return
    if not context.args:
        await update.message.reply_text("Kimni o'ldirish kerak? Masalan: /kill @username")
        return
    target_text = context.args[0].lstrip("@")
    target = None
    for pl in game.alive_players:
        if pl.name.lower() == target_text.lower() or str(pl.user_id) == target_text:
            target = pl
            break
        if update.effective_message.entities:
            for ent in update.effective_message.entities:
                if ent.type == "mention" and ent.user:
                    if ent.user.id == pl.user_id:
                        target = pl
                        break
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    if target.user_id == user.id:
        await update.message.reply_text("O'zingizni o'ldira olmaysiz!")
        return
    game.night_target = target.user_id
    game.mafia_ready = True
    await update.message.reply_text(f"\u2714\ufe0f {target.name} ga ovoz berildi.")
    await check_night_ready(game, context)


async def save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "night":
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or p.role != "Doctor" or not p.alive:
        return
    if not context.args:
        await update.message.reply_text("Kimni qutqarish kerak? Masalan: /save @username")
        return
    target_text = context.args[0].lstrip("@")
    target = None
    for pl in game.alive_players:
        if pl.name.lower() == target_text.lower() or str(pl.user_id) == target_text:
            target = pl
            break
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    game.save_target = target.user_id
    game.doctor_ready = True
    await update.message.reply_text(f"\u2714\ufe0f {target.name} qutqariladi.")
    await check_night_ready(game, context)


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        return
    game = games[chat.id]
    if game.phase != "night":
        return
    user = update.effective_user
    p = game.get_player(user.id)
    if not p or p.role != "Sheriff" or not p.alive:
        return
    if not context.args:
        await update.message.reply_text("Kimni tekshirish kerak? Masalan: /check @username")
        return
    target_text = context.args[0].lstrip("@")
    target = None
    for pl in game.alive_players:
        if pl.name.lower() == target_text.lower() or str(pl.user_id) == target_text:
            target = pl
            break
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    if target.user_id == user.id:
        await update.message.reply_text("O'zingizni tekshira olmaysiz!")
        return
    game.check_target = target.user_id
    game.check_result = (target.role == "Mafia")
    game.sheriff_ready = True
    result_text = "\U0001f7e5 Mafia" if game.check_result else "\U0001f7e9 Mafia emas"
    await update.message.reply_text(f"\u2714\ufe0f {target.name}: {result_text}")
    await check_night_ready(game, context)


async def check_night_ready(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    has_mafia = len(game.mafia_players) > 0
    has_doctor = any(p.role == "Doctor" and p.alive for p in game.players.values())
    has_sheriff = any(p.role == "Sheriff" and p.alive for p in game.players.values())

    mafia_ok = not has_mafia or game.mafia_ready
    doctor_ok = not has_doctor or game.doctor_ready
    sheriff_ok = not has_sheriff or game.sheriff_ready

    if mafia_ok and doctor_ok and sheriff_ok:
        await resolve_night(game, context)


async def resolve_night(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    killed = None
    saved = None
    msg = f"\U0001f306 **{game.day}-kun**\n\n"

    if game.night_target:
        killed = game.players.get(game.night_target)
    if game.save_target:
        saved = game.players.get(game.save_target)

    if killed and saved and killed.user_id == saved.user_id:
        msg += f"Doctor {killed.name} ni qutqardi! Hech kim o'lmadi.\n"
    elif killed:
        killed.alive = False
        msg += f"\U0001f480 {killed.name} o'ldirildi! (Role: {killed.role})\n"
    else:
        msg += "Bu tun tinch o'tdi, hech kim o'lmadi.\n"

    if game.check_result is not None and game.check_target:
        checked = game.players.get(game.check_target)
        if checked:
            msg += f"Sheriff tekshiruvi: {checked.name} - {'\U0001f7e5 Mafia' if game.check_result else '\U0001f7e9 Mafia emas'}\n"

    if check_winner(game):
        msg += "\n\U0001f3c6 **O'yin tugadi!** " + check_winner(game)
        game.phase = "ended"
        await context.bot.send_message(game.chat_id, msg)
        del games[game.chat_id]
        return

    alive_list = "\n".join([f"{i+1}. {p.name} ({p.role})" for i, p in enumerate(game.alive_players)])
    msg += f"\n**Tirik o'yinchilar ({game.alive_count()}):**\n{alive_list}"
    msg += "\n\n\U0001f5f3 Ovoz berish vaqti! /vote @user orqali ovoz bering."

    game.phase = "vote"
    game.votes = {}
    await context.bot.send_message(game.chat_id, msg)


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
        await update.message.reply_text("Kimga ovoz berish kerak? Masalan: /vote @username")
        return
    target_text = context.args[0].lstrip("@")
    target = None
    for pl in game.alive_players:
        if pl.name.lower() == target_text.lower() or str(pl.user_id) == target_text:
            target = pl
            break
    if not target:
        await update.message.reply_text("Bunday o'yinchi topilmadi.")
        return
    if target.user_id == user.id:
        await update.message.reply_text("O'zingizga ovoz bera olmaysiz!")
        return
    game.votes[user.id] = target.user_id
    voted = len(game.votes)
    total = game.alive_count()
    await update.message.reply_text(f"\u2714\ufe0f {target.name} ga ovoz berdingiz. ({voted}/{total})")

    if voted >= total:
        await resolve_vote(game, context)


async def resolve_vote(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    vote_count = {}
    for uid, target_id in game.votes.items():
        vote_count[target_id] = vote_count.get(target_id, 0) + 1

    if not vote_count:
        await context.bot.send_message(game.chat_id, "Hech kim ovoz bermadi.")
        await start_night(game, context)
        return

    max_votes = max(vote_count.values())
    max_voted = [uid for uid, cnt in vote_count.items() if cnt == max_votes]

    msg = f"\U0001f5f3 **Ovoz natijalari:**\n"
    for uid, cnt in sorted(vote_count.items(), key=lambda x: -x[1]):
        pl = game.players.get(uid)
        if pl:
            msg += f"{pl.name}: {cnt} ovoz\n"

    if len(max_voted) == 1:
        eliminated = game.players.get(max_voted[0])
        if eliminated:
            eliminated.alive = False
            msg += f"\n\U0001f480 {eliminated.name} haydaldi! (Role: {eliminated.role})"
    else:
        msg += "\nOvozlar teng, hech kim haydalmadi."

    winner = check_winner(game)
    if winner:
        msg += f"\n\n\U0001f3c6 **O'yin tugadi!** {winner}"
        await context.bot.send_message(game.chat_id, msg)
        game.phase = "ended"
        if game.chat_id in games:
            del games[game.chat_id]
        return

    alive_list = "\n".join([f"{i+1}. {p.name} ({p.role})" for i, p in enumerate(game.alive_players)])
    msg += f"\n\n**Tirik o'yinchilar ({game.alive_count()}):**\n{alive_list}"
    await context.bot.send_message(game.chat_id, msg)
    await start_night(game, context)


async def start_night(game: MafiaGame, context: ContextTypes.DEFAULT_TYPE):
    game.day += 1
    game.phase = "night"
    game.night_target = None
    game.save_target = None
    game.check_target = None
    game.mafia_ready = False
    game.doctor_ready = False
    game.sheriff_ready = False
    game.votes = {}
    await context.bot.send_message(
        game.chat_id,
        f"\U0001f319 **{game.day}-tun** – Mafia uxlasin! \n"
        f"Tirik: {game.alive_count()} / {len(game.players)}"
    )

    for p in game.alive_players:
        try:
            if p.role == "Mafia":
                await context.bot.send_message(
                    p.user_id,
                    "/kill @user orqali odam o'ldiring"
                )
            elif p.role == "Doctor":
                await context.bot.send_message(
                    p.user_id,
                    "/save @user orqali odam qutqaring"
                )
            elif p.role == "Sheriff":
                await context.bot.send_message(
                    p.user_id,
                    "/check @user orqali odamni tekshiring"
                )
        except Exception as e:
            logging.warning(f"Night msg error for {p.user_id}: {e}")


def check_winner(game: MafiaGame):
    alive = game.alive_players
    mafia_alive = [p for p in alive if p.role == "Mafia"]
    village_alive = [p for p in alive if p.role != "Mafia"]

    if not mafia_alive:
        return "\U0001f389 **Tinch aholi yutdi!**"
    if len(mafia_alive) >= len(village_alive):
        return "\U0001f47e **Mafia yutdi!**"
    return None


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in games:
        await update.message.reply_text("O'yin mavjud emas.")
        return
    game = games[chat.id]
    alive_list = "\n".join([f"{'🟢' if p.alive else '💀'} {p.name} ({p.role})" for p in game.players.values()])
    await update.message.reply_text(
        f"**O'yin holati**\n"
        f"Faza: {game.phase}\n"
        f"Kun: {game.day}\n"
        f"O'yinchilar: {len(game.players)} (tirik: {game.alive_count()})\n\n"
        f"{alive_list}"
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
    app.add_handler(CommandHandler("vote", vote))
    app.add_handler(CommandHandler("status", status))
    logging.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
