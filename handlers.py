"""
Defines handlers for Telegram bot commands and messages,
routing them to appropriate Gemini API interactions.
"""
from telebot import TeleBot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton # Added InlineKeyboard imports
from core.utils import escape_html # Replaced md2tgmd with escape_html
import traceback
import time # Add this for last_update logic
from config import conf
import gemini
from core.limits import general_limiter, streaming_limiter # Ensure streaming_limiter is imported
from services.stream import stream_text, safe_generate_stream # Added safe_generate_stream
from core.database import get_default_model, set_default_model, decrement_quota, get_chat_history, add_chat_message, clear_chat_history # Added clear_chat_history

# gemini_chat_dict        = gemini.gemini_chat_dict # Obsolete, will be removed if not already
# gemini_pro_chat_dict    = gemini.gemini_pro_chat_dict # Obsolete, will be removed if not already
# default_model_dict      = gemini.default_model_dict # Removed
gemini_draw_dict        = gemini.gemini_draw_dict # Still used by gemini.py for now

async def start(message: Message, bot: TeleBot) -> None:
    """Handles the /start command and sends a welcome message."""
    welcome_text = "Welcome, you can ask me questions now. <br>For example: <code>/gemini Who is john lennon?</code>"
    try:
        async with general_limiter:
            await bot.reply_to(message, welcome_text, parse_mode="HTML")
    except IndexError: # Should not happen with a static message
        async with general_limiter:
            await bot.reply_to(message, conf["error_info"], parse_mode="HTML") # Assuming conf["error_info"] is HTML or plain

async def gemini_stream_handler(message: Message, bot: TeleBot) -> None:
    """Handles the /gemini command for streaming text responses using the 'flash' model."""
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        reply_text = "Please add what you want to say after <code>/gemini</code>. <br>For example: <code>/gemini Who is john lennon?</code>"
        async with general_limiter:
            await bot.reply_to(message, reply_text, parse_mode="HTML")
        return

    user_id = message.from_user.id
    if not await decrement_quota(user_id):
        reply_text = "You have run out of quota. Please contact the administrator for assistance."
        async with general_limiter:
            await bot.reply_to(message, reply_text, parse_mode="HTML")
        return

    session_id = str(user_id)
    user_history = await get_chat_history(session_id)

    sent_message = None
    full_response = ""
    try:
        async with general_limiter:
            await bot.send_chat_action(message.chat.id, 'typing')
        async with general_limiter:
            sent_message = await bot.reply_to(message, conf["before_generate_info"], parse_mode="MarkdownV2")

        last_update = time.time()
        update_interval = conf["streaming_update_interval"]

        async for text_chunk in stream_text(kind="flash", prompt=m, history=user_history):
            full_response += text_chunk
            current_time = time.time()
            if sent_message and current_time - last_update >= update_interval:
                async with streaming_limiter:
                    try:
                        # Add indicator, escape the main response
                        await bot.edit_message_text(
                            escape_html(full_response) + " ..." , # Use escape_html
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="HTML" # Ensure parse_mode is HTML
                        )
                    except Exception as e_edit:
                        if "message is not modified" not in str(e_edit).lower():
                            print(f"Error editing message during stream: {e_edit}") # Log error
                last_update = current_time
        
        await add_chat_message(session_id, 'user', m)
        if full_response: # Save model response if it's not empty
            await add_chat_message(session_id, 'model', full_response)

        
        await add_chat_message(session_id, 'user', m)
        if full_response: # Save model response if it's not empty
            await add_chat_message(session_id, 'model', full_response)

        if sent_message: # Final update after stream ends
            action_kb = create_action_keyboard(session_id, sent_message.message_id)
            async with general_limiter:
                await bot.edit_message_text(
                    escape_html(full_response), # Use escape_html
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id,
                    parse_mode="HTML", # Ensure parse_mode is HTML
                    reply_markup=action_kb
                )
    except Exception as e:
        traceback.print_exc()
        await add_chat_message(session_id, 'user', m) # Still save user message on error
        if full_response: # Save partial model response if any
            await add_chat_message(session_id, 'model', full_response)
        
        error_message_to_user = f"{conf['error_info']}<br>Error details: {escape_html(str(e))}" # Use <br> and escape_html
        if sent_message and full_response: # If error after some streaming
             async with general_limiter:
                # Try to append error to what was streamed so far
                await bot.edit_message_text(escape_html(full_response) + f"<br><br>⚠️ Error: {escape_html(str(e))}", chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="HTML")
        elif sent_message: # If error before any streaming, or stream_text failed early
            async with general_limiter:
                await bot.edit_message_text(error_message_to_user, chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="HTML")
        else: # If initial reply failed
            async with general_limiter:
                await bot.reply_to(message, error_message_to_user, parse_mode="HTML")

