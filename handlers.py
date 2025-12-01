from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
import traceback
from config import conf
from database import db
import gemini


def extract_command_argument(message: Message) -> str:
    """Return the text following the command in a message or caption."""
    text = (message.text or message.caption or "").strip()
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""

error_info              =       conf["error_info"]
before_generate_info    =       conf["before_generate_info"]
download_pic_notify     =       conf["download_pic_notify"]
model_1                 =       conf["model_1"]
model_2                 =       conf["model_2"]

gemini_chat_dict        = gemini.gemini_chat_dict
gemini_pro_chat_dict    = gemini.gemini_pro_chat_dict
default_model_dict      = gemini.default_model_dict
gemini_draw_dict        = gemini.gemini_draw_dict

async def start(message: Message, bot: TeleBot) -> None:
    try:
        await bot.reply_to(
            message,
            escape("Добро пожаловать, теперь вы можете задавать вопросы.\nНапример: `Кто такой Джон Леннон?`"),
            parse_mode="MarkdownV2",
        )
    except IndexError:
        await bot.reply_to(message, error_info)

async def gemini_stream_handler(message: Message, bot: TeleBot) -> None:
    m = extract_command_argument(message)
    if not m:
        await bot.reply_to(
            message,
            escape("Пожалуйста, добавьте текст после /gemini.\nНапример: `/gemini Кто такой Джон Леннон?`"),
            parse_mode="MarkdownV2",
        )
        return
    await gemini.gemini_stream(bot, message, m, model_1)

async def gemini_pro_stream_handler(message: Message, bot: TeleBot) -> None:
    m = extract_command_argument(message)
    if not m:
        await bot.reply_to(
            message,
            escape("Пожалуйста, добавьте текст после /gemini_pro.\nНапример: `/gemini_pro Кто такой Джон Леннон?`"),
            parse_mode="MarkdownV2",
        )
        return
    await gemini.gemini_stream(bot, message, m, model_2)

async def clear(message: Message, bot: TeleBot) -> None:
    # Check if the chat is already in gemini_chat_dict.
    if (str(message.from_user.id) in gemini_chat_dict):
        del gemini_chat_dict[str(message.from_user.id)]
    if (str(message.from_user.id) in gemini_pro_chat_dict):
        del gemini_pro_chat_dict[str(message.from_user.id)]
    if (str(message.from_user.id) in gemini_draw_dict):
        del gemini_draw_dict[str(message.from_user.id)]

    # Also clear from DB
    db.clear_history(message.from_user.id)

    await bot.reply_to(message, "История очищена")

async def switch(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        await bot.reply_to(message, "Эта команда доступна только в личном чате!")
        return

    user_id = str(message.from_user.id)
    current_model = db.get_user_model(user_id)

    if current_model == model_2:
        new_model = model_1
        await bot.reply_to(message, "Теперь вы используете " + model_1)
    else:
        # Default is usually model_1 (Flash), so switch to model_2 (Pro)
        # But wait, original logic:
        # if not in dict -> set False (Pro) -> reply "Uses Pro"
        # if True (Flash) -> set False (Pro)
        # else -> set True (Flash)

        # Original: default_model_dict[id] = True means Flash.
        # If not in dict, set False (Pro).

        if current_model == model_1:
             new_model = model_2
             await bot.reply_to(message, "Теперь вы используете " + model_2)
        else:
             # If None (not set) or already model_2
             if current_model is None:
                 # Original logic: if not in dict, set False (Pro).
                 new_model = model_2
                 await bot.reply_to(message, "Теперь вы используете " + model_2)
             else:
                 new_model = model_1
                 await bot.reply_to(message, "Теперь вы используете " + model_1)

    db.set_user_model(user_id, new_model)
    # Also update in-memory for consistency if needed, but handlers read from DB now?
    # No, `gemini_private_handler` below reads from `default_model_dict`.
    # I should update `gemini_private_handler` to read from DB too.

async def gemini_private_handler(message: Message, bot: TeleBot) -> None:
    m = message.text.strip()
    user_id = str(message.from_user.id)

    current_model = db.get_user_model(user_id)

    # If not set, default to model_1 (Flash) as per typical expectation,
    # OR follow original logic: "If not in default_model_dict -> set True -> use model_1"
    # Wait, `switch` original: "if not in dict: dict=False (Pro)".
    # `gemini_private_handler` original: "if not in dict: dict=True (Flash)".
    # So by default private chat uses Flash. Switch toggles it.

    if current_model is None:
        current_model = model_1
        db.set_user_model(user_id, model_1)

    await gemini.gemini_stream(bot, message, m, current_model)

async def gemini_voice_handler(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        # Maybe allow in groups if replied to bot? For now private only or explicit command?
        # Standard behavior: handle if private.
        pass

    try:
        file_info = await bot.get_file(message.voice.file_id)
        file_data = await bot.download_file(file_info.file_path)

        # User model preference
        user_id = str(message.from_user.id)
        current_model = db.get_user_model(user_id) or model_1

        await gemini.gemini_voice(bot, message, file_data, current_model)

    except Exception as e:
        traceback.print_exc()
        await bot.reply_to(message, error_info)

async def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        s = message.caption or ""
        if not s or not (s.startswith("/gemini")):
            return
        m = extract_command_argument(message)
        try:
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, error_info)
            return
        await gemini.gemini_edit(bot, message, m, photo_file)
    else:
        m = extract_command_argument(message)
        try:
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, error_info)
            return
        await gemini.gemini_edit(bot, message, m, photo_file)

async def gemini_edit_handler(message: Message, bot: TeleBot) -> None:
    if not message.photo:
        await bot.reply_to(message, "Пожалуйста, отправьте фотографию")
        return
    m = extract_command_argument(message)
    try:
        file_path = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file_path.file_path)
    except Exception as e:
        traceback.print_exc()
        await bot.reply_to(message, str(e))
        return
    await gemini.gemini_edit(bot, message, m, photo_file)

async def draw_handler(message: Message, bot: TeleBot) -> None:
    m = extract_command_argument(message)
    if not m:
        await bot.reply_to(
            message,
            escape("Пожалуйста, добавьте, что нарисовать после /draw.\nНапример: `/draw нарисуй мне кота.`"),
            parse_mode="MarkdownV2",
        )
        return

    # reply to the message first, then delete the "drawing..." message
    drawing_msg = await bot.reply_to(message, "Рисую...")
    try:
        await gemini.gemini_draw(bot, message, m)
    finally:
        await bot.delete_message(chat_id=message.chat.id, message_id=drawing_msg.message_id)
