response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
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
