import argparse
import os
import traceback
import asyncio
import re
import telebot
from telebot.async_telebot import AsyncTeleBot
import handlers
from config import conf, generation_config, safety_settings
from core.database import ensure_db_initialized

# Init args
parser = argparse.ArgumentParser()
parser.add_argument("tg_token", help="telegram token")
parser.add_argument("GOOGLE_GEMINI_KEY", help="Google Gemini API key")
options = parser.parse_args()
print("Arg parse done.")


async def main():
    # Set GOOGLE_GEMINI_KEY from command-line options to an environment variable
    # so that core.ai_client.py can access it via os.getenv()
    if options.GOOGLE_GEMINI_KEY:
        os.environ['GOOGLE_GEMINI_KEY'] = options.GOOGLE_GEMINI_KEY
    else:
        print("Error: GOOGLE_GEMINI_KEY argument is missing.")
        return # Or raise an error
    # Init bot
    bot = AsyncTeleBot(options.tg_token, parse_mode='HTML')
    await bot.delete_my_commands(scope=None, language_code=None)
    await bot.set_my_commands(
    commands=[
        telebot.types.BotCommand("start", "Start"),
        telebot.types.BotCommand("gemini", f"using {conf['model_1']}"),
        telebot.types.BotCommand("gemini_pro", f"using {conf['model_2']}"),
        telebot.types.BotCommand("draw", "draw picture"),
        telebot.types.BotCommand("edit", "edit photo"),
        telebot.types.BotCommand("clear", "Clear all history"),
        telebot.types.BotCommand("switch","switch default model")
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
    bot.register_message_handler(handlers.gemini_photo_handler,          content_types=["photo"],    pass_bot=True)
    bot.register_message_handler(
        handlers.gemini_private_handler,
        func=lambda message: message.chat.type == "private",
        content_types=['text'],
        pass_bot=True)

    # Register callback query handlers
    bot.register_callback_query_handler(handlers.regenerate_callback_handler, 
                                        func=lambda call: call.data.startswith("regenerate:"), 
                                        pass_bot=True)
    bot.register_callback_query_handler(handlers.continue_callback_handler, 
                                        func=lambda call: call.data.startswith("continue:"), 
                                        pass_bot=True)

    # Initialize the settings database
    await ensure_db_initialized()
    print("Settings database initialized.")

    # Start bot
    print("Starting Gemini_Telegram_Bot.")
    await bot.polling(none_stop=True)

if __name__ == '__main__':
    asyncio.run(main())
