import io
import time
import traceback
import sys
import os # Added for os.remove
from PIL import Image
from telebot.types import Message
from md2tgmd import escape
from telebot import TeleBot
from config import conf, generation_config, messages, safety_settings # Ensure safety_settings is imported
import google.generativeai as genai # Use alias for consistency

# --- System Prompt Management ---
SYSTEM_PROMPT_FILE = "system_prompt.txt"
current_system_prompt = None

def load_system_prompt():
    """Loads the system prompt from SYSTEM_PROMPT_FILE into current_system_prompt."""
    global current_system_prompt
    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            prompt_content = f.read().strip()
            if prompt_content:
                current_system_prompt = prompt_content
            else:
                current_system_prompt = None # Handle empty file as no prompt
    except FileNotFoundError:
        current_system_prompt = None
    print(f"System prompt loaded: {current_system_prompt}")

def save_system_prompt(text: str | None):
    """Saves the system prompt to file, updates current_system_prompt, and clears chat dicts."""
    global current_system_prompt
    
    # Clear all chat histories because system prompt change invalidates them
    gemini_chat_dict.clear()
    gemini_pro_chat_dict.clear()
    gemini_draw_dict.clear() # Assuming draw chat also uses system prompt

    if text and text.strip():
        with open(SYSTEM_PROMPT_FILE, "w", encoding="utf-8") as f:
            f.write(text.strip())
        current_system_prompt = text.strip()
    else: # Delete prompt if text is None or empty
        try:
            os.remove(SYSTEM_PROMPT_FILE)
        except FileNotFoundError:
            pass # Already removed or never existed
        current_system_prompt = None
    print(f"System prompt saved: {current_system_prompt}")

# Load system prompt when module is imported
load_system_prompt()
# --- End System Prompt Management ---

gemini_draw_dict = {}
gemini_chat_dict = {}
gemini_pro_chat_dict = {}
default_model_dict = {}
language_dict = {}  # 用户语言偏好字典

model_1 = conf["model_1"]
model_2 = conf["model_2"]
default_language = conf["default_language"]

search_tool = {'google_search': {}} # Assuming this is correctly defined or None if not used

# IMPORTANT: genai.configure(api_key=YOUR_API_KEY) must be called in your main entry point (e.g., main.py)
# Remove old client: client = genai.Client(api_key=sys.argv[2])

# 获取用户语言
def get_user_language(user_id):
    user_id_str = str(user_id)
    if user_id_str not in language_dict:
        language_dict[user_id_str] = default_language
    return language_dict[user_id_str]

# 获取用户消息
def get_message(message_key, user_id):
    lang = get_user_language(user_id)
    return messages[lang][message_key]

