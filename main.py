import argparse
import traceback
import asyncio
import re
import telebot
from telebot.async_telebot import AsyncTeleBot
import handlers
from config import conf, generation_config, safety_settings, lang_settings
from gemini import user_language_dict, get_user_lang

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
    bot.register_message_handler(handlers.gemini_photo_handler,          content_types=["photo"],    pass_bot=True)
    bot.register_message_handler(
        handlers.gemini_private_handler,
        func=lambda message: message.chat.type == "private",
        content_types=['text'],
        pass_bot=True)

    # Start bot
    print("Starting Gemini_Telegram_Bot.")
    await bot.polling(
        none_stop=True,
        interval=1,
        timeout=20,
        allowed_updates=["message", "callback_query"],
        skip_pending=True,
        request_timeout=20
    )

if __name__ == '__main__':
    asyncio.run(main())