async def gemini_pro_stream_handler(message: Message, bot: TeleBot) -> None:
    """Handles the /gemini_pro command for streaming text responses using the 'pro' model."""
    try:
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        reply_text = "Please add what you want to say after <code>/gemini_pro</code>. <br>For example: <code>/gemini_pro Who is john lennon?</code>"
        async with general_limiter:
            await bot.reply_to(message, reply_text, parse_mode="HTML")
        return

    user_id = message.from_user.id
    if not await decrement_quota(user_id):
        reply_text = "You have run out of quota. Please contact the administrator for assistance."
        async with general_limiter:
            await bot.reply_to(message, reply_text, parse_mode="HTML")
        return
        
    session_id = str(user_id)
    user_history = await get_chat_history(session_id)

    sent_message = None
    full_response = ""
    try:
        async with general_limiter:
            await bot.send_chat_action(message.chat.id, 'typing')
        async with general_limiter:
            sent_message = await bot.reply_to(message, conf["before_generate_info"], parse_mode="MarkdownV2")

        last_update = time.time()
        update_interval = conf["streaming_update_interval"]

        async for text_chunk in safe_generate_stream(prompt=m, history=user_history): # Changed to safe_generate_stream
            full_response += text_chunk
            current_time = time.time()
            if sent_message and current_time - last_update >= update_interval:
                async with streaming_limiter:
                    try:
                        # Add indicator, escape the main response
                        await bot.edit_message_text(
                            escape_html(full_response) + " ...", # Use escape_html
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="HTML" # Ensure parse_mode is HTML
                        )
                    except Exception as e_edit:
                        if "message is not modified" not in str(e_edit).lower():
                            print(f"Error editing message during stream: {e_edit}") # Log error
                last_update = current_time
        
        await add_chat_message(session_id, 'user', m)
        if full_response: # Save model response if it's not empty
            await add_chat_message(session_id, 'model', full_response)

        
        await add_chat_message(session_id, 'user', m)
        if full_response: # Save model response if it's not empty
            await add_chat_message(session_id, 'model', full_response)

        if sent_message: # Final update after stream ends
            action_kb = create_action_keyboard(session_id, sent_message.message_id)
            async with general_limiter:
                await bot.edit_message_text(
                    escape_html(full_response), # Use escape_html
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id,
                    parse_mode="HTML", # Ensure parse_mode is HTML
                    reply_markup=action_kb
                )
    except Exception as e:
        traceback.print_exc()
        await add_chat_message(session_id, 'user', m) # Still save user message on error
        if full_response: # Save partial model response if any
            await add_chat_message(session_id, 'model', full_response)

        error_message_to_user = f"{conf['error_info']}<br>Error details: {escape_html(str(e))}" # Use <br> and escape_html
        if sent_message and full_response: # If error after some streaming
             async with general_limiter:
                # Try to append error to what was streamed so far
                await bot.edit_message_text(escape_html(full_response) + f"<br><br>⚠️ Error: {escape_html(str(e))}", chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="HTML")
        elif sent_message: # If error before any streaming, or stream_text failed early
            async with general_limiter:
                await bot.edit_message_text(error_message_to_user, chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="HTML")
        else: # If initial reply failed
            async with general_limiter:
                await bot.reply_to(message, error_message_to_user, parse_mode="HTML")

