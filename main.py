import argparse
import traceback
import asyncio
import google.generativeai as genai
import re
import telebot
from telebot.async_telebot import AsyncTeleBot
from pathlib import Path
from telebot import TeleBot
from telebot.types import BotCommand, Message


generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 8192,
}

safety_settings = []

def find_all_index(str, pattern):
    index_list = [0]
    for match in re.finditer(pattern, str, re.MULTILINE):
        if match.group(1) != None:
            start = match.start(1)
            end = match.end(1)
            index_list += [start, end]
    index_list.append(len(str))
    return index_list


def replace_all(text, pattern, function):
    poslist = [0]
    strlist = []
    originstr = []
    poslist = find_all_index(text, pattern)
    for i in range(1, len(poslist[:-1]), 2):
        start, end = poslist[i : i + 2]
        strlist.append(function(text[start:end]))
    for i in range(0, len(poslist), 2):
        j, k = poslist[i : i + 2]
        originstr.append(text[j:k])
    if len(strlist) < len(originstr):
        strlist.append("")
    else:
        originstr.append("")
    new_list = [item for pair in zip(originstr, strlist) for item in pair]
    return "".join(new_list)

def escapeshape(text):
    return "▎*" + text.split()[1] + "*"


def escapeminus(text):
    return "\\" + text


def escapebackquote(text):
    return r"\`\`"


def escapeplus(text):
    return "\\" + text

def escape(text, flag=0):
    # In all other places characters
    # _ * [ ] ( ) ~ ` > # + - = | { } . !
    # must be escaped with the preceding character '\'.
    text = re.sub(r"\\\[", "@->@", text)
    text = re.sub(r"\\\]", "@<-@", text)
    text = re.sub(r"\\\(", "@-->@", text)
    text = re.sub(r"\\\)", "@<--@", text)
    if flag:
        text = re.sub(r"\\\\", "@@@", text)
    text = re.sub(r"\\", r"\\\\", text)
    if flag:
        text = re.sub(r"\@{3}", r"\\\\", text)
    text = re.sub(r"_", "\_", text)
    text = re.sub(r"\*{2}(.*?)\*{2}", "@@@\\1@@@", text)
    text = re.sub(r"\n{1,2}\*\s", "\n\n• ", text)
    text = re.sub(r"\*", "\*", text)
    text = re.sub(r"\@{3}(.*?)\@{3}", "*\\1*", text)
    text = re.sub(r"\!?\[(.*?)\]\((.*?)\)", "@@@\\1@@@^^^\\2^^^", text)
    text = re.sub(r"\[", "\[", text)
    text = re.sub(r"\]", "\]", text)
    text = re.sub(r"\(", "\(", text)
    text = re.sub(r"\)", "\)", text)
    text = re.sub(r"\@\-\>\@", "\[", text)
    text = re.sub(r"\@\<\-\@", "\]", text)
    text = re.sub(r"\@\-\-\>\@", "\(", text)
    text = re.sub(r"\@\<\-\-\@", "\)", text)
    text = re.sub(r"\@{3}(.*?)\@{3}\^{3}(.*?)\^{3}", "[\\1](\\2)", text)
    text = re.sub(r"~", "\~", text)
    text = re.sub(r">", "\>", text)
    text = replace_all(text, r"(^#+\s.+?$)|```[\D\d\s]+?```", escapeshape)
    text = re.sub(r"#", "\#", text)
    text = replace_all(
        text, r"(\+)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeplus
    )
    text = re.sub(r"\n{1,2}(\s*)-\s", "\n\n\\1• ", text)
    text = re.sub(r"\n{1,2}(\s*\d{1,2}\.\s)", "\n\n\\1", text)
    text = replace_all(
        text, r"(-)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeminus
    )
    text = re.sub(r"```([\D\d\s]+?)```", "@@@\\1@@@", text)
    text = replace_all(text, r"(``)", escapebackquote)
    text = re.sub(r"\@{3}([\D\d\s]+?)\@{3}", "```\\1```", text)
    text = re.sub(r"=", "\=", text)
    text = re.sub(r"\|", "\|", text)
    text = re.sub(r"{", "\{", text)
    text = re.sub(r"}", "\}", text)
    text = re.sub(r"\.", "\.", text)
    text = re.sub(r"!", "\!", text)
    return text

