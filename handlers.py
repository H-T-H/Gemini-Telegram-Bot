from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
import traceback
from config import conf
import gemini

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
        await bot.reply_to(message , escape("Welcome, you can ask me questions now. \nFor example: `Who is john lennon?`"), parse_mode="MarkdownV2")
    except IndexError:
        await bot.reply_to(message, error_info)

async def gemini_stream_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Please add what you want to say after /gemini. \nFor example: `/gemini Who is john lennon?`"), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, m, model_1)

async def gemini_pro_stream_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Please add what you want to say after /gemini_pro. \nFor example: `/gemini_pro Who is john lennon?`"), parse_mode="MarkdownV2")
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
    await bot.reply_to(message, "Your history has been cleared")

async def switch(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        await bot.reply_to( message , "This command is only for private chat !")
        return
    # Check if the chat is already in default_model_dict.
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
    if message.content_type == 'photo': # Check if the message is a photo
        s = message.caption or "" # Get caption as prompt
        try:
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
            await gemini.gemini_image_understand(bot, message, photo_file, prompt=s)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, error_info)
        return

    m = message.text.strip()
    if str(message.from_user.id) not in default_model_dict:
        default_model_dict[str(message.from_user.id)] = True
        await gemini.gemini_stream(bot,message,m,model_1)
    else:
        if default_model_dict[str(message.from_user.id)]:
            await gemini.gemini_stream(bot,message,m,model_1)
        else:
            await gemini.gemini_stream(bot,message,m,model_2)

async def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption or ""
    # If it's a private chat and no command, or it's a command that is NOT /edit (or other future model_3 specific commands)
    if message.chat.type == "private" and not s.startswith("/"):
        try:
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
            # Use the caption as a prompt if available
            await gemini.gemini_image_understand(bot, message, photo_file, prompt=s)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, error_info)
        return
    
    # Existing logic for commands like /edit or for group chats (where we might assume commands are necessary for image processing)
    # Or if the command is specifically /edit (or others that should use model_3)
    if message.chat.type != "private" or (s.startswith("/edit")):
        try:
            # For /edit, we expect the command prefix, so we try to strip it.
            # If other commands use model_3 with photos, adjust stripping accordingly.
            m = ""
            if s.startswith("/edit"):
                 m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
            else: # For group chats without specific command, or other future commands.
                 m = s # Use the whole caption as prompt for model_3 if not /edit
            
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
            await gemini.gemini_edit(bot, message, m, photo_file)
        except Exception:
            traceback.print_exc()
            await bot.reply_to(message, error_info)
        return
    # Fallback for private chat with other commands if any (currently none that take photos directly without specific handling)
    # This part might need adjustment if new photo commands are added that don't use model_3
    # For now, if it's private, has a command, and it's not /edit, it's unhandled for photos by this logic block.
    # Consider adding a default reply or error if a private chat photo message with an unhandled command is received.


async def gemini_edit_handler(message: Message, bot: TeleBot) -> None:
    if not message.photo:
        await bot.reply_to(message, "pls send a photo")
        return
    s = message.caption or ""
    try:
        m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
        file_path = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file_path.file_path)
    except Exception as e:
        traceback.print_exc()
        # It's better to show a generic error or the specific error if it's safe to display
        await bot.reply_to(message, f"{error_info}. Details: {str(e)}")
        return
    await gemini.gemini_edit(bot, message, m, photo_file)

async def draw_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("Please add what you want to draw after /draw. \nFor example: `/draw draw me a cat.`"), parse_mode="MarkdownV2")
        return
    
    # reply to the message first, then delete the "drawing..." message
    drawing_msg = await bot.reply_to(message, "Drawing...")
    try:
        await gemini.gemini_draw(bot, message, m)
    finally:
        await bot.delete_message(chat_id=message.chat.id, message_id=drawing_msg.message_id)
