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
        await bot.reply_to(message , escape("欢迎，您现在可以向我提问。\n例如：`约翰·列侬是谁？`"), parse_mode="MarkdownV2")
    except IndexError:
        await bot.reply_to(message, error_info)

async def gemini_stream_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("请在 /gemini 后添加您想说的内容。\n例如：`/gemini 约翰·列侬是谁？`"), parse_mode="MarkdownV2")
        return
    await gemini.gemini_stream(bot, message, m, model_1)

async def gemini_pro_stream_handler(message: Message, bot: TeleBot) -> None:
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("请在 /gemini_pro 后添加您想说的内容。\n例如：`/gemini_pro 约翰·列侬是谁？`"), parse_mode="MarkdownV2")
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
    await bot.reply_to(message, "您的历史记录已被清除")

async def switch(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        await bot.reply_to( message , "此命令仅适用于私聊！")
        return
    # Check if the chat is already in default_model_dict.
    if str(message.from_user.id) not in default_model_dict:
        default_model_dict[str(message.from_user.id)] = False
        await bot.reply_to( message , "您现在正在使用 "+model_2)
        return
    if default_model_dict[str(message.from_user.id)] == True:
        default_model_dict[str(message.from_user.id)] = False
        await bot.reply_to( message , "您现在正在使用 "+model_2)
    else:
        default_model_dict[str(message.from_user.id)] = True
        await bot.reply_to( message , "您现在正在使用 "+model_1)

async def gemini_private_handler(message: Message, bot: TeleBot) -> None:
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
            await bot.reply_to(message, error_info)
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
            await bot.reply_to(message, error_info)
            return
        await gemini.gemini_edit(bot, message, m, photo_file)

async def gemini_edit_handler(message: Message, bot: TeleBot) -> None:
    if not message.photo:
        await bot.reply_to(message, "请发送一张照片")
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
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape("请在 /draw 后添加您想绘制的内容。\n例如：`/draw 给我画一只猫。`"), parse_mode="MarkdownV2")
        return
    
    # reply to the message first, then delete the "drawing..." message
    drawing_msg = await bot.reply_to(message, "正在绘制...")
    try:
        await gemini.gemini_draw(bot, message, m)
    finally:
        await bot.delete_message(chat_id=message.chat.id, message_id=drawing_msg.message_id)
