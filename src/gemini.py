import io
import time
import traceback
from telebot.types import Message
from md2tgmd import escape
from telebot import TeleBot

from config import conf
from utils import init_user

model_1 = conf["model_1"]
model_2 = conf["model_2"]
error_info = conf["error_info"]
before_generate_info = conf["before_generate_info"]
download_pic_notify = conf["download_pic_notify"]


async def gemini_stream(bot:TeleBot, message:Message, contents:str|list) -> None:
    sent_message = await bot.reply_to(message, "🤖 Gerando respostas...")
    chat, lock = await init_user(message.from_user.id)
    
    try:
        await lock.acquire()
        
        response = await chat.send_message_async(contents)
        full_plain_message = response.text
    except:
        info = error_info + traceback.format_exc()
        await bot.edit_message_text(info, sent_message.chat.id, sent_message.message_id)
    else:
        await bot.edit_message_text(escape(full_plain_message),
                                   sent_message.chat.id,
                                   sent_message.message_id,
                                   parse_mode="MarkdownV2")
    finally:
        lock.release()


async def gemini_photo(bot:TeleBot, message:Message) -> None:
    sent_message = await bot.reply_to(message, before_generate_info)
    file_path = await bot.get_file(message.photo[-1].file_id)
    download_file = await bot.download_file(file_path.file_path)
    chat, lock = await init_user(message.from_user.id)
    await bot.edit_message_text(download_pic_notify, sent_message.chat.id, sent_message.message_id)
    
    try:
        await lock.acquire()
        
        pil_image = io.BytesIO(download_file)
        response = await chat.send_message_async([message.caption if message.caption else "Descreva esta imagem", pil_image])
        full_plain_message = response.text
    except:
        info = error_info + traceback.format_exc()
        await bot.edit_message_text(info, sent_message.chat.id, sent_message.message_id)
    else:
        await bot.edit_message_text(escape(full_plain_message),
                                   sent_message.chat.id,
                                   sent_message.message_id,
                                   parse_mode="MarkdownV2")
    finally:
        lock.release()
