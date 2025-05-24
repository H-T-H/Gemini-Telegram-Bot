"""
Handles interactions with the Google Gemini API for text generation, image editing, and drawing.
"""
import io
import time
import traceback
# import sys # Removed as client initialization is removed
from PIL import Image
from telebot.types import Message
from md2tgmd import escape
from telebot import TeleBot
from config import conf, NEW_SAFETY_SETTINGS # Added NEW_SAFETY_SETTINGS
from google.generativeai import types as genai_types
from core.ai_client import get_model
from core.limits import general_limiter
# from google import genai # Removed as client initialization is removed

# gemini_draw_dict = {} # Removed
# default_model_dict = {} # Removed as it's now handled by core.database

search_tool = {'google_search': {}} # This might be used by stream_text if that service evolves

# client = genai.Client(api_key=sys.argv[2]) # Removed

async def gemini_edit(bot: TeleBot, message: Message, text_prompt: str, image_bytes: bytes):
    """
    Handles vision-based tasks (e.g., describing or editing an image) using Gemini.
    It sends a text prompt and an image to the Gemini 'image' model.
    The model's response can be text and/or an image.

    Parameters:
        bot (TeleBot): The TeleBot instance.
        message (Message): The incoming Telegram message object.
        text_prompt (str): The text prompt.
        image_bytes (bytes): Raw bytes of the photo.
    """
    try:
        img_model = get_model(kind="image") # Uses the new client via get_model
        pil_image = Image.open(io.BytesIO(image_bytes))

        # The old generation_config from config.py is not directly compatible.
        # Safety settings will be added in Step 5.
        # model=conf["model_3"] is now handled by get_model(kind="image")

        request_options = genai_types.RequestOptions(timeout=90) # 90s timeout
        response = await img_model.generate_content_async(
            contents=[text_prompt, pil_image],
            request_options=request_options,
            safety_settings=NEW_SAFETY_SETTINGS # Added safety_settings
        )

        # Process response parts
        if not response.parts:
            async with general_limiter:
                await bot.reply_to(message, "The model did not provide a response for the image and prompt.", parse_mode="MarkdownV2")
            return

        for part in response.parts:
            if part.text:
                async with general_limiter:
                    await bot.send_message(message.chat.id, escape(part.text), parse_mode="MarkdownV2")
            elif part.blob and part.blob.mime_type.startswith("image/"):
                photo_data = part.blob.data
                async with general_limiter:
                    await bot.send_photo(message.chat.id, photo_data)
            # Note: The old code checked part.inline_data.data.
            # The new SDK typically uses part.blob for binary data.

    except Exception as e:
        traceback.print_exc()
        async with general_limiter:
            # Use reply_to for better context if possible
            await bot.reply_to(message, f"{conf['error_info']}\nError details: {str(e)}", parse_mode="MarkdownV2")

async def gemini_draw(bot:TeleBot, message:Message, m:str):
    """
    Generates an image based on the user's text prompt using the Gemini 'image' model.

    Parameters:
        bot (TeleBot): The TeleBot instance.
        message (Message): The incoming Telegram message object.
        text_prompt (str): The text prompt for drawing.
    """
    try:
        img_model = get_model(kind="image")

        request_options = genai_types.RequestOptions(timeout=180) # 180s timeout for image generation
        response = await img_model.generate_content_async(
            contents=[m], # Changed text_prompt to m to match existing variable name
            request_options=request_options,
            safety_settings=NEW_SAFETY_SETTINGS # Added safety_settings
        )

        image_generated = False
        text_response_sent = False

        if not response.parts:
            async with general_limiter:
                await bot.reply_to(message, "The model did not return any content for your drawing request.", parse_mode="MarkdownV2")
            return

        for part in response.parts:
            if part.blob and part.blob.mime_type.startswith("image/"):
                photo_data = part.blob.data
                async with general_limiter:
                    # Reply to the original message for context
                    await bot.send_photo(message.chat.id, photo_data, reply_to_message_id=message.message_id)
                image_generated = True
                break # Typically send one image for a draw command
            elif part.text: # Handle potential text part, e.g. refusal or comment
                async with general_limiter:
                    await bot.send_message(message.chat.id, escape(part.text), parse_mode="MarkdownV2", reply_to_message_id=message.message_id)
                text_response_sent = True
        
        if not image_generated and not text_response_sent:
            # If no image and no specific text part explaining why
            async with general_limiter:
                await bot.reply_to(message, "Sorry, I couldn't generate an image or get a specific text response for your drawing request.", parse_mode="MarkdownV2")

    except Exception as e:
        traceback.print_exc()
        async with general_limiter:
            await bot.reply_to(message, f"{conf['error_info']}\nError details: {str(e)}", parse_mode="MarkdownV2")