async def clear(message: Message, bot: TeleBot) -> None:
    """Handles the /clear command to erase the user's chat history with the bot."""
    user_id_str = str(message.from_user.id)

    # Clear text-based chat history from the database
    await clear_chat_history(user_id_str)

    # Keep clearing gemini_draw_dict for now, as it's separate
    # and still used in gemini.py (though should ideally be refactored later)
    if user_id_str in gemini_draw_dict:
        del gemini_draw_dict[user_id_str]
        print(f"Cleared gemini_draw_dict for user {user_id_str}") # Optional: for server log
    
    # Remove from old in-memory dicts if they are still somehow present
    # These should be fully obsolete now.
    if user_id_str in gemini_chat_dict:
        del gemini_chat_dict[user_id_str]
        print(f"Cleared obsolete gemini_chat_dict for user {user_id_str}")
    if user_id_str in gemini_pro_chat_dict:
        del gemini_pro_chat_dict[user_id_str]
        print(f"Cleared obsolete gemini_pro_chat_dict for user {user_id_str}")

    async with general_limiter: # Ensure general_limiter is available
        await bot.reply_to(message, "Your chat history has been cleared.", parse_mode="HTML")

async def switch(message: Message, bot: TeleBot) -> None:
    """Handles the /switch command to toggle the user's default model between 'flash' and 'pro'."""
    if message.chat.type != "private":
        async with general_limiter: # Ensure general_limiter is used
            await bot.reply_to(message, "This command is only for private chat!", parse_mode="HTML")
        return
    
    user_id = message.from_user.id
    # get_default_model ensures the user is in DB, defaulting to 'flash' if new
    current_model_kind = await get_default_model(user_id) 

    new_model_kind = ""
    if current_model_kind == "flash":
        new_model_kind = "pro"
    else: # Was 'pro', or some unexpected value (e.g. if DB was manually changed), so default to 'flash'
        new_model_kind = "flash"
        
    await set_default_model(user_id, new_model_kind)
    
    reply_model_name_key = "model_1" if new_model_kind == "flash" else "model_2"
    # Get the actual model name string from conf for the reply message
    # conf["model_1"] should be flash's full name, conf["model_2"] should be pro's full name.
    # These are defined in config.py and used by core.ai_client._MODELS (indirectly via handlers).
    # For user display, it might be better to use the _MODELS keys directly or map them.
    # Let's use the kind 'flash' or 'pro' for clarity in the message for now.
    # Or, better, use the full model name from `conf` as previously.
    
    display_model_name = conf.get(reply_model_name_key, new_model_kind) # Fallback to kind if key not in conf

    async with general_limiter: # Ensure general_limiter is used
        await bot.reply_to(message, f"Now your default model is: <code>{escape_html(display_model_name)}</code>", parse_mode="HTML")

