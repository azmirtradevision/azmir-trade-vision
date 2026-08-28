import os
import logging

from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# =========================
# Configuration
# =========================

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

# Render-এর URL Environment Variable হিসেবে রাখব
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

# =========================
# Logging
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# =========================
# Telegram Application
# =========================

telegram_app = Application.builder().token(TOKEN).build()


# =========================
# Telegram Commands
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Azmir Trade Vision চালু হয়েছে!\n\n"
        "📊 মার্কেটের screenshot পাঠাও।\n"
        "আমি technical analysis করার জন্য প্রস্তুত।"
    )


telegram_app.add_handler(CommandHandler("start", start))


# =========================
# Flask App
# =========================

app = Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    return "Azmir Trade Vision is running! 🚀", 200


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


@app.route("/webhook", methods=["POST"])
async def webhook():
    try:
        data = request.get_json(force=True)

        update = Update.de_json(
            data,
            telegram_app.bot
        )

        await telegram_app.process_update(update)

        return "OK", 200

    except Exception as e:
        logger.exception("Webhook error: %s", e)
        return "ERROR", 500


# =========================
# Initialize Telegram
# =========================

async def initialize_bot():
    await telegram_app.initialize()

    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"

        await telegram_app.bot.set_webhook(
            url=webhook_url
        )

        logger.info(
            "Telegram webhook set: %s",
            webhook_url
        )
    else:
        logger.warning(
            "RENDER_EXTERNAL_URL is not configured."
        )


# =========================
# Startup
# =========================

@app.before_request
async def startup():
    if not getattr(app, "_bot_initialized", False):
        await initialize_bot()
        app._bot_initialized = True


# =========================
# Local Run
# =========================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=PORT
    )
