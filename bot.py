import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Azmir Trade Vision চালু হয়েছে!\n\n"
        "📊 মার্কেটের screenshot পাঠাও।\n"
        "আমি সেটার ভিত্তিতে technical analysis করার জন্য প্রস্তুত।"
    )

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("Azmir Trade Vision is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
