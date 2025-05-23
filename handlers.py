"""
Defines handlers for Telegram bot commands and messages,
routing them to appropriate Gemini API interactions.
"""
from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
import traceback
from config import conf
import gemini

gemini_chat_dict        = gemini.gemini_chat_dict
gemini_pro_chat_dict    = gemini.gemini_pro_chat_dict
default_model_dict      = gemini.default_model_dict
gemini_draw_dict        = gemini.gemini_draw_dict

async def start(message: Message, bot: TeleBot) -> None:
    """Handles the /start command and sends a welcome message."""
    try:
        await bot.reply_to(message , escape("Welcome, you can ask me questions now. \nFor example: `Who is john lennon?`"), parse_mode="MarkdownV2")
    except IndexError:
        await bot.reply_to(message, conf["error_info"])

async def gemini_stream_handler(message: Message, bot: TeleBot) -> None:
    """Handles the /gemini command for streaming text responses from the default model."""
    try:
        # Extract the prompt text after the command
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Please add what you want to say after /gemini. \nFor example: `/gemini Who is john lennon?`"), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, m, conf["model_1"])

async def gemini_pro_stream_handler(message: Message, bot: TeleBot) -> None:
    """Handles the /gemini_pro command for streaming text responses from the pro model."""
    try:
        # Extract the prompt text after the command
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Please add what you want to say after /gemini_pro. \nFor example: `/gemini_pro Who is john lennon?`"), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, m, conf["model_2"])

async def clear(message: Message, bot: TeleBot) -> None:
    """Handles the /clear command to erase the user's chat history with the bot."""
    # Check if the chat is already in gemini_chat_dict.
    if (str(message.from_user.id) in gemini_chat_dict):
        del gemini_chat_dict[str(message.from_user.id)]
    if (str(message.from_user.id) in gemini_pro_chat_dict):
        del gemini_pro_chat_dict[str(message.from_user.id)]
    if (str(message.from_user.id) in gemini_draw_dict):
        del gemini_draw_dict[str(message.from_user.id)]
    await bot.reply_to(message, "Your history has been cleared")

async def switch(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        await bot.reply_to( message , "This command is only for private chat !")
        return
    # Check if the chat is already in default_model_dict, otherwise initialize it.
    if str(message.from_user.id) not in default_model_dict:
        default_model_dict[str(message.from_user.id)] = False # Default to model_2
        await bot.reply_to( message , "Now you are using "+conf["model_2"])
        return
    # Toggle the model
    if default_model_dict[str(message.from_user.id)] == True:
        default_model_dict[str(message.from_user.id)] = False
        await bot.reply_to( message , "Now you are using "+conf["model_2"])
    else:
        default_model_dict[str(message.from_user.id)] = True
        await bot.reply_to( message , "Now you are using "+conf["model_1"])

async def gemini_private_handler(message: Message, bot: TeleBot) -> None:
    """Handles direct text messages in private chats, using the user's selected default model."""
    m = message.text.strip()
    # Initialize default model for the user if not set
    if str(message.from_user.id) not in default_model_dict:
        default_model_dict[str(message.from_user.id)] = True
        await gemini.gemini_stream(bot,message,m,conf["model_1"])
    else:
        if default_model_dict[str(message.from_user.id)]:
            await gemini.gemini_stream(bot,message,m,conf["model_1"])
        else:
            await gemini.gemini_stream(bot,message,m,conf["model_2"])

async def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        s = message.caption or ""
        # In group chats, only respond if the caption starts with /gemini
        if not s or not (s.startswith("/gemini")):
            return
        try:
            m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, conf["error_info"])
            return
        await gemini.gemini_edit(bot, message, m, photo_file)
    else: # Private chat
        s = message.caption or ""
        try:
            # Extract prompt from caption, if any
            m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, conf["error_info"])
            return
        await gemini.gemini_edit(bot, message, m, photo_file)

async def gemini_edit_handler(message: Message, bot: TeleBot) -> None:
    """Handles the /edit command for editing an image with a prompt."""
    if not message.photo:
        await bot.reply_to(message, "pls send a photo")
        return
    s = message.caption or ""
    try:
        # Extract prompt from caption, if any
        m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
        file_path = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file_path.file_path)
    except Exception as e:
        traceback.print_exc()
        await bot.reply_to(message, e.str())
        return
    await gemini.gemini_edit(bot, message, m, photo_file)

async def draw_handler(message: Message, bot: TeleBot) -> None:
    """Handles the /draw command to generate an image based on a text prompt."""
    try:
        # Extract the prompt text after the command
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Please add what you want to draw after /draw. \nFor example: `/draw draw me a cat.`"), parse_mode="MarkdownV2")
        return
    
    
    # Reply with a "Drawing..." message, which will be deleted after the image is sent
    drawing_msg = await bot.reply_to(message, "Drawing...")
    try:
        await gemini.gemini_draw(bot, message, m)
    finally:
        await bot.delete_message(chat_id=message.chat.id, message_id=drawing_msg.message_id)
