from telebot import TeleBot
from telebot.types import Message
from md2tgmd import escape
import traceback
from config import conf, messages, command_descriptions
import gemini
import telebot
import json
import os
import time
import asyncio

model_1 = conf["model_1"]
model_2 = conf["model_2"]

gemini_chat_dict = gemini.gemini_chat_dict
gemini_pro_chat_dict = gemini.gemini_pro_chat_dict
default_model_dict = gemini.default_model_dict
language_dict = gemini.language_dict

# 存储用户设置的系统提示
user_system_prompts = {}
# 存储用户选择的模型
user_models = {}
# 存储用户的语言设置
user_languages = {}
# 存储用户的搜索设置
user_search_settings = {}

# 获取用户语言
def get_user_language(user_id):
    return user_languages.get(str(user_id), conf['default_language'])

# 获取用户特定语言的消息
def get_message(message_key, user_id):
    lang = get_user_language(user_id)
    return messages[lang][message_key]

# --- System Prompt Command Handlers ---
async def set_system_prompt_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    try:
        prompt_text = message.text.strip().split(maxsplit=1)[1].strip()
        if not prompt_text:
            await bot.reply_to(message, escape(gemini.get_message("system_prompt_set_usage", user_id)), parse_mode="MarkdownV2")
            return
        gemini.save_system_prompt(prompt_text)
        await bot.reply_to(message, escape(gemini.get_message("system_prompt_set_success", user_id) + f"\n---\n{prompt_text}\n---"), parse_mode="MarkdownV2")
    except IndexError:
        await bot.reply_to(message, escape(gemini.get_message("system_prompt_set_usage", user_id)), parse_mode="MarkdownV2")
    except Exception as e:
        traceback.print_exc()
        await bot.reply_to(message, f"{gemini.get_message('error_info', user_id)}\nDetail: {str(e)}")

async def view_system_prompt_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    try:
        if gemini.current_system_prompt:
            response_text = gemini.get_message("system_prompt_current", user_id) + f"\n---\n{gemini.current_system_prompt}\n---"
        else:
            response_text = gemini.get_message("system_prompt_not_set", user_id)
        await bot.reply_to(message, escape(response_text), parse_mode="MarkdownV2")
    except Exception as e:
        traceback.print_exc()
        await bot.reply_to(message, f"{gemini.get_message('error_info', user_id)}\nDetail: {str(e)}")

async def delete_system_prompt_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    try:
        gemini.save_system_prompt(None) # Passing None deletes the prompt
        await bot.reply_to(message, escape(gemini.get_message("system_prompt_deleted_success", user_id)), parse_mode="MarkdownV2")
    except Exception as e:
        traceback.print_exc()
        await bot.reply_to(message, f"{gemini.get_message('error_info', user_id)}\nDetail: {str(e)}")
# --- End System Prompt Command Handlers ---

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
        default_model_dict[str(user_id)] = False
        await gemini.gemini_stream(bot, message, m, model_2)
    else:
        if default_model_dict[str(user_id)]:
            await gemini.gemini_stream(bot, message, m, model_1)
        else:
            await gemini.gemini_stream(bot, message, m, model_2)

async def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    user_id = message.from_user.id
    s = message.caption or ""
    # In private chat, any photo can be processed. 
    # In group chat, caption must start with /gemini (or a specific command if you want to route it differently)
    if message.chat.type != "private" and not (s and s.lower().startswith("/gemini")):
        if not (s and s.lower().startswith("/edit")):
             return # Ignore if not a command in group chat

    try:
        # Try to extract text after a command, or use the whole caption, or default to empty.
        # This logic might need adjustment based on how you want to trigger photo processing with text.
        command_text = ""
        if s:
            parts = s.strip().split(maxsplit=1)
            if len(parts) > 1 and (parts[0].lower() == "/gemini" or parts[0].lower() == "/edit"):
                command_text = parts[1].strip()
            elif message.chat.type == "private": # In private, if no command, assume caption is the prompt
                command_text = s.strip()
        # If no command_text derived and it was a group chat, it implies it was just /gemini or /edit with no text
        # In that case, command_text remains "" which is fine.

        file_path = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file_path.file_path)
    except Exception:
        traceback.print_exc()
        await bot.reply_to(message, gemini.get_message("error_info", user_id))
        return
    await gemini.gemini_edit(bot, message, command_text, photo_file)

async def gemini_edit_handler(message: Message, bot: TeleBot) -> None: # This might be redundant if gemini_photo_handler covers /edit
    user_id = message.from_user.id
    if not message.photo:
        await bot.reply_to(message, gemini.get_message("send_photo_request", user_id))
        return
    s = message.caption or ""
    command_text = ""
    if s:
        parts = s.strip().split(maxsplit=1)
        if len(parts) > 1: # Assumes command like /edit <prompt>
            command_text = parts[1].strip()
        # If just /edit with a photo, command_text will be empty.

    try:
        file_path = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file_path.file_path)
    except Exception as e:
        traceback.print_exc()
        await bot.reply_to(message, f"{gemini.get_message('error_info', user_id)}\nDetail: {str(e)}")
        return
    await gemini.gemini_edit(bot, message, command_text, photo_file)

async def draw_handler(message: Message, bot: TeleBot) -> None:
    # 使用 model_3 通过聊天会话生成图像
    # 不使用专用的图像生成 API，而是通过常规聊天功能检测并返回 inline_data
    user_id = message.from_user.id
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        await bot.reply_to(message, escape(gemini.get_message("draw_usage_tip", user_id)), parse_mode="MarkdownV2")
        return
    
    await gemini.gemini_draw(bot, message, m)

# 新添加的测试搜索功能处理器
async def test_search_handler(message: Message, bot: TeleBot) -> None:
    """处理 /testsearch 命令，测试Google搜索功能"""
    # 只允许私聊使用此命令
    if message.chat.type != 'private':
        await bot.reply_to(message, "此命令只能在私聊中使用。")
        return
    
    print(f"用户 {message.from_user.id} 请求测试 Google 搜索功能")
    await gemini.test_search_capability(bot, message)

# 添加切换搜索功能的命令处理函数
async def toggle_search_handler(message: Message):
    try:
        user_id = str(message.from_user.id)
        # 切换搜索设置，如果不存在则默认为开启状态（True）
        current_setting = user_search_settings.get(user_id, True)
        new_setting = not current_setting
        user_search_settings[user_id] = new_setting
        
        # 获取用户语言并发送合适的消息
        if new_setting:
            reply_message = get_message('search_enabled', user_id)
        else:
            reply_message = get_message('search_disabled', user_id)
        
        await message.bot.reply_to(message, reply_message)
    except Exception as e:
        traceback.print_exc()
        await message.bot.reply_to(message, f"Error toggling search: {str(e)}")

# 添加测试搜索功能的命令处理函数
async def test_search_handler(message: Message):
    try:
        await test_search_capability(message.bot, message)
    except Exception as e:
        traceback.print_exc()
        await message.bot.reply_to(message, f"Error testing search: {str(e)}")
