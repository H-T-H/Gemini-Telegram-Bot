from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
import traceback
import google.generativeai as genai

from config import conf
import gemini

error_info              =       conf["error_info"]
before_generate_info    =       conf["before_generate_info"]
download_pic_notify     =       conf["download_pic_notify"]
model_1                 =       conf["model_1"]
model_2                 =       conf["model_2"]

gemini_player_dict = gemini.gemini_player_dict
gemini_pro_player_dict = gemini.gemini_pro_player_dict
default_model_dict = gemini.default_model_dict

async def start(message: Message, bot: TeleBot) -> None:
    try:
        await bot.reply_to(message , escape("Welcome, you can ask me questions now. \nFor example: `Who is john lennon?`"), parse_mode="MarkdownV2")
    except IndexError:
        await bot.reply_to(message, error_info)

async def gemini_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to( message , escape("Please add what you want to say after /gemini. \nFor example: `/gemini Who is john lennon?`"), parse_mode="MarkdownV2")
        return
    await gemini.gemini(bot,message,m,model_1)

async def gemini_pro_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to( message , escape("Please add what you want to say after /gemini_pro. \nFor example: `/gemini_pro Who is john lennon?`"), parse_mode="MarkdownV2")
        return
    await gemini.gemini(bot,message,m,model_2)

    async def gemini_stream_handler(message: Message, bot: TeleBot) -> None:
        try:
            m = message.text.strip().split(maxsplit=1)[1].strip()
        except IndexError:
            await bot.reply_to(message, escape("Please add what you want to say after /gemini_stream. \nFor example: `/gemini_stream Who is john lennon?`"), parse_mode="MarkdownV2")
            return
    await gemini.gemini_stream(bot, message, m, model_1)

async def gemini_pro_stream_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Please add what you want to say after /gemini_pro_stream. \nFor example: `/gemini_pro_stream Who is john lennon?`"), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, m, model_2)

async def clear(message: Message, bot: TeleBot) -> None:
    # Check if the player is already in gemini_player_dict.
    if (str(message.from_user.id) in gemini_player_dict):
        del gemini_player_dict[str(message.from_user.id)]
    if (str(message.from_user.id) in gemini_pro_player_dict):
        del gemini_pro_player_dict[str(message.from_user.id)]
    await bot.reply_to(message, "Your history has been cleared")

async def switch(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        await bot.reply_to( message , "This command is only for private chat !")
        return
    # Check if the player is already in default_model_dict.
    if str(message.from_user.id) not in default_model_dict:
        default_model_dict[str(message.from_user.id)] = False
        await bot.reply_to( message , "Now you are using "+model_2)
        return
    if default_model_dict[str(message.from_user.id)] == True:
        default_model_dict[str(message.from_user.id)] = False
        await bot.reply_to( message , "Now you are using "+model_2)
    else:
        default_model_dict[str(message.from_user.id)] = True
        await bot.reply_to( message , "Now you are using "+model_1)

async def gemini_private_handler(message: Message, bot: TeleBot) -> None:
    m = message.text.strip()
    if str(message.from_user.id) not in default_model_dict:
        default_model_dict[str(message.from_user.id)] = True
        await gemini.gemini_stream(bot, message, m, model_1)
    else:
        if default_model_dict[str(message.from_user.id)]:
            await gemini.gemini_stream(bot, message, m, model_1)
        else:
            await gemini.gemini_stream(bot, message, m, model_2)

async def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        s = message.caption
        if not s or not (s.startswith("/gemini")):
            return
        try:
            prompt = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
            file_path = await bot.get_file(message.photo[-1].file_id)
            sent_message = await bot.reply_to(message, download_pic_notify)
            downloaded_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, error_info)
        model = genai.GenerativeModel(model_1)
        contents = {
            "parts": [{"mime_type": "image/jpeg", "data": downloaded_file}, {"text": prompt}]
        }
        try:
            await bot.edit_message_text(before_generate_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            response = await gemini.async_generate_content(model, contents)
            await bot.edit_message_text(response.text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        except Exception:
            traceback.print_exc()
            await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
    else:
        s = message.caption if message.caption else ""
        try:
            prompt = s.strip()
            file_path = await bot.get_file(message.photo[-1].file_id)
            sent_message = await bot.reply_to(message, download_pic_notify)
            downloaded_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, error_info)
        model = genai.GenerativeModel(model_1)
        contents = {
            "parts": [{"mime_type": "image/jpeg", "data": downloaded_file}, {"text": prompt}]
        }
        try:
            await bot.edit_message_text(before_generate_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            response = await gemini.async_generate_content(model, contents)
            await bot.edit_message_text(response.text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        except Exception:
            traceback.print_exc()
            await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