async def gemini_private_handler(message: Message, bot: TeleBot) -> None:
    """Handles direct text messages in private chats, using the user's selected default model."""
    m = message.text.strip()
    user_id = message.from_user.id

    if not await decrement_quota(user_id):
        reply_text = "You have run out of quota. Please contact the administrator for assistance."
        async with general_limiter:
            await bot.reply_to(message, reply_text, parse_mode="HTML")
        return
    
    session_id = str(user_id)
    user_history = await get_chat_history(session_id)
    # Get the user's default model kind ('flash' or 'pro') from the database.
    # This also ensures the user is created with default settings if they don't exist.
    model_kind_to_use = await get_default_model(user_id)
    
    # The stream_text function is now in services.stream, not gemini.gemini_stream
    # This was refactored in Step 3.4 Part A.
    # Replicating the streaming logic from gemini_stream_handler here:
    sent_message = None
    full_response = ""
    try:
        async with general_limiter:
            await bot.send_chat_action(message.chat.id, 'typing')
        async with general_limiter:
            sent_message = await bot.reply_to(message, conf["before_generate_info"], parse_mode="MarkdownV2")

        last_update = time.time()
        # Ensure 'time' is imported in handlers.py (it was for previous step)
        # Ensure 'conf', 'escape', 'general_limiter', 'streaming_limiter' are available
        # Ensure 'stream_text' from 'services.stream' is imported
        update_interval = conf["streaming_update_interval"]

        async for text_chunk in stream_text(kind=model_kind_to_use, prompt=m, history=user_history):
            full_response += text_chunk
            current_time = time.time()
            if sent_message and current_time - last_update >= update_interval:
                async with streaming_limiter:
                    try:
                        await bot.edit_message_text(
                            escape_html(full_response) + " ...", # Use escape_html
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="HTML" # Ensure parse_mode is HTML
                        )
                    except Exception as e_edit:
                        if "message is not modified" not in str(e_edit).lower():
                            print(f"Error editing message during private stream: {e_edit}")
                last_update = current_time
        
        await add_chat_message(session_id, 'user', m)
        if full_response: # Save model response if it's not empty
            await add_chat_message(session_id, 'model', full_response)

        
        await add_chat_message(session_id, 'user', m)
        if full_response: # Save model response if it's not empty
            await add_chat_message(session_id, 'model', full_response)

        if sent_message: # Final update
            action_kb = create_action_keyboard(session_id, sent_message.message_id)
            async with general_limiter:
                await bot.edit_message_text(
                    escape_html(full_response), # Use escape_html
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id,
                    parse_mode="HTML", # Ensure parse_mode is HTML
                    reply_markup=action_kb
                )
    except Exception as e:
        traceback.print_exc()
        await add_chat_message(session_id, 'user', m) # Still save user message on error
        if full_response: # Save partial model response if any
            await add_chat_message(session_id, 'model', full_response)

        error_message_to_user = f"{conf['error_info']}<br>Error details: {escape_html(str(e))}" # Use <br> and escape_html
        if sent_message and full_response:
             async with general_limiter:
                await bot.edit_message_text(escape_html(full_response) + f"<br><br>⚠️ Error: {escape_html(str(e))}", chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="HTML")
        elif sent_message:
            async with general_limiter:
                await bot.edit_message_text(error_message_to_user, chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="HTML")
        else:
            async with general_limiter:
                await bot.reply_to(message, error_message_to_user, parse_mode="HTML")

async def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    if message.chat.type != "private":
        s = message.caption or ""
        # In group chats, only respond if the caption starts with /gemini
        if not s or not (s.startswith("/gemini")):
            return

        user_id = message.from_user.id
        if not await decrement_quota(user_id):
            reply_text = "You have run out of quota. Please contact the administrator for assistance."
            async with general_limiter:
                await bot.reply_to(message, reply_text, parse_mode="HTML")
            return
        
        async with general_limiter:
            await bot.send_chat_action(message.chat.id, 'typing')
            
        try:
            m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            async with general_limiter:
                await bot.reply_to(message, conf["error_info"], parse_mode="HTML") # Assuming conf["error_info"] is HTML or plain
            return
        await gemini.gemini_edit(bot, message, m, photo_file)
    else: # Private chat
        s = message.caption or ""
        
        user_id = message.from_user.id
        if not await decrement_quota(user_id):
            reply_text = "You have run out of quota. Please contact the administrator for assistance."
            async with general_limiter:
                await bot.reply_to(message, reply_text, parse_mode="HTML")
            return

        async with general_limiter:
            await bot.send_chat_action(message.chat.id, 'typing')

        try:
            # Extract prompt from caption, if any
            m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
            file_path = await bot.get_file(message.photo[-1].file_id)
            photo_file = await bot.download_file(file_path.file_path)
        except Exception:
            traceback.print_exc()
            async with general_limiter:
                await bot.reply_to(message, conf["error_info"], parse_mode="HTML") # Assuming conf["error_info"] is HTML or plain
            return
        await gemini.gemini_edit(bot, message, m, photo_file)

