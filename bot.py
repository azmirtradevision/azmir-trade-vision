import os
import logging
import time
import threading
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

GEMINI_MODEL = "gemini-3.6-flash"
MAX_RETRIES = 3
RETRY_DELAYS = [3, 6, 9]

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
# DUPLICATE UPDATE PROTECTION
# ==========================================

processed_updates = set()
processed_updates_lock = threading.Lock()

MAX_STORED_UPDATES = 1000


def is_duplicate_update(update_id):

    if update_id is None:
        return False

    with processed_updates_lock:

        if update_id in processed_updates:
            return True

        processed_updates.add(update_id)

        # Prevent unlimited memory growth
        if len(processed_updates) > MAX_STORED_UPDATES:

            processed_updates.clear()

            processed_updates.add(update_id)

        return False


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
# GEMINI TECHNICAL ANALYSIS V2 + RETRY
# ==========================================

def analyze_chart(image_bytes):

    logger.info(
        "Starting Gemini V2 image analysis..."
    )

    prompt = """
You are Azmir Trade Vision V2.

Your task is to analyze a trading-chart screenshot
for DEMO research only.

The intended observation horizon is approximately
10 seconds.

IMPORTANT:

You cannot know the future price.
Never claim guaranteed accuracy.
Never claim a 95% win rate from one screenshot.
Do not invent information that is not visible.

Your primary objective is QUALITY OVER QUANTITY.

Analyze these factors:

1. MARKET STRUCTURE
- Higher highs / higher lows
- Lower highs / lower lows
- Range / sideways structure

2. TREND
- Bullish
- Bearish
- Neutral

3. MOMENTUM
- Strong
- Moderate
- Weak
- Conflicting

4. CANDLE STRUCTURE
Look at the latest visible candles.

Check:
- body size
- wick rejection
- consecutive candles
- engulfing behavior if clearly visible
- exhaustion
- consolidation

5. SUPPORT AND RESISTANCE

Only mention levels that are actually visible.
Never invent price levels.

6. BREAKOUT / REJECTION

Check whether price is:
- breaking a visible level
- rejecting a level
- consolidating
- too close to resistance/support

7. SIGNAL QUALITY

Use a strict confirmation system.

Consider these seven confirmations:

A. Trend alignment
B. Market structure
C. Momentum
D. Candle confirmation
E. Support/resistance position
F. Breakout/rejection confirmation
G. Absence of major contradiction

A setup should normally have at least
6 strong confirmations before producing
CALL or PUT.

If important factors conflict,
return NO SIGNAL.

If the screenshot is unclear,
return NO SIGNAL.

If price is already highly extended near
a major visible resistance/support level,
prefer NO SIGNAL unless there is a
very clear breakout confirmation.

Do not force a signal.

OUTPUT EXACTLY:

📊 AZMIR TRADE VISION V2

Trend: ...
Market Structure: ...
Momentum: ...
Candle Structure: ...
Support: ...
Resistance: ...

🔎 CONFIRMATIONS

Trend Alignment: STRONG / WEAK / NONE
Structure: STRONG / WEAK / NONE
Momentum: STRONG / WEAK / NONE
Candle Confirmation: STRONG / WEAK / NONE
Level Position: STRONG / WEAK / NONE
Breakout/Rejection: STRONG / WEAK / NONE
Contradiction Check: CLEAR / CONFLICT

🎯 SIGNAL

CALL / PUT / NO SIGNAL

📈 SETUP QUALITY

HIGH / MEDIUM / LOW

📌 CONFIDENCE

Give a probability estimate based only
on visible evidence.

Do not automatically use 95%.

If evidence is weak,
use a lower number.

💡 REASON

Explain briefly why the signal or
NO SIGNAL was selected.

⏱️ DEMO HORIZON

Approximately 10 seconds

⚠️ RISK NOTE

This is experimental technical analysis
for demo testing.

Short-duration and OTC markets can be
highly unpredictable.

No signal is guaranteed.

FINAL RULE:

A false signal is worse than NO SIGNAL.

Therefore, when uncertain,
choose NO SIGNAL.
"""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            logger.info(
                "Gemini attempt %s of %s",
                attempt,
                MAX_RETRIES
            )

            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg"
                    ),
                    prompt
                ]
            )

            result = response.text

            if not result:

                raise RuntimeError(
                    "Gemini returned an empty response"
                )

            logger.info(
                "Gemini response received successfully"
            )

            return result

        except Exception as exc:

            last_error = exc
            error_text = str(exc)

            logger.exception(
                "Gemini attempt %s failed: %s",
                attempt,
                exc
            )

            is_unavailable = (
                "503" in error_text
                or "UNAVAILABLE" in error_text.upper()
                or "high demand" in error_text.lower()
            )

            if attempt < MAX_RETRIES and is_unavailable:

                delay = RETRY_DELAYS[
                    attempt - 1
                ]

                logger.warning(
                    "Gemini temporarily unavailable. "
                    "Retrying in %s seconds...",
                    delay
                )

                time.sleep(delay)

                continue

            break

    raise RuntimeError(
        f"Gemini analysis failed after "
        f"{MAX_RETRIES} attempts: {last_error}"
    )


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/", methods=["GET", "HEAD"])
def home():

    return (
        "Azmir Trade Vision V2 is running! 🚀",
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

        # ==================================
        # DUPLICATE UPDATE CHECK
        # ==================================

        update_id = data.get("update_id")

        if is_duplicate_update(update_id):

            logger.info(
                "Duplicate update ignored: %s",
                update_id
            )

            return "OK", 200

        logger.info(
            "Telegram update received: %s",
            update_id
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
                "🚀 Azmir Trade Vision V2 চালু হয়েছে!\n\n"
                "📊 10-second demo analysis-এর জন্য "
                "একটি পরিষ্কার market screenshot পাঠাও।\n\n"
                "🧠 Strong confirmation না থাকলে "
                "আমি NO SIGNAL দেব।"
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

            # Send confirmation only once
            send_message(
                chat_id,
                "📸 Screenshot পেয়েছি! ✅\n\n"
                "🧠 V2 technical analysis শুরু করছি...\n"
                "🔄 প্রয়োজনে AI automatically retry করবে।\n"
                "⏱️ Target horizon: 10 seconds"
            )

            logger.info(
                "Getting Telegram file..."
            )

            file_path = get_file_path(
                file_id
            )

            logger.info(
                "Telegram file path received"
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
                "Gemini V2 analysis completed"
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
            "📸 একটি পরিষ্কার market screenshot পাঠাও।"
        )

        return "OK", 200


    except Exception as exc:

        logger.exception(
            "WEBHOOK ERROR: %s",
            exc
        )

        if chat_id:

            try:

                error_text = str(exc)

                if (
                    "503" in error_text
                    or "UNAVAILABLE" in error_text.upper()
                ):

                    message_text = (
                        "⚠️ Gemini AI এই মুহূর্তে ব্যস্ত আছে।\n\n"
                        "🔄 আমি কয়েকবার automatically retry করেছি, "
                        "কিন্তু response পাইনি।\n\n"
                        "📸 একটু পরে আবার screenshot পাঠাও।"
                    )

                else:

                    message_text = (
                        "⚠️ Analysis করতে সমস্যা হয়েছে।\n\n"
                        f"Error: {error_text[:700]}"
                    )

                send_message(
                    chat_id,
                    message_text
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