async def make_new_gemini_convo():
    model = genai.GenerativeModel(
        model_name="gemini-pro",
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    convo = model.start_chat()
    return convo

async def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="telegram token")
    parser.add_argument("GOOGLE_GEMINI_KEY", help="Google Gemini API key")
    options = parser.parse_args()
    print("Arg parse done.")
    gemini_player_dict = {}

    genai.configure(api_key=options.GOOGLE_GEMINI_KEY)

    # Init bot
    bot = AsyncTeleBot(options.tg_token)
    await bot.delete_my_commands(scope=None, language_code=None)
    await bot.set_my_commands(
        commands=[
            telebot.types.BotCommand("gemini", "call bot in a group"),
            telebot.types.BotCommand("clear", "delete history")
        ],
    )
    print("Bot init done.")

    # Init commands
    @bot.message_handler(commands=["gemini"])
    async def gemini_handler(message: Message):
        try:
            m = message.text.strip().split(maxsplit=1)[1].strip()
        except IndexError:
            await bot.reply_to( message , escape("Please type /gemini followed by what you want to say.For example:\n`/gemini Hello!`"), parse_mode="MarkdownV2")
            return
        player = None
        # restart will lose all TODO
        if str(message.from_user.id) not in gemini_player_dict:
            player = await make_new_gemini_convo()
            gemini_player_dict[str(message.from_user.id)] = player
        else:
            player = gemini_player_dict[str(message.from_user.id)]
        if len(player.history) > 10:
            player.history = player.history[2:]
        try:
            player.send_message(m)
            try:
                await bot.reply_to( message , escape(player.last.text) , parse_mode="MarkdownV2",)
            except:
                await bot.reply_to(message, escape(player.last.text))

        except Exception as e:
            traceback.print_exc()
            await bot.reply_to(message, "Something wrong, possibly due to security, please try changing your prompt or contact admin")

    @bot.message_handler(commands=["clear"])
    async def gemini_handler(message: Message):
        # Check if the player is already in gemini_player_dict.
        if str(message.from_user.id) in gemini_player_dict:
            del gemini_player_dict[str(message.from_user.id)]
            await bot.reply_to(message, "Your history has been cleared")
        else:
            await bot.reply_to(message, "your history is empty already")
    
    @bot.message_handler(func=lambda message: message.chat.type == "private", content_types=['text'])
    async def gemini_private_handler(message: Message):
        m = message.text.strip()
        player = None 
        # Check if the player is already in gemini_player_dict.
        if str(message.from_user.id) not in gemini_player_dict:
            player = await make_new_gemini_convo()
            gemini_player_dict[str(message.from_user.id)] = player
        else:
            player = gemini_player_dict[str(message.from_user.id)]
        # Control the length of the history record.
        if len(player.history) > 10:
            player.history = player.history[2:]
        try:
            player.send_message(m)
            try:
                await bot.reply_to(message, escape(player.last.text), parse_mode="MarkdownV2")
            except:
                await bot.reply_to(message, escape(player.last.text))

        except Exception as e:
            traceback.print_exc()
            await bot.reply_to(message, "Something wrong, possibly due to security, please try changing your prompt or contact admin")
            
    @bot.message_handler(content_types=["photo"])
    async def gemini_photo_handler(message: Message) -> None:
        if message.chat.type != "private":
            s = message.caption
            if not s or not (s.startswith("/gemini")):
                return
            try:
                prompt = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else "no prompt"
                file_path = await bot.get_file(message.photo[-1].file_id)
                downloaded_file = await bot.download_file(file_path.file_path)
                with open("gemini_temp.jpg", "wb") as temp_file:
                    temp_file.write(downloaded_file)
            except Exception as e:
                traceback.print_exc()
                await bot.reply_to(message, "Something is wrong reading your photo or prompt")
            model = genai.GenerativeModel("gemini-pro-vision")
            image_path = Path("gemini_temp.jpg")
            image_data = image_path.read_bytes()
            contents = {
                "parts": [{"mime_type": "image/jpeg", "data": image_data}, {"text": prompt}]
            }
            try:
                response = model.generate_content(contents=contents)
                await bot.reply_to(message, response.text)
            except Exception as e:
                traceback.print_exc()
                await bot.reply_to(message, "Something wrong, possibly due to security, please try changing your prompt or contact admin")
        else:
            s = message.caption if message.caption else "no prompt"
            try:
                prompt = s.strip()
                file_path = await bot.get_file(message.photo[-1].file_id)
                downloaded_file = await bot.download_file(file_path.file_path)
                with open("gemini_temp.jpg", "wb") as temp_file:
                    temp_file.write(downloaded_file)
            except Exception as e:
                traceback.print_exc()
                await bot.reply_to(message, "Something is wrong reading your photo or prompt")
            model = genai.GenerativeModel("gemini-pro-vision")
            image_path = Path("gemini_temp.jpg")
            image_data = image_path.read_bytes()
            contents = {
                "parts": [{"mime_type": "image/jpeg", "data": image_data}, {"text": prompt}]
            }
            try:
                response = model.generate_content(contents=contents)
                await bot.reply_to(message, response.text)
            except Exception as e:
                traceback.print_exc()
                await bot.reply_to(message, "Something wrong, possibly due to security, please try changing your prompt or contact admin")
                
    # Start bot
    print("Starting Gemini_Telegram_Bot.")
    await bot.polling()


if __name__ == '__main__':
    asyncio.run(main())