async def gemini_edit_handler(message: Message, bot: TeleBot) -> None:
    """Handles the /edit command for editing an image with a prompt."""
    if not message.photo:
        async with general_limiter:
            await bot.reply_to(message, "pls send a photo", parse_mode="HTML") # Assuming this is plain or already HTML
        return

    user_id = message.from_user.id
    if not await decrement_quota(user_id):
        reply_text = "You have run out of quota. Please contact the administrator for assistance."
        async with general_limiter:
            await bot.reply_to(message, reply_text, parse_mode="HTML")
        return
    
    async with general_limiter:
        await bot.send_chat_action(message.chat.id, 'typing')
        
    s = message.caption or ""
    try:
        # Extract prompt from caption, if any
        m = s.strip().split(maxsplit=1)[1].strip() if len(s.strip().split(maxsplit=1)) > 1 else ""
        file_path = await bot.get_file(message.photo[-1].file_id)
        photo_file = await bot.download_file(file_path.file_path)
    except Exception as e:
        traceback.print_exc()
        async with general_limiter:
            await bot.reply_to(message, escape_html(str(e)), parse_mode="HTML") # Escape error
        return
    await gemini.gemini_edit(bot, message, m, photo_file)

async def draw_handler(message: Message, bot: TeleBot) -> None:
    """Handles the /draw command to generate an image based on a text prompt."""
    try:
        # Extract the prompt text after the command
        m = message.text.strip().split(maxsplit=1)[1].strip()
    except IndexError:
        reply_text = "Please add what you want to draw after <code>/draw</code>. <br>For example: <code>/draw draw me a cat.</code>"
        async with general_limiter:
            await bot.reply_to(message, reply_text, parse_mode="HTML")
        return
    
    user_id = message.from_user.id
    if not await decrement_quota(user_id):
        reply_text = "You have run out of quota. Please contact the administrator for assistance."
        async with general_limiter:
            await bot.reply_to(message, reply_text, parse_mode="HTML")
        return
    
    async with general_limiter:
        await bot.send_chat_action(message.chat.id, 'typing')
        
    # Reply with a "Drawing..." message, which will be deleted after the image is sent
    async with general_limiter:
        drawing_msg = await bot.reply_to(message, "Drawing...", parse_mode="HTML") # Assuming plain or already HTML
    try:
        await gemini.gemini_draw(bot, message, m)
    finally:
        async with general_limiter:
            await bot.delete_message(chat_id=message.chat.id, message_id=drawing_msg.message_id)

# --- Helper function to create action keyboard ---
def create_action_keyboard(session_id: str, message_id: int | None = None) -> InlineKeyboardMarkup:
    # message_id could be used if actions are specific to a message context
    keyboard = InlineKeyboardMarkup()
    # Using session_id in callback_data to potentially retrieve context
    # Format: action:session_id(:optional_message_id)
    regenerate_data = f"regenerate:{session_id}"
    continue_data = f"continue:{session_id}"
    
    if message_id: # If we want to tie actions to a specific message
            regenerate_data += f":{message_id}"
            continue_data += f":{message_id}"

    keyboard.row(
        InlineKeyboardButton("🔄 Regenerate", callback_data=regenerate_data),
        InlineKeyboardButton("➡️ Continue", callback_data=continue_data)
    )
    # Later, an "Explain" button can be added here.
    return keyboard

# --- Placeholder Callback Query Handlers ---
async def regenerate_callback_handler(call: TeleBot.types.CallbackQuery, bot: TeleBot): # Adjusted type hint
    """Handles the 'Regenerate' button callback."""
    # call.data will be "regenerate:session_id" or "regenerate:session_id:message_id"
    parts = call.data.split(':')
    session_id = parts[1]
    # message_id_str = parts[2] if len(parts) > 2 else None

    async with general_limiter:
        await bot.answer_callback_query(call.id, text="Regenerating response... (Not implemented yet)")
    # Placeholder: actual regeneration logic will involve fetching history, last user prompt,
    # and re-triggering generation. Might need to resend the "Generating answers..." message.
    print(f"Regenerate called for session: {session_id}")

async def continue_callback_handler(call: TeleBot.types.CallbackQuery, bot: TeleBot): # Adjusted type hint
    """Handles the 'Continue' button callback."""
    parts = call.data.split(':')
    session_id = parts[1]
    # message_id_str = parts[2] if len(parts) > 2 else None

    async with general_limiter:
        await bot.answer_callback_query(call.id, text="Continuing conversation... (Not implemented yet)")
    # Placeholder: actual continuation logic will involve fetching history,
    # potentially asking user for more input or using a "continue" prompt.
    print(f"Continue called for session: {session_id}")
