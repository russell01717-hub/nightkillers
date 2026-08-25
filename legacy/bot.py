import sys
sys.path.insert(0, r"D:\pylibs")

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8388604050:AAFLH3sa6kIbg3YuuiLGMp1VBJT0JT2X9vg"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Salom")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()


if __name__ == "__main__":
    main()
