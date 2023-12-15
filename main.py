import argparse
import subprocess
import traceback
from pathlib import Path

import numpy as np
import PIL
from PIL import Image
from telebot import TeleBot  # type: ignore
from telebot.types import BotCommand, Message  # type: ignore
import google.generativeai as genai



generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE",
    },
]


def make_new_gemini_convo():
    model = genai.GenerativeModel(
        model_name="gemini-pro",
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    convo = model.start_chat()
    return convo

def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="telegram token")
    parser.add_argument("GOOGLE_GEMINI_KEY", help="Google Gemini API key")
    options = parser.parse_args()
    print("Arg parse done.")
    gemini_player_dict = {}

    genai.configure(api_key=options.GOOGLE_GEMINI_KEY)

    # Init bot
    bot = TeleBot(options.tg_token)
    bot.set_my_commands(
        [
            BotCommand("gemini", "Gemini : /gemini <你的问题>"),
        ]
    )
    print("Bot init done.")

    @bot.message_handler(commands=["gemini"])
    def gemini_handler(message: Message):
        m = message.text.strip().split(maxsplit=1)[1].strip()
        player = None
        # restart will lose all TODO
        if str(message.from_user.id) not in gemini_player_dict:
            player = make_new_gemini_convo()
            gemini_player_dict[str(message.from_user.id)] = player
        else:
            player = gemini_player_dict[str(message.from_user.id)]
        if len(player.history) > 10:
            player.history = player.history[2:]
        try:
            player.send_message(m)
            try:
                bot.reply_to(
                    message,
                    player.last.text,
                    parse_mode="MarkdownV2",
                )
            except:
                bot.reply_to(message, player.last.text)

        except Exception as e:
            traceback.print_exc()
            bot.reply_to(message, "Something wrong please check the log")

    @bot.message_handler(content_types=["photo"])
    def gemini_photo_handler(message: Message) -> None:
        s = message.caption
        if not s or not (s.startswith("/gemini")):
            return
        try:
            prompt = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""

            max_size_photo = max(message.photo, key=lambda p: p.file_size)
            file_path = bot.get_file(max_size_photo.file_id).file_path
            downloaded_file = bot.download_file(file_path)
            with open("gemini_temp.jpg", "wb") as temp_file:
                temp_file.write(downloaded_file)
        except Exception as e:
            traceback.print_exc()
            bot.reply_to(message, "Something is wrong reading your photo or prompt")
        model = genai.GenerativeModel("gemini-pro-vision")
        image_path = Path("gemini_temp.jpg")
        image_data = image_path.read_bytes()
        contents = {
            "parts": [{"mime_type": "image/jpeg", "data": image_data}, {"text": prompt}]
        }
        try:
            response = model.generate_content(contents=contents)
            bot.reply_to(message, response.text)
        except Exception as e:
            traceback.print_exc()
            bot.reply_to(message, "Something wrong please check the log")

    # Start bot
    print("Starting tg collections bot.")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
