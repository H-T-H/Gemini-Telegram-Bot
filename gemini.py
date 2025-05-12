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

model_1                 =       conf["model_1"]
model_2                 =       conf["model_2"]
model_3                 =       conf["model_3"]
error_info              =       conf["error_info"]
before_generate_info    =       conf["before_generate_info"]
download_pic_notify     =       conf["download_pic_notify"]

search_tool = {'google_search': {}}

client = genai.Client(api_key=sys.argv[2])

async def gemini_stream(bot:TeleBot, message:Message, m:str, model_type:str):
    sent_message = None
    try:
        sent_message = await bot.reply_to(message, "🤖 Generating answers...")

        chat = None
        if model_type == model_1:
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
                f"{error_info}\nError details: {str(e)}",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
        else:
            await bot.reply_to(message, f"{error_info}\nError details: {str(e)}")

async def gemini_edit(bot: TeleBot, message: Message, m: str, photo_file: bytes):

    image = Image.open(io.BytesIO(photo_file))
    try:
        response = await client.aio.models.generate_content(
        model=model_3,
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

async def gemini_image_understand(bot: TeleBot, message: Message, photo_file: bytes, prompt: str = ""):
    sent_message = None
    try:
        sent_message = await bot.reply_to(message, "🤖 Understanding image...")
        image = Image.open(io.BytesIO(photo_file))
        
        # Determine the model based on user's default setting
        current_model = model_1 # Default to model_1
        if str(message.from_user.id) in default_model_dict and not default_model_dict[str(message.from_user.id)]:
            current_model = model_2

        contents = [image]
        if prompt:
            contents.append(prompt)

        response = await client.aio.models.generate_content(
            model=current_model, 
            contents=contents,
            config=generation_config,
            # Ensure that the stream parameter is not used here if not supported for image and text combined
        )
        
        # Assuming the response for image understanding is primarily text
        # and located in response.text or similar attribute based on Gemini API for image inputs
        
        text_response = ""
        # Iterate through parts if the response structure is like multi-modal,
        # otherwise, directly access .text if available and appropriate.
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    text_response += part.text
        elif hasattr(response, 'text'): # Fallback for simpler text response
             text_response = response.text

        if text_response:
            await bot.edit_message_text(
                escape(text_response),
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id,
                parse_mode="MarkdownV2"
            )
        else:
            await bot.edit_message_text(
                "🤖 Couldn't understand the image or no text response found.",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )

    except Exception as e:
        traceback.print_exc()
        error_message = f"{error_info}\\nError details: {str(e)}"
        if sent_message:
            await bot.edit_message_text(
                error_message,
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
        else:
            await bot.reply_to(message, error_message)

async def gemini_draw(bot:TeleBot, message:Message, m:str):
    chat_dict = gemini_draw_dict
    if str(message.from_user.id) not in chat_dict:
        chat = client.aio.chats.create(
            model=model_3,
            config=generation_config,
        )
        chat_dict[str(message.from_user.id)] = chat
    else:
        chat = chat_dict[str(message.from_user.id)]

    response = await chat.send_message(m)
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            text = part.text
            while len(text) > 4000:
                await bot.send_message(message.chat.id, escape(text[:4000]), parse_mode="MarkdownV2")
                text = text[4000:]
            if text:
                await bot.send_message(message.chat.id, escape(text), parse_mode="MarkdownV2")
        elif part.inline_data is not None:
            photo = part.inline_data.data
            await bot.send_photo(message.chat.id, photo)
