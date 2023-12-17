import argparse
import asyncio
import logging
from contextvars import ContextVar
from io import BytesIO

import google.generativeai as genai
import telegram
from google.generativeai.types import BrokenResponseError
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    filters,
)

generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

logger = logging.getLogger("gemini-bot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
]
placehold_message = ContextVar("placehold_message")


def make_new_gemini_convo():
    model = genai.GenerativeModel(
        model_name="gemini-pro",
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    convo = model.start_chat()
    return convo


async def post_init(application: Application):
    await application.bot.set_my_commands(
        [
            BotCommand("clear", "Clear conversation history"),
        ]
    )


async def is_bot_mentioned(update: Update, context: CallbackContext):
    try:
        message = update.message

        if message.chat.type == "private":
            return True

        if message.text is not None and ("@" + context.bot.username) in message.text:
            return True

        if message.reply_to_message is not None:
            if message.reply_to_message.from_user.id == context.bot.id:
                return True
    except:
        return True
    else:
        return False


async def edited_message_handle(update: Update, context: CallbackContext):
    if update.edited_message.chat.type == "private":
        text = "🥲 Unfortunately, message <b>editing</b> is not supported"
        await update.edited_message.reply_text(text, parse_mode=ParseMode.HTML)


async def get_placehold_message(update: Update, text="..."):
    if not placehold_message.get(None):
        placehold_message.set(await update.message.reply_text(text))
        await update.message.chat.send_action(action="typing")
    return placehold_message.get()


async def stream_msg(update: Update, context: CallbackContext, response):
    message = await get_placehold_message(update)
    try:
        answer = ""
        async for chunk in response:
            answer += chunk.text
            answer = answer[:4096]  # telegram message length limit
            try:
                await context.bot.edit_message_text(
                    answer,
                    chat_id=message.chat_id,
                    message_id=message.message_id,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except telegram.error.BadRequest as e:
                if not str(e).startswith("Message is not modified"):
                    await context.bot.edit_message_text(answer, chat_id=message.chat_id, message_id=message.message_id)
            await asyncio.sleep(0.1)  # wait a bit to avoid flooding
    except asyncio.CancelledError:
        raise

    except Exception as e:
        error_text = f"🥲 Something went wrong during completion. Reason: {e}"
        logger.error(error_text)
        await context.bot.edit_message_text(error_text, chat_id=message.chat_id, message_id=message.message_id)

    await asyncio.sleep(0.1)


async def message_handler(update: Update, context: CallbackContext, message=None):
    # check if bot was mentioned (for group chats)
    if not await is_bot_mentioned(update, context):
        return

    # check if message is edited
    if update.edited_message is not None:
        await edited_message_handle(update, context)
        return

    text = message or update.message.text

    # remove bot mention (in group chats)
    if update.message.chat.type != "private":
        text = text.replace("@" + context.bot.username, "").strip()

    if text is None or len(text) == 0:
        await update.message.reply_text(
            "🥲 You sent <b>empty message</b>. Please, try again!", parse_mode=ParseMode.HTML
        )
        return
    player = gemini_player_dict.setdefault(update.message.from_user.id, make_new_gemini_convo())
    try:
        response = await player.send_message_async(text, stream=True)
    except BrokenResponseError:
        player.rewind()
        placehold_message.set(await get_placehold_message(update, "🥲 Something went wrong, I'll try again..."))
        return await message_handler(update, context, message)
    await stream_msg(update, context, response)


async def photo_handler(update: Update, context: CallbackContext):
    placehold_message.set(await get_placehold_message(update, "🤖 Processing your photo..."))

    max_size_photo = max(update.message.photo, key=lambda p: p.file_size)
    try:
        file = await max_size_photo.get_file()
        with BytesIO() as bio:
            await file.download_to_memory(bio)
            img = bio.getvalue()
    except Exception as e:
        await update.message.reply_text(f"🥲 Something is wrong while reading your photo: {e}")
        return
    model = genai.GenerativeModel("gemini-pro-vision")
    contents = {
        "parts": [
            {
                "mime_type": "image/jpeg",
                "data": img,
            },
            {
                "text": update.message.caption or "Please describe this image",
            },
        ],
    }
    response = await model.generate_content_async(contents, stream=True)
    await stream_msg(update, context, response)


async def clear_handler(update: Update, context: CallbackContext):
    gemini_player_dict.pop(update.message.from_user.id, None)
    await update.message.reply_text("🤖 Conversation history cleared")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="telegram token")
    parser.add_argument("gemini_key", help="Google Gemini API key")
    options = parser.parse_args()
    genai.configure(api_key=options.gemini_key)

    app = (
        ApplicationBuilder()
        .token(options.tg_token)
        .concurrent_updates(True)
        .rate_limiter(AIORateLimiter(max_retries=5))
        .http_version("1.1")
        .get_updates_http_version("1.1")
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, photo_handler))
    app.run_polling()


if __name__ == "__main__":
    gemini_player_dict = {}
    main()
