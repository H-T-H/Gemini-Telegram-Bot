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
    current_model_name_for_error_msg = "configured model" # Placeholder
    try:
        # Determine the model and chat dictionary based on user's default setting
        current_model_name = model_1 # Default to model_1
        chat_dict_to_use = gemini_chat_dict
        if str(message.from_user.id) in default_model_dict and not default_model_dict[str(message.from_user.id)]:
            current_model_name = model_2
            chat_dict_to_use = gemini_pro_chat_dict
        current_model_name_for_error_msg = current_model_name

        sent_message = await bot.reply_to(message, f"🤖 Understanding image with {current_model_name}...")
        
        image_pil = Image.open(io.BytesIO(photo_file))
        
        # Prepare contents: a list containing the PIL Image object and the prompt string.
        current_contents = [image_pil]
        if prompt:
            current_contents.append(prompt)
        else:
            # If no specific prompt, provide a generic one to guide the model for image understanding.
            current_contents.append("Describe this image.")
        
        # Get or create chat session for the selected model
        chat_session = None
        if str(message.from_user.id) not in chat_dict_to_use:
            # Using generation_config here, assuming it's compatible. 
            # The `tools` config might be problematic for direct image input in a chat context.
            # If issues persist, this chat creation part for image tasks might need to be model-specific without tools,
            # or use client.aio.models.generate_content directly if chat session is the issue.
            chat_session = client.aio.chats.create(model=current_model_name, config=generation_config) 
            # chat_session = client.aio.chats.create(model=current_model_name, config={'tools': [search_tool]}) # Original from text stream
            chat_dict_to_use[str(message.from_user.id)] = chat_session
        else:
            chat_session = chat_dict_to_use[str(message.from_user.id)]
        
        # Send message to chat session. send_message_stream should handle multimodal contents.
        response_stream = await chat_session.send_message_stream(contents=current_contents)
        
        full_response_text = ""
        last_update_time = time.time()
        update_interval = conf.get("streaming_update_interval", 1.0) # Default to 1 second

        async for chunk in response_stream:
            if hasattr(chunk, 'text') and chunk.text:
                full_response_text += chunk.text
                current_time = time.time()
                if current_time - last_update_time >= update_interval:
                    try:
                        await bot.edit_message_text(
                            escape(full_response_text + "..."), # Indicate streaming
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="MarkdownV2"
                        )
                        last_update_time = current_time
                    except Exception as e_stream:
                        if "message is not modified" not in str(e_stream).lower() and "parse markdown" not in str(e_stream).lower():
                            print(f"Streaming update error for image understanding: {e_stream}")
                        elif "parse markdown" in str(e_stream).lower(): # Attempt to send raw if markdown fails
                             await bot.edit_message_text(full_response_text + "...", chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                             last_update_time = current_time


        # Final update for the completed response
        if full_response_text:
            try:
                await bot.edit_message_text(
                    escape(full_response_text),
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id,
                    parse_mode="MarkdownV2"
                )
            except Exception: # Fallback to raw text if markdown fails
                await bot.edit_message_text(full_response_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        else:
            await bot.edit_message_text(
                f"🤖 Model {current_model_name} did not provide a text response for the image.",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )

    except genai.types.BlockedPromptException as bpe:
        traceback.print_exc()
        error_msg = f"🤖 My response was blocked when processing the image. (Details: {str(bpe)})"
        if sent_message:
            await bot.edit_message_text(error_msg, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        else:
            await bot.reply_to(message, error_msg)
    except Exception as e:
        traceback.print_exc()
        error_detail_str = str(e)
        specific_error_check = "This model only supports text output." in error_detail_str and "INVALID_ARGUMENT" in error_detail_str.upper()
        
        error_message = f"{error_info}\\\nError details: {error_detail_str}"
        if specific_error_check:
            error_message = (
                f"{error_info}\\\n" \
                f"API Error: {error_detail_str}\\\n" \
                f"This error suggests that the model \'{current_model_name_for_error_msg}\' (as configured in your config.py) " \
                f"might not support direct image input, or the input format is incorrect for this model type. " \
                f"Please ensure \'{model_1}\' and \'{model_2}\' in config.py are multimodal models capable of image input (e.g., \'gemini-1.5-flash-latest\')."\
            )
        
        if sent_message:
            await bot.edit_message_text(error_message, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
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
