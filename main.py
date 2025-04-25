import argparse
import traceback
import asyncio
import re
import telebot
from telebot.async_telebot import AsyncTeleBot
import handlers
from config import conf, generation_config, safety_settings, command_descriptions

# Init args
parser = argparse.ArgumentParser()
parser.add_argument("tg_token", help="telegram token")
parser.add_argument("GOOGLE_GEMINI_KEY", help="Google Gemini API key")
options = parser.parse_args()
print("Arg parse done.")


async def main():
    # Init bot
    bot = AsyncTeleBot(options.tg_token)
    await bot.delete_my_commands(scope=None, language_code=None)
    
    # 设置命令，使用默认语言（中文）
    lang = conf["default_language"]
    await bot.set_my_commands(
commands=[
        telebot.types.BotCommand("start", command_descriptions[lang]["start"]),
        telebot.types.BotCommand("gemini", command_descriptions[lang]["gemini"]),
        telebot.types.BotCommand("gemini_pro", command_descriptions[lang]["gemini_pro"]),
        telebot.types.BotCommand("draw", command_descriptions[lang]["draw"]),
        telebot.types.BotCommand("edit", command_descriptions[lang]["edit"]),
        telebot.types.BotCommand("clear", command_descriptions[lang]["clear"]),
        telebot.types.BotCommand("switch", command_descriptions[lang]["switch"]),
        telebot.types.BotCommand("language", command_descriptions[lang]["language"])
    ],
)
    print("Bot init done.")

    # Init commands
    bot.register_message_handler(handlers.start,                         commands=['start'],         pass_bot=True)
    bot.register_message_handler(handlers.gemini_stream_handler,         commands=['gemini'],        pass_bot=True)
    bot.register_message_handler(handlers.gemini_pro_stream_handler,     commands=['gemini_pro'],    pass_bot=True)
    bot.register_message_handler(handlers.draw_handler,                  commands=['draw'],          pass_bot=True)
    bot.register_message_handler(handlers.gemini_edit_handler,           commands=['edit'],          pass_bot=True)
    bot.register_message_handler(handlers.clear,                         commands=['clear'],         pass_bot=True)
    bot.register_message_handler(handlers.switch,                        commands=['switch'],        pass_bot=True)
    bot.register_message_handler(handlers.language_switch,               commands=['language'],      pass_bot=True)
    bot.register_message_handler(handlers.gemini_photo_handler,          content_types=["photo"],    pass_bot=True)
    bot.register_message_handler(
        handlers.gemini_private_handler,
        func=lambda message: message.chat.type == "private",
        content_types=['text'],
        pass_bot=True)

    # Start bot
    print("正在启动 Gemini_Telegram_Bot。")
    await bot.polling(none_stop=True)

if __name__ == '__main__':
    asyncio.run(main())
