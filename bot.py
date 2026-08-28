import os
import logging
import base64
import requests

from flask import Flask, request
from openai import OpenAI


# ==========================================
# CONFIGURATION
# ==========================================

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not configured")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not configured")


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

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
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

    return response.json()


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
# OPENAI VISION
# ==========================================

def analyze_chart(image_bytes):

    logger.info(
        "Starting OpenAI image analysis..."
    )

    image_base64 = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    image_data_url = (
        f"data:image/jpeg;base64,{image_base64}"
    )

    prompt = """
You are Azmir Trade Vision.

Analyze the trading chart screenshot carefully.

Only use information that is actually visible.

Analyze:

1. Trend
2. Recent candle structure
3. Momentum
4. Support
5. Resistance
6. Possible continuation
7. Possible reversal
8. Overall setup quality

Return this format:

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

Important rules:

- Never claim 100% accuracy.
- Never guarantee profit.
- Never invent price levels.
- If the screenshot is unclear, choose NO SIGNAL.
- If the setup is weak or conflicting, choose NO SIGNAL.
- This is technical analysis, not financial advice.
"""

    try:

        response = openai_client.responses.create(
            model="gpt-5.6-luna",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        },
                        {
                            "type": "input_image",
                            "image_url": image_data_url
                        }
                    ]
                }
            ]
        )

        logger.info(
            "OpenAI response received successfully"
        )

        result = response.output_text

        if not result:
            raise RuntimeError(
                "OpenAI returned an empty response"
            )

        return result

    except Exception as exc:

        logger.exception(
            "OPENAI ERROR: %s",
            exc
        )

        # গুরুত্বপূর্ণ:
        # আসল error Telegram-এ দেখাবে
        raise RuntimeError(
            f"OpenAI error: {exc}"
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

            # Confirmation
            send_message(
                chat_id,
                "📸 Screenshot পেয়েছি! ✅\n\n"
                "🧠 AI technical analysis শুরু করছি..."
            )

            # Get file
            logger.info(
                "Getting Telegram file..."
            )

            file_path = get_file_path(
                file_id
            )

            logger.info(
                "Telegram file path received"
            )

            # Download
            image_bytes = download_image(
                file_path
            )

            logger.info(
                "Image downloaded successfully: %s bytes",
                len(image_bytes)
            )

            # Analyze
            analysis = analyze_chart(
                image_bytes
            )

            logger.info(
                "AI analysis completed"
            )

            # Send result
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
                    "Could not send error to Telegram: %s",
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
