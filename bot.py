import os
import logging
import requests

from flask import Flask, request


# =========================
# Configuration
# =========================

TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")


# =========================
# Logging
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


# =========================
# Telegram API
# =========================

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    response = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# =========================
# Flask
# =========================

app = Flask(__name__)


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

        logger.info("Telegram update received")

        message = data.get("message")

        if not message:
            return "OK", 200

        chat = message.get("chat")

        if not chat:
            return "OK", 200

        chat_id = chat.get("id")

        # =========================
        # Text Message
        # =========================

        text = message.get("text", "")

        if text.strip().lower() == "/start":

            send_message(
                chat_id,
                "🚀 Azmir Trade Vision চালু হয়েছে!\n\n"
                "📊 মার্কেটের screenshot পাঠাও।\n"
                "আমি technical analysis করার জন্য প্রস্তুত।"
            )

            logger.info("Start message sent to chat %s", chat_id)

            return "OK", 200

        # =========================
        # Photo / Screenshot
        # =========================

        photos = message.get("photo")

        if photos:

            # Telegram সাধারণত একাধিক size-এর photo দেয়।
            # শেষেরটি সবচেয়ে বড় resolution-এর হয়।
            photo = photos[-1]

            file_id = photo.get("file_id")

            logger.info(
                "Screenshot received. File ID: %s",
                file_id
            )

            send_message(
                chat_id,
                "📸 Screenshot পেয়েছি! ✅\n\n"
                "🧠 এখন technical analysis-এর জন্য প্রস্তুত করছি..."
            )

            return "OK", 200

        # =========================
        # Other Messages
        # =========================

        send_message(
            chat_id,
            "📸 অনুগ্রহ করে মার্কেটের একটি screenshot পাঠাও।"
        )

        return "OK", 200

    except Exception as exc:

        logger.exception(
            "Webhook error: %s",
            exc
        )

        return "ERROR", 500


# =========================
# Run
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=PORT
    )
