from config import conf, generation_config, safety_settings
import asyncio
import google.generativeai as genai
import traceback
from md2tgmd import escape
gemini_player_dict = {}
gemini_pro_player_dict = {}
default_model_dict = {}

n = conf["n"]
model_1                 =       conf["model_1"]
model_2                 =       conf["model_2"]
error_info              =       conf["error_info"]
before_generate_info    =       conf["before_generate_info"]
download_pic_notify     =       conf["download_pic_notify"]

async def make_new_gemini_convo(model_name):
    loop = asyncio.get_running_loop()

    def create_convo():
        model = genai.GenerativeModel(
            model_name          =   model_name,
            generation_config   =   generation_config,
            safety_settings     =   safety_settings,
        )
        convo = model.start_chat()
        return convo

    # Run the synchronous "create_convo" function in a thread pool
    convo = await loop.run_in_executor(None, create_convo)
    return convo

async def send_message(player, message):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, player.send_message, message)
    
async def async_generate_content(model, contents):
    loop = asyncio.get_running_loop()

    def generate():
        return model.generate_content(contents=contents)

    response_stream = await loop.run_in_executor(None, generate)
    return response_stream

async def async_generate_content_stream(model, contents):
    loop = asyncio.get_running_loop()

    def generate_stream():
        return model.generate_content(contents=contents, stream=True)

    response_stream = await loop.run_in_executor(None, generate_stream)
    return response_stream

async def gemini(bot, message, m, model_type):
    player = None
    if      model_type == model_1:   
        player_dict = gemini_player_dict 
    else:   player_dict = gemini_pro_player_dict
    if str(message.from_user.id) not in player_dict:
        player = await make_new_gemini_convo(model_type)
        player_dict[str(message.from_user.id)] = player
    else:
        player = player_dict[str(message.from_user.id)]
    if len(player.history) > n:
        player.history = player.history[2:]
    try:
        sent_message = await bot.reply_to(message, before_generate_info)
        await send_message(player, m)
        try:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="MarkdownV2")
        except:
            await bot.edit_message_text(escape(player.last.text), chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    except Exception:
        traceback.print_exc()
        await bot.edit_message_text(error_info, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        
async def gemini_stream(bot, message, m, model_type):
    sent_message = None
    try:
        model = genai.GenerativeModel(
            model_name=model_type,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        sent_message = await bot.reply_to(message, "🔄 Generating answers...")

        player = None
        if model_type == model_1:   
            player_dict = gemini_player_dict 
        else:
            player_dict = gemini_pro_player_dict
            
        if str(message.from_user.id) not in player_dict:
            player = await make_new_gemini_convo(model_type)
            player_dict[str(message.from_user.id)] = player
        else:
            player = player_dict[str(message.from_user.id)]
            
        if len(player.history) > n:
            player.history = player.history[2:]
        
        response = model.generate_content(m, stream=True)
        
        full_response = ""
        last_update = asyncio.get_event_loop().time()
        update_interval = conf["streaming_update_interval"]
        
        print("Start streaming answers")

        edit_lock = asyncio.Lock()

        for chunk in response:
            if hasattr(chunk, 'text') and chunk.text:
                full_response += chunk.text
                current_time = asyncio.get_event_loop().time()

                if current_time - last_update >= update_interval:

                    async with edit_lock:
                        try:
                            print(f"Update message, length: {len(full_response)}")

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
                        except Exception as e:
                            print(f"Streaming update error (non-fatal): {e}")

        try:
            print("Send final full response")
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
            
        player.history.append({"role": "user", "parts": [m]})
        player.history.append({"role": "model", "parts": [full_response]})
                
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
