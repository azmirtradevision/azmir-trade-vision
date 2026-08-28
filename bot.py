import os
import asyncio
import logging
import threading

from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# =========================
# Configuration
# =========================

TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

if not RENDER_EXTERNAL_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not configured")


# =========================
# Logging
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# =========================
# Flask
# =========================

app = Flask(__name__)


# =========================
# Telegram Bot
# =========================

telegram_app = Application.builder().token(TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "🚀 Azmir Trade Vision চালু হয়েছে!\n\n"
            "📊 মার্কেটের screenshot পাঠাও।\n"
            "আমি technical analysis করার জন্য প্রস্তুত।"
        )


telegram_app.add_handler(CommandHandler("start", start))


# =========================
# Dedicated Telegram Event Loop
# =========================

telegram_loop = asyncio.new_event_loop()


def run_telegram_loop():
    asyncio.set_event_loop(telegram_loop)

    async def startup():
        await telegram_app.initialize()
        await telegram_app.start()

        webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook"

        await telegram_app.bot.set_webhook(
            url=webhook_url
        )

        logger.info("Telegram webhook set: %s", webhook_url)

    telegram_loop.run_until_complete(startup())

    logger.info("Telegram event loop started")

    telegram_loop.run_forever()


telegram_thread = threading.Thread(
    target=run_telegram_loop,
    daemon=True
)

telegram_thread.start()


# =========================
# Health Check
# =========================

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "Azmir Trade Vision is running! 🚀", 200


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


# =========================
# Telegram Webhook
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)

        update = Update.de_json(
            data,
            telegram_app.bot
        )

        future = asyncio.run_coroutine_threadsafe(
            telegram_app.process_update(update),
            telegram_loop
        )

        future.result(timeout=30)

        return "OK", 200

    except Exception as exc:
        logger.exception("Webhook error: %s", exc)
        return "ERROR", 500


# =========================
# Local Run
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT
    )
