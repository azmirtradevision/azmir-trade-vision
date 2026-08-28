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
# DOWNLOAD TELEGRAM IMAGE
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
# OPENAI VISION ANALYSIS
# ==========================================

def analyze_chart(image_bytes):

    image_base64 = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    image_data_url = (
        f"data:image/jpeg;base64,{image_base64}"
    )

    prompt = """
You are Azmir Trade Vision, a cautious technical-analysis assistant.

Analyze this trading-chart screenshot.

Look only at information that is actually visible in the image.

Analyze:

1. Market trend
2. Recent candle structure
3. Momentum
4. Support and resistance
5. Possible continuation
6. Possible reversal
7. Overall setup quality

Then provide the result in exactly this format:

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
- Never pretend to know information that is not visible.
- If the chart is unclear, choose NO SIGNAL.
- If the setup is weak or conflicting, choose NO SIGNAL.
- Do not invent price levels.
- Do not guarantee profit.
- The signal is an analytical opinion, not financial advice.
"""

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
                        "image_url": image_data_url,
                        "detail": "high"
                    }
                ]
            }
        ]
    )

    return response.output_text


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
        # /START
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

            # Largest available Telegram image
            photo = photos[-1]

            file_id = photo.get("file_id")

            logger.info(
                "Screenshot received"
            )

            # First confirmation
            send_message(
                chat_id,
                "📸 Screenshot পেয়েছি! ✅\n\n"
                "🧠 AI technical analysis শুরু করছি..."
            )

            # Get Telegram file path
            file_path = get_file_path(
                file_id
            )

            # Download image
            image_bytes = download_image(
                file_path
            )

            logger.info(
                "Image downloaded successfully"
            )

            # AI analysis
            analysis = analyze_chart(
                image_bytes
            )

            logger.info(
                "AI analysis completed"
            )

            # Send analysis
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
            "📸 অনুগ্রহ করে একটি market screenshot পাঠাও।"
        )

        return "OK", 200

    except Exception as exc:

        logger.exception(
            "Webhook error: %s",
            exc
        )

        try:

            if "chat_id" in locals():

                send_message(
                    chat_id,
                    "⚠️ Screenshot analysis করতে সমস্যা হয়েছে।\n\n"
                    "কিছুক্ষণ পরে আবার চেষ্টা করো।"
                )

        except Exception:

            pass

        return "ERROR", 500


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=PORT
)
