import traceback
import io
from PIL import Image
import gemini as gemini
from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
from config import conf
from utils import get_model, update_chat, chat_dict

error_info              =       conf["error_info"]
before_generate_info    =       conf["before_generate_info"]
download_pic_notify     =       conf["download_pic_notify"]
model_1                 =       conf["model_1"]
model_2                 =       conf["model_2"]

async def start(message: Message, bot: TeleBot) -> None:
    try:
        await bot.reply_to(message , escape("Welcome, you can ask me questions now. \nFor example: `Who is john lennon?`"), parse_mode="MarkdownV2")
    except IndexError:
        await bot.reply_to(message, error_info)

async def gemini_handler(message: Message, bot: TeleBot) -> None:
    try:
        contents = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Please add what you want to say after /gemini. \nFor example: `/gemini Who is john lennon?`"), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, contents)

async def clear(message: Message, bot: TeleBot) -> None:
    # Check if the chat is already in chat_dict.
    if (message.from_user.id in chat_dict):
        del chat_dict[message.from_user.id]
    await bot.reply_to(message, "Your history has been cleared")

async def switch(message: Message, bot: TeleBot) -> None:
    model = await get_model(message.from_user.id)
    if model == model_1:
        await update_chat(message.from_user.id, model_2)
        await bot.reply_to(message , "Now you are using "+model_2)
    else:
        await update_chat(message.from_user.id, model_1)
        await bot.reply_to(message , "Now you are using "+model_1)

async def gemini_private_handler(message: Message, bot: TeleBot) -> None:
    contents = message.text.strip()
    await gemini.gemini_stream(bot,message,contents)

async def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption or ""
    if message.chat.type != "private" and not s.startswith("/gemini"):
        return
    try:
        m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
        file = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file.file_path)
        image_stream = io.BytesIO(photo_file)
        image = Image.open(image_stream)
        contents = [image, m]
    except Exception:
        traceback.print_exc()
        await bot.reply_to(message, error_info)
        return
    await gemini.gemini_stream(bot, message, contents)
