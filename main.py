import argparse
import traceback
import asyncio
import re
import telebot
from telebot.async_telebot import AsyncTeleBot
from google import genai
import os # Import os for environment variable access

# 添加更详细的异常处理
try:
    print("Trying to import handlers...")
    import handlers
    print("Successfully imported handlers.")
except Exception as e:
    print(f"Error importing handlers: {e}")
    print("Traceback:")
    traceback.print_exc()
    raise

from config import conf, generation_config, safety_settings, command_descriptions

# Init args
parser = argparse.ArgumentParser()
parser.add_argument("tg_token", help="telegram token")
parser.add_argument("GOOGLE_GEMINI_KEY", help="Google Gemini API key")
options = parser.parse_args()
print("Arg parse done.")

async def main():
    # Initialize the Google GenAI Client
    api_key_to_use = os.getenv("GOOGLE_API_KEY")
    client_init_method = "environment variable GOOGLE_API_KEY"

    if not api_key_to_use:
        print(f"GOOGLE_API_KEY environment variable not set. Falling back to command line argument.")
        api_key_to_use = options.GOOGLE_GEMINI_KEY
        client_init_method = "command line argument GOOGLE_GEMINI_KEY"
        if not api_key_to_use:
            print("FATAL: API key not found in GOOGLE_API_KEY environment variable or command line argument.")
            print("Please set the GOOGLE_API_KEY environment variable or provide the key as a command line argument.")
            return

    client = None # Define client here to ensure it's in scope for finally block or further use
    try:
        client = genai.Client(api_key=api_key_to_use)
        print(f"Google GenAI Client initialized successfully using API key from {client_init_method}.")
        
        # Set the client for the gemini module (via handlers)
        # Ensure handlers and handlers.gemini are loaded before this call
        if hasattr(handlers, 'gemini') and handlers.gemini:
            handlers.gemini.set_gemini_client(client)
        else:
            print("CRITICAL ERROR: handlers.gemini module not available. Cannot set Gemini client.")
            print("Make sure 'import gemini' is present in handlers.py and gemini.py exists.")
            return # Critical error, cannot proceed
            
    except Exception as e:
        print(f"FATAL: Failed to initialize Google GenAI Client or set it in gemini.py: {e}")
        traceback.print_exc()
        return

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
        telebot.types.BotCommand("language", command_descriptions[lang]["language"]),
        telebot.types.BotCommand("set_system_prompt", command_descriptions[lang]["set_system_prompt"]),
        telebot.types.BotCommand("view_system_prompt", command_descriptions[lang]["view_system_prompt"]),
        telebot.types.BotCommand("delete_system_prompt", command_descriptions[lang]["delete_system_prompt"])
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
    bot.register_message_handler(handlers.set_system_prompt_handler,     commands=['set_system_prompt'], pass_bot=True)
    bot.register_message_handler(handlers.view_system_prompt_handler,    commands=['view_system_prompt'], pass_bot=True)
    bot.register_message_handler(handlers.delete_system_prompt_handler,  commands=['delete_system_prompt'], pass_bot=True)
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
