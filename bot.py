import os
import logging
import base64
import requests

from flask import Flask, request
from google import genai
from google.genai import types


# ==========================================
# CONFIGURATION
# ==========================================

TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not configured")


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger("bot")


# ==========================================
# CLIENTS
# ==========================================

TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ==========================================
# FLASK
# ==========================================

app = Flask(__name__)


# ==========================================
# TELEGRAM SEND MESSAGE
# ==========================================

def send_message(chat_id, text):

    response = requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )

    response.raise_for_status()


# ==========================================
# TELEGRAM GET FILE
# ==========================================

def get_file_path(file_id):

    response = requests.get(
        f"{TELEGRAM_API}/getFile",
        params={
            "file_id": file_id
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(
            f"Telegram getFile failed: {data}"
        )

    return data["result"]["file_path"]


# ==========================================
# DOWNLOAD IMAGE
# ==========================================

def download_image(file_path):

    url = (
        f"https://api.telegram.org/file/"
        f"bot{TOKEN}/{file_path}"
    )

    response = requests.get(
        url,
        timeout=60
    )

    response.raise_for_status()

    return response.content


# ==========================================
# GEMINI VISION ANALYSIS
# ==========================================

def analyze_chart(image_bytes):

    logger.info(
        "Starting Gemini image analysis..."
    )

    prompt = """
You are Azmir Trade Vision, a cautious technical-analysis assistant.

Analyze the supplied trading-chart screenshot.

Only use information that is actually visible.

Analyze:

1. Market trend
2. Recent candle structure
3. Momentum
4. Support
5. Resistance
6. Possible continuation
7. Possible reversal
8. Overall setup quality

Return exactly this structure:

📊 MARKET ANALYSIS

Trend: ...
Momentum: ...
Candle Structure: ...
Support: ...
Resistance: ...

🎯 SIGNAL
CALL / PUT / NO SIGNAL

📌 CONFIDENCE
...%

💡 REASON
...

⚠️ RISK NOTE
...

Rules:

- Never claim 100% accuracy.
- Never guarantee profit.
- Never invent price levels.
- If the screenshot is unclear, choose NO SIGNAL.
- If the setup is weak or conflicting, choose NO SIGNAL.
- This is technical analysis, not financial advice.
"""

    try:

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg"
                ),
                prompt
            ]
        )

        logger.info(
            "Gemini response received"
        )

        result = response.text

        if not result:
            raise RuntimeError(
                "Gemini returned an empty response"
            )

        return result

    except Exception as exc:

        logger.exception(
            "GEMINI ERROR: %s",
            exc
        )

        raise RuntimeError(
            f"Gemini error: {exc}"
        ) from exc


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/", methods=["GET", "HEAD"])
def home():

    return (
        "Azmir Trade Vision is running! 🚀",
        200
    )


@app.route("/health", methods=["GET"])
def health():

    return "OK", 200


# ==========================================
# TELEGRAM WEBHOOK
# ==========================================

@app.route("/webhook", methods=["POST"])
def webhook():

    chat_id = None

    try:

        data = request.get_json(force=True)

        logger.info(
            "Telegram update received"
        )

        message = data.get("message")

        if not message:
            return "OK", 200

        chat = message.get("chat")

        if not chat:
            return "OK", 200

        chat_id = chat.get("id")

        # ==================================
        # START
        # ==================================

        text = message.get("text", "")

        if text.strip().lower() == "/start":

            send_message(
                chat_id,
                "🚀 Azmir Trade Vision চালু হয়েছে!\n\n"
                "📊 মার্কেটের screenshot পাঠাও।\n"
                "আমি technical analysis করার জন্য প্রস্তুত।"
            )

            logger.info(
                "Start message sent"
            )

            return "OK", 200

        # ==================================
        # PHOTO
        # ==================================

        photos = message.get("photo")

        if photos:

            logger.info(
                "Screenshot received"
            )

            photo = photos[-1]

            file_id = photo.get("file_id")

            send_message(
                chat_id,
                "📸 Screenshot পেয়েছি! ✅\n\n"
                "🧠 Gemini AI technical analysis শুরু করছি..."
            )

            logger.info(
                "Getting Telegram file..."
            )

            file_path = get_file_path(
                file_id
            )

            image_bytes = download_image(
                file_path
            )

            logger.info(
                "Image downloaded: %s bytes",
                len(image_bytes)
            )

            analysis = analyze_chart(
                image_bytes
            )

            logger.info(
                "Gemini analysis completed"
            )

            send_message(
                chat_id,
                analysis
            )

            return "OK", 200

        # ==================================
        # OTHER MESSAGE
        # ==================================

        send_message(
            chat_id,
            "📸 একটি market screenshot পাঠাও।"
        )

        return "OK", 200

    except Exception as exc:

        logger.exception(
            "WEBHOOK ERROR: %s",
            exc
        )

        if chat_id:

            try:

                send_message(
                    chat_id,
                    "⚠️ Analysis করতে সমস্যা হয়েছে।\n\n"
                    f"Error: {str(exc)[:700]}"
                )

            except Exception as telegram_error:

                logger.exception(
                    "Telegram error: %s",
                    telegram_error
                )

        return "ERROR", 500


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=PORT
    )
