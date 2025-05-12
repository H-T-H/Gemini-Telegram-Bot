import argparse
import traceback
import asyncio
import re
import telebot
from telebot.async_telebot import AsyncTeleBot
import handlers
from config import conf, generation_config, safety_settings, lang_settings
from gemini import user_language_dict, get_user_lang
import logging
import time
import random

# 配置日志记录
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Init args
parser = argparse.ArgumentParser()
parser.add_argument("tg_token", help="telegram token")
parser.add_argument("GOOGLE_GEMINI_KEY", help="Google Gemini API key")
options = parser.parse_args()
print("Arg parse done.")


async def main():
    # Init bot
    bot = AsyncTeleBot(options.tg_token)
    
    # 定义中英文菜单
    menu_zh = [
        telebot.types.BotCommand("start", "开始使用"),
        telebot.types.BotCommand("gemini", f"使用 {conf['model_1']}"),
        telebot.types.BotCommand("gemini_pro", f"使用 {conf['model_2']}"),
        telebot.types.BotCommand("draw", "绘图"),
        telebot.types.BotCommand("edit", "编辑图片"),
        telebot.types.BotCommand("clear", "清除历史记录"),
        telebot.types.BotCommand("switch", "切换默认模型"),
        telebot.types.BotCommand("system", "系统提示词管理"),
        telebot.types.BotCommand("lang", "切换语言 (中/英)"),
        telebot.types.BotCommand("language", "显示当前语言")
    ]
    
    menu_en = [
        telebot.types.BotCommand("start", "Start"),
        telebot.types.BotCommand("gemini", f"using {conf['model_1']}"),
        telebot.types.BotCommand("gemini_pro", f"using {conf['model_2']}"),
        telebot.types.BotCommand("draw", "draw picture"),
        telebot.types.BotCommand("edit", "edit photo"),
        telebot.types.BotCommand("clear", "Clear all history"),
        telebot.types.BotCommand("switch", "switch default model"),
        telebot.types.BotCommand("system", "Manage system prompts"),
        telebot.types.BotCommand("lang", "switch language (中/英)"),
        telebot.types.BotCommand("language", "show current language")
    ]
    
    # 默认使用中文菜单
    await bot.delete_my_commands(scope=None, language_code=None)
    await bot.set_my_commands(menu_zh)
    print("Bot init done.")

    # 语言切换后更新菜单的处理函数
    async def on_lang_changed(message, new_lang):
        user_scope = telebot.types.BotCommandScopeChat(message.chat.id)
        if new_lang == "zh":
            await bot.set_my_commands(menu_zh, scope=user_scope)
        else:
            await bot.set_my_commands(menu_en, scope=user_scope)
    
    # 修改语言切换处理函数，加入菜单切换
    async def language_switch_handler_with_menu(message: telebot.types.Message, bot: AsyncTeleBot) -> None:
        user_id_str = str(message.from_user.id)
        current_lang = get_user_lang(user_id_str)
        
        # 切换语言
        new_lang = "en" if current_lang == "zh" else "zh"
        user_language_dict[user_id_str] = new_lang
        
        # 更新菜单
        await on_lang_changed(message, new_lang)
        
        # 发送语言切换确认消息
        await bot.reply_to(message, lang_settings[new_lang]["language_switched"])

    # 系统提示词命令处理函数
    async def system_prompt_handler(message: telebot.types.Message, bot: AsyncTeleBot) -> None:
        """处理 /system 命令，提供系统提示词管理选项"""
        user_id = message.from_user.id
        lang = get_user_lang(user_id)
        
        # 准备菜单文本
        if lang == "zh":
            text = (
                "📝 *系统提示词管理*\n\n"
                "您可以使用以下命令管理系统提示词：\n"
                "• `/system show` - 显示当前系统提示词\n"
                "• `/system set <提示词>` - 设置新的系统提示词\n"
                "• `/system reset` - 重置为默认系统提示词\n"
                "• `/system delete` - 删除自定义系统提示词\n\n"
                "系统提示词会影响 AI 的行为和回复方式。"
            )
        else:
            text = (
                "📝 *System Prompt Management*\n\n"
                "You can manage system prompts with these commands:\n"
                "• `/system show` - Show current system prompt\n"
                "• `/system set <prompt>` - Set a new system prompt\n"
                "• `/system reset` - Reset to default system prompt\n"
                "• `/system delete` - Delete custom system prompt\n\n"
                "System prompts affect AI behavior and response style."
            )
        
        try:
            await bot.send_message(message.chat.id, text, parse_mode="Markdown")
        except Exception as e:
            # 如果 Markdown 解析失败，尝试发送纯文本
            text = text.replace("*", "").replace("`", "")
            await bot.send_message(message.chat.id, text)

    # 处理系统提示词的子命令
    async def system_prompt_command_handler(message: telebot.types.Message, bot: AsyncTeleBot) -> None:
        """处理 /system 的子命令，如 show, set, reset, delete"""
        from gemini import show_system_prompt, set_system_prompt, reset_system_prompt, delete_system_prompt
        
        command_text = message.text.strip()
        command_parts = command_text.split(maxsplit=2)
        
        # 子命令至少需要两部分：/system 和子命令名称
        if len(command_parts) < 2:
            await system_prompt_handler(message, bot)
            return
        
        subcommand = command_parts[1].lower()
        
        if subcommand == "show":
            await show_system_prompt(bot, message)
        elif subcommand == "reset":
            await reset_system_prompt(bot, message)
        elif subcommand == "delete":
            await delete_system_prompt(bot, message)
        elif subcommand == "set" and len(command_parts) >= 3:
            # 提取提示词文本
            prompt_text = command_parts[2]
            await set_system_prompt(bot, message, prompt_text)
        elif subcommand == "set":
            # 如果是 /system set 但没有提供提示词
            user_id = message.from_user.id
            lang = get_user_lang(user_id)
            error_msg = "请在命令后提供提示词文本。例如：\n`/system set 你是一个有帮助的助手`" if lang == "zh" else \
                      "Please provide prompt text after the command. For example:\n`/system set You are a helpful assistant`"
            await bot.reply_to(message, error_msg)
        else:
            # 未知子命令，显示帮助信息
            await system_prompt_handler(message, bot)

    # Init commands
    bot.register_message_handler(handlers.start,                         commands=['start'],         pass_bot=True)
    bot.register_message_handler(handlers.gemini_stream_handler,         commands=['gemini'],        pass_bot=True)
    bot.register_message_handler(handlers.gemini_pro_stream_handler,     commands=['gemini_pro'],    pass_bot=True)
    bot.register_message_handler(handlers.draw_handler,                  commands=['draw'],          pass_bot=True)
    bot.register_message_handler(handlers.gemini_edit_handler,           commands=['edit'],          pass_bot=True)
    bot.register_message_handler(handlers.clear,                         commands=['clear'],         pass_bot=True)
    bot.register_message_handler(handlers.switch,                        commands=['switch'],        pass_bot=True)
    bot.register_message_handler(language_switch_handler_with_menu,      commands=['lang'],          pass_bot=True)
    bot.register_message_handler(handlers.language_status_handler,       commands=['language'],      pass_bot=True)
    bot.register_message_handler(system_prompt_handler,                  commands=['system'],        pass_bot=True)
    bot.register_message_handler(system_prompt_command_handler,          regexp=r'^\/system\s+\w+', pass_bot=True)
    bot.register_message_handler(handlers.gemini_photo_handler,          content_types=["photo"],    pass_bot=True)
    bot.register_message_handler(
        handlers.gemini_private_handler,
        func=lambda message: message.chat.type == "private",
        content_types=['text'],
        pass_bot=True)

    # Start bot with retry logic
    max_retries = 5
    retry_count = 0
    base_delay = 1  # 初始延迟1秒
    max_delay = 30  # 最大延迟30秒

    while True:
        try:
            print("Starting Gemini_Telegram_Bot.")
            await bot.polling(
                none_stop=True,
                interval=1,
                timeout=30,  # 增加超时时间
                allowed_updates=["message", "callback_query"],
                skip_pending=True,
                request_timeout=30  # 增加请求超时时间
            )
        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"Max retries ({max_retries}) exceeded. Stopping bot.")
                break
                
            # 计算指数退避延迟
            delay = min(max_delay, base_delay * (2 ** (retry_count - 1)))
            
            # 添加随机抖动，避免多个实例同时重试
            jitter = delay * 0.1  # 10% 的抖动
            delay = delay + (jitter * (2 * (0.5 - random.random())))
            
            logger.error(f"Error in polling: {e}")
            logger.info(f"Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})")
            
            # 释放资源
            if hasattr(bot, 'session') and bot.session:
                try:
                    await bot.session.close()
                    logger.info("Bot session closed successfully")
                except Exception as session_err:
                    logger.error(f"Error closing session: {session_err}")
                    
            # 等待后重试
            await asyncio.sleep(delay)
        else:
            # 如果正常退出循环，退出重试
            break

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Unhandled exception: {e}")
        traceback.print_exc()
