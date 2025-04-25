from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
import traceback
from config import conf, messages
import gemini

model_1 = conf["model_1"]
model_2 = conf["model_2"]

gemini_chat_dict = gemini.gemini_chat_dict
gemini_pro_chat_dict = gemini.gemini_pro_chat_dict
default_model_dict = gemini.default_model_dict
gemini_draw_dict = gemini.gemini_draw_dict
language_dict = gemini.language_dict

async def start(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    try:
        await bot.reply_to(message, escape(gemini.get_message("welcome_message", user_id)), parse_mode="MarkdownV2")
    except IndexError:
        await bot.reply_to(message, gemini.get_message("error_info", user_id))

async def gemini_stream_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape(gemini.get_message("gemini_usage_tip", user_id)), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, m, model_1)

async def gemini_pro_stream_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape(gemini.get_message("gemini_pro_usage_tip", user_id)), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, m, model_2)

async def clear(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    # Check if the chat is already in gemini_chat_dict.
    if (str(user_id) in gemini_chat_dict):
        del gemini_chat_dict[str(user_id)]
    if (str(user_id) in gemini_pro_chat_dict):
        del gemini_pro_chat_dict[str(user_id)]
    if (str(user_id) in gemini_draw_dict):
        del gemini_draw_dict[str(user_id)]
    await bot.reply_to(message, gemini.get_message("history_cleared", user_id))

async def switch(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    if message.chat.type != "private":
        await bot.reply_to(message, gemini.get_message("private_chat_only", user_id))
        return
    # Check if the chat is already in default_model_dict.
    if str(user_id) not in default_model_dict:
        default_model_dict[str(user_id)] = False
        await bot.reply_to(message, gemini.get_message("using_model", user_id) + model_2)
        return
    if default_model_dict[str(user_id)] == True:
        default_model_dict[str(user_id)] = False
        await bot.reply_to(message, gemini.get_message("using_model", user_id) + model_2)
    else:
        default_model_dict[str(user_id)] = True
        await bot.reply_to(message, gemini.get_message("using_model", user_id) + model_1)

async def language_switch(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    user_id_str = str(user_id)
    
    # 切换语言
    current_lang = gemini.get_user_language(user_id)
    new_lang = "en" if current_lang == "zh" else "zh"
    language_dict[user_id_str] = new_lang
    
    # 发送语言已切换的消息
    await bot.reply_to(message, gemini.get_message("language_switched", user_id))
    
    # 发送语言使用提示
    await bot.reply_to(message, gemini.get_message("language_usage_tip", user_id))

async def gemini_private_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    m = message.text.strip()
    if str(user_id) not in default_model_dict:
        default_model_dict[str(user_id)] = True
        await gemini.gemini_stream(bot, message, m, model_1)
    else:
        if default_model_dict[str(user_id)]:
            await gemini.gemini_stream(bot, message, m, model_1)
        else:
            await gemini.gemini_stream(bot, message, m, model_2)

async def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    if message.chat.type != "private":
        s = message.caption or ""
        if not s or not (s.startswith("/gemini")):
            return
        try:
            m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, gemini.get_message("error_info", user_id))
            return
        await gemini.gemini_edit(bot, message, m, photo_file)
    else:
        s = message.caption or ""
        try:
            m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, gemini.get_message("error_info", user_id))
            return
        await gemini.gemini_edit(bot, message, m, photo_file)

async def gemini_edit_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    if not message.photo:
        await bot.reply_to(message, gemini.get_message("send_photo_request", user_id))
        return
    s = message.caption or ""
    try:
        m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
        file_path = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file_path.file_path)
    except Exception as e:
        traceback.print_exc()
        await bot.reply_to(message, e.str())
        return
    await gemini.gemini_edit(bot, message, m, photo_file)

async def draw_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape(gemini.get_message("draw_usage_tip", user_id)), parse_mode="MarkdownV2")
        return
    
    # reply to the message first, then delete the "drawing..." message
    drawing_msg = await bot.reply_to(message, gemini.get_message("drawing", user_id))
    try:
        await gemini.gemini_draw(bot, message, m)
    finally:
        await bot.delete_message(chat_id=message.chat.id, message_id=drawing_msg.message_id)
