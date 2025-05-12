from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
import traceback
from config import conf, lang_settings
import gemini

# 直接从 gemini 模块导入语言相关功能
from gemini import (
    get_user_text, get_user_lang, switch_language, get_language,
    set_system_prompt, delete_system_prompt, reset_system_prompt, show_system_prompt
)

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
        welcome_msg = get_user_text(message.from_user.id, "welcome_message")
        await bot.reply_to(message, escape(welcome_msg), parse_mode="MarkdownV2")
    except IndexError:
        error_msg = get_user_text(message.from_user.id, "error_info")
        await bot.reply_to(message, error_msg)

async def gemini_stream_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        help_msg = get_user_text(message.from_user.id, "gemini_prompt_help")
        await bot.reply_to(message, escape(help_msg), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, m, model_1)

async def gemini_pro_stream_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        help_msg = get_user_text(message.from_user.id, "gemini_pro_prompt_help")
        await bot.reply_to(message, escape(help_msg), parse_mode="MarkdownV2")
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
    cleared_msg = get_user_text(message.from_user.id, "history_cleared")
    await bot.reply_to(message, cleared_msg)

async def switch(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        private_chat_msg = get_user_text(message.from_user.id, "private_chat_only")
        await bot.reply_to(message, private_chat_msg)
        return
    # Check if the chat is already in default_model_dict.
    if str(message.from_user.id) not in default_model_dict:
        default_model_dict[str(message.from_user.id)] = False
        now_using_msg = get_user_text(message.from_user.id, "now_using_model")
        await bot.reply_to(message, f"{now_using_msg} {model_2}")
        return
    if default_model_dict[str(message.from_user.id)] == True:
        default_model_dict[str(message.from_user.id)] = False
        now_using_msg = get_user_text(message.from_user.id, "now_using_model")
        await bot.reply_to(message, f"{now_using_msg} {model_2}")
    else:
        default_model_dict[str(message.from_user.id)] = True
        now_using_msg = get_user_text(message.from_user.id, "now_using_model")
        await bot.reply_to(message, f"{now_using_msg} {model_1}")

# 新增：语言切换处理函数
async def language_switch_handler(message: Message, bot: TeleBot) -> None:
    await switch_language(bot, message)

# 新增：获取当前语言状态处理函数
async def language_status_handler(message: Message, bot: TeleBot) -> None:
    await get_language(bot, message)

async def gemini_private_handler(message: Message, bot: TeleBot) -> None:
    if message.content_type == 'photo': # Check if the message is a photo
        s = message.caption or "" # Get caption as prompt
        try:
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
            await gemini.gemini_image_understand(bot, message, photo_file, prompt=s)
        except Exception:
            traceback.print_exc()
            error_msg = get_user_text(message.from_user.id, "error_info")
            await bot.reply_to(message, error_msg)
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
            error_msg = get_user_text(message.from_user.id, "error_info")
            await bot.reply_to(message, error_msg)
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
            error_msg = get_user_text(message.from_user.id, "error_info")
            await bot.reply_to(message, error_msg)
        return
    # Fallback for private chat with other commands if any (currently none that take photos directly without specific handling)
    # This part might need adjustment if new photo commands are added that don't use model_3
    # For now, if it's private, has a command, and it's not /edit, it's unhandled for photos by this logic block.
    # Consider adding a default reply or error if a private chat photo message with an unhandled command is received.


async def gemini_edit_handler(message: Message, bot: TeleBot) -> None:
    if not message.photo:
        photo_prompt_msg = get_user_text(message.from_user.id, "send_photo_prompt")
        await bot.reply_to(message, photo_prompt_msg)
        return
    s = message.caption or ""
    try:
        m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
        file_path = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file_path.file_path)
    except Exception as e:
        traceback.print_exc()
        # It's better to show a generic error or the specific error if it's safe to display
        error_msg = get_user_text(message.from_user.id, "error_info")
        await bot.reply_to(message, f"{error_msg}. Details: {str(e)}")
        return
    await gemini.gemini_edit(bot, message, m, photo_file)

async def draw_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        draw_help_msg = get_user_text(message.from_user.id, "draw_prompt_help")
        await bot.reply_to(message, escape(draw_help_msg), parse_mode="MarkdownV2")
        return
    
    # reply to the message first, then delete the "drawing..." message
    drawing_msg = get_user_text(message.from_user.id, "drawing_message")
    drawing_msg_obj = await bot.reply_to(message, drawing_msg)
    try:
        await gemini.gemini_draw(bot, message, m)
    finally:
        await bot.delete_message(chat_id=message.chat.id, message_id=drawing_msg_obj.message_id)

# 系统提示词设置处理函数
async def system_prompt_handler(message: Message, bot: TeleBot) -> None:
    try:
        prompt = message.text.strip().split(maxsplit=1)[1].strip()
        await set_system_prompt(bot, message, prompt)
    except IndexError:
        help_msg = get_user_text(message.from_user.id, "system_prompt_help")
        await bot.reply_to(message, help_msg)

# 删除系统提示词处理函数
async def system_prompt_clear_handler(message: Message, bot: TeleBot) -> None:
    await delete_system_prompt(bot, message)

# 重置系统提示词处理函数
async def system_prompt_reset_handler(message: Message, bot: TeleBot) -> None:
    await reset_system_prompt(bot, message)

# 显示系统提示词处理函数
async def system_prompt_show_handler(message: Message, bot: TeleBot) -> None:
    await show_system_prompt(bot, message)
