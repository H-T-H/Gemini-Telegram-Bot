import traceback
import io
from PIL import Image
import gemini as gemini
from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
from config import conf
from utils import switch_model, clear_history

error_info              =       conf["error_info"]
before_generate_info    =       conf["before_generate_info"]
download_pic_notify     =       conf["download_pic_notify"]
model_1                 =       conf["model_1"]
model_2                 =       conf["model_2"]


async def start(message: Message, bot: TeleBot) -> None:
    try:
        await bot.reply_to(message , escape("Bem-vindo, você pode me fazer perguntas agora. \nPor exemplo: `Quem é John Lennon?`"), parse_mode="MarkdownV2")
    except IndexError:
        await bot.reply_to(message, error_info)


async def gemini_handler(message: Message, bot: TeleBot) -> None:
    try:
        contents = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Por favor, adicione o que você quer dizer após /gemini. \nPor exemplo: `/gemini Quem é John Lennon?`"), parse_mode="MarkdownV2")
        return

    await gemini.gemini_stream(bot, message, contents)


async def clear(message: Message, bot: TeleBot) -> None:
    await clear_history(message.from_user.id)
    await bot.reply_to(message, "Seu histórico foi apagado")


async def switch(message: Message, bot: TeleBot) -> None:
    model = await switch_model(message.from_user.id)
    await bot.reply_to(message , "Agora você está usando " + model)


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