async def gemini_stream(bot:TeleBot, message:Message, m:str, model_type:str):
    user_id = message.from_user.id
    sent_message = None
    try:
        sent_message = await bot.reply_to(message, get_message("generating_answers", user_id))

        chat_session_dict = gemini_chat_dict if model_type == model_1 else gemini_pro_chat_dict
        
        if str(user_id) not in chat_session_dict:
            print(f"Creating new chat for {user_id} with system prompt: {current_system_prompt}")
            # Determine tools based on model_type
            tools_for_model = [search_tool] if model_type == model_1 and search_tool else None

            model_instance = genai.GenerativeModel(
                model_name=model_type,
                system_instruction=current_system_prompt,
                generation_config=generation_config,
                safety_settings=safety_settings,
                tools=tools_for_model
            )
            chat = model_instance.start_chat(history=[]) # Start with empty history
            chat_session_dict[str(user_id)] = chat
        else:
            chat = chat_session_dict[str(user_id)]

        # Use send_message_async for streaming
        response_stream = await chat.send_message_async(m, stream=True)

        full_response = ""
        last_update = time.time()
        update_interval = conf["streaming_update_interval"]

        async for chunk in response_stream:
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
                        elif "message is not modified" not in str(e).lower():
                            print(f"Error updating message: {e}")
                    last_update = current_time
        
        # Final update for the full response
        try:
            await bot.edit_message_text(
                escape(full_response) if full_response else "No content generated.", # Handle empty full_response
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            if "parse markdown" in str(e).lower():
                 await bot.edit_message_text(
                    full_response if full_response else "No content generated.",
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id
                )
            elif "message is not modified" not in str(e).lower():
                 traceback.print_exc()


    except Exception as e:
        traceback.print_exc()
        error_msg_key = 'error_info'
        error_details_key = 'error_details'
        # Attempt to get localized error messages
        try:
            error_message_text = f"{get_message(error_msg_key, user_id)}\n{get_message(error_details_key, user_id)}{str(e)}"
        except Exception: # Fallback if get_message fails (e.g., during init)
             error_message_text = f"An error occurred: {str(e)}"

        if sent_message:
            await bot.edit_message_text(
                error_message_text,
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
        else:
            await bot.reply_to(message, error_message_text)

async def gemini_edit(bot: TeleBot, message: Message, m: str, photo_file: bytes):
    user_id = message.from_user.id
    pil_image = Image.open(io.BytesIO(photo_file))
    try:
        print(f"Using system prompt for edit: {current_system_prompt}")
        model_instance = genai.GenerativeModel(
            model_name=model_2, # Uses model_2 as per previous fix
            system_instruction=current_system_prompt,
            generation_config=generation_config, # From config.py
            safety_settings=safety_settings      # From config.py
        )
        
        contents_payload = []
        if m and m.strip():
            contents_payload.append(m)
        contents_payload.append(pil_image)

        response = await model_instance.generate_content_async(contents=contents_payload)
        
        # Process response parts
        # Ensure response.candidates exists and is not empty
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    await bot.send_message(message.chat.id, escape(part.text), parse_mode="MarkdownV2")
                # elif part.inline_data is not None: # This model config only supports text output
                #     photo = part.inline_data.data
                #     await bot.send_photo(message.chat.id, photo)
        else:
            await bot.send_message(message.chat.id, "No response content generated.")

    except Exception as e:
        traceback.print_exc()
        error_msg_key = 'error_info'
        # Attempt to get localized error messages
        try:
            error_message_text = f"{get_message(error_msg_key, user_id)}: {str(e)}"
        except Exception: # Fallback if get_message fails
             error_message_text = f"Error in gemini_edit: {str(e)}"
        await bot.send_message(message.chat.id, error_message_text)


async def gemini_draw(bot:TeleBot, message:Message, m:str):
    user_id = message.from_user.id
    sent_message = None # To hold the "Drawing..." message
    try:
        # It seems like gemini_draw was intended to be a chat for model_1
        # Let's keep a separate dict for it if its behavior is different or uses a different model by default
        chat_session_dict = gemini_draw_dict 
        
        # Reply with "Drawing..." or similar before making the API call
        sent_message = await bot.reply_to(message, get_message("drawing", user_id))

        if str(user_id) not in chat_session_dict:
            print(f"Creating new draw chat for {user_id} with system prompt: {current_system_prompt}")
            model_instance = genai.GenerativeModel(
                model_name=model_1, # gemini_draw traditionally used model_1
                system_instruction=current_system_prompt,
                generation_config=generation_config, # Use global config
                safety_settings=safety_settings
            )
            chat = model_instance.start_chat(history=[])
            chat_session_dict[str(user_id)] = chat
        else:
            chat = chat_session_dict[str(user_id)]

        response = await chat.send_message_async(m) # Non-streaming for draw

        # Process response parts
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text is not None:
                    text_to_send = part.text
                    # Split long messages if necessary (Telegram limit is 4096)
                    while len(text_to_send) > 4000:
                        await bot.send_message(message.chat.id, escape(text_to_send[:4000]), parse_mode="MarkdownV2")
                        text_to_send = text_to_send[4000:]
                    if text_to_send: # Send remaining part or the whole message if short
                        await bot.send_message(message.chat.id, escape(text_to_send), parse_mode="MarkdownV2")
                # elif part.inline_data is not None: # Assuming draw is text-to-image if model_1 supports it & config allows
                #     photo = part.inline_data.data
                #     await bot.send_photo(message.chat.id, photo)
        else:
             await bot.send_message(message.chat.id, "No content generated by draw.")
        
        # Delete the "Drawing..." message if it was sent
        if sent_message:
            await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    except Exception as e:
        traceback.print_exc()
        # Fallback error message
        error_message_text = f"Error in gemini_draw: {str(e)}"
        try: # Try to get localized message
            error_message_text = f"{get_message('error_info', user_id)}\n{get_message('error_details', user_id)}{str(e)}"
        except Exception:
            pass
        
        # If "Drawing..." message was sent and error occurs, edit it. Otherwise, send a new message.
        if sent_message:
            await bot.edit_message_text(error_message_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        else:
            await bot.reply_to(message, error_message_text)
