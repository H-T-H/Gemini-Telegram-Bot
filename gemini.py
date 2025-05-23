"""
Handles interactions with the Google Gemini API for text generation, image editing, and drawing.
"""
import io
import time
import traceback
import sys
from PIL import Image
from telebot.types import Message
from md2tgmd import escape
from telebot import TeleBot
from config import conf, generation_config
from google import genai

gemini_draw_dict = {}
gemini_chat_dict = {}
gemini_pro_chat_dict = {}
default_model_dict = {}

search_tool = {'google_search': {}}

client = genai.Client(api_key=sys.argv[2])

async def gemini_stream(bot:TeleBot, message:Message, m:str, model_type:str):
    """
    Streams responses from the Gemini model for a given text prompt,
    progressively editing the reply message.

    Parameters:
        bot (TeleBot): The TeleBot instance.
        message (Message): The incoming Telegram message object.
        m (str): The user's text prompt.
        model_type (str): The specific Gemini model to use.
    """
    sent_message = None
    try:
        sent_message = await bot.reply_to(message, "🤖 Generating answers...")

        chat = None
        if model_type == conf["model_1"]:
            chat_dict = gemini_chat_dict
        else:
            chat_dict = gemini_pro_chat_dict

        if str(message.from_user.id) not in chat_dict:
            chat = client.aio.chats.create(model=model_type, config={'tools': [search_tool]})
            chat_dict[str(message.from_user.id)] = chat
        else:
            chat = chat_dict[str(message.from_user.id)]

        response = await chat.send_message_stream(m)

        full_response = ""
        last_update = time.time()
        update_interval = conf["streaming_update_interval"]

        async for chunk in response:
            if hasattr(chunk, 'text') and chunk.text:
                full_response += chunk.text
                current_time = time.time()

                if current_time - last_update >= update_interval:

                    try:
                        await bot.edit_message_text(
                            escape(full_response),
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="MarkdownV2"
                            )
                    except Exception as e:
                        if "parse markdown" in str(e).lower():
                            await bot.edit_message_text(
                                full_response,
                                chat_id=sent_message.chat.id,
                                message_id=sent_message.message_id
                                )
                        else:
                            if "message is not modified" not in str(e).lower():
                                print(f"Error updating message: {e}")
                    last_update = current_time

        try:
            await bot.edit_message_text(
                escape(full_response),
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            try:
                if "parse markdown" in str(e).lower():
                    await bot.edit_message_text(
                        full_response,
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id
                    )
            except Exception:
                traceback.print_exc()


    except Exception as e:
        traceback.print_exc()
        if sent_message:
            await bot.edit_message_text(
                f"{conf['error_info']}\nError details: {str(e)}",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
        else:
            await bot.reply_to(message, f"{conf['error_info']}\nError details: {str(e)}")

async def gemini_edit(bot: TeleBot, message: Message, m: str, photo_file: bytes):
    """
    Sends a prompt and an image to the Gemini model for vision-based tasks
    (e.g., describing or editing an image).

    Parameters:
        bot (TeleBot): The TeleBot instance.
        message (Message): The incoming Telegram message object.
        m (str): The text prompt.
        photo_file (bytes): Bytes of the photo.
    """
    image = Image.open(io.BytesIO(photo_file))
    try:
        response = await client.aio.models.generate_content(
        model=conf["model_3"],
        contents=[m, image],
        config=generation_config
    )
    except Exception as e:
        await bot.send_message(message.chat.id, e.str())
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            await bot.send_message(message.chat.id, escape(part.text), parse_mode="MarkdownV2")
        elif part.inline_data is not None:
            photo = part.inline_data.data
            await bot.send_photo(message.chat.id, photo)

async def gemini_draw(bot:TeleBot, message:Message, m:str):
    """
    Generates an image based on the user's text prompt using the Gemini model.

    Parameters:
        bot (TeleBot): The TeleBot instance.
        message (Message): The incoming Telegram message object.
        m (str): The text prompt for drawing.
    """
    chat_dict = gemini_draw_dict
    # Retrieve or create a chat session for the user for drawing tasks
    if str(message.from_user.id) not in chat_dict:
        chat = client.aio.chats.create(
            model=conf["model_3"], # Uses the designated drawing model
            config=generation_config,
        )
        chat_dict[str(message.from_user.id)] = chat
    else:
        chat = chat_dict[str(message.from_user.id)]

    response = await chat.send_message(m)
    # Process the response parts, sending text or image data
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            text = part.text
            # Split long text messages if they exceed Telegram's limit
            while len(text) > 4000:
                await bot.send_message(message.chat.id, escape(text[:4000]), parse_mode="MarkdownV2")
                text = text[4000:]
            if text: # Send remaining part of the text
                await bot.send_message(message.chat.id, escape(text), parse_mode="MarkdownV2")
        elif part.inline_data is not None: # If the part contains image data
            photo = part.inline_data.data
            await bot.send_photo(message.chat.id, photo)
