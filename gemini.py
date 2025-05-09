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
from google import genai
from google.genai import types
from typing import Optional

# Module-level client instance and setter for the new SDK
gemini_client = None

def set_gemini_client(client_instance):
    """Sets the global genai.Client instance for this module."""
    global gemini_client
    gemini_client = client_instance
    if gemini_client:
        print("Gemini client instance set successfully in gemini.py")
    else:
        # This could be problematic if not intentional
        print("Warning: Attempted to set a None client in gemini.py (gemini_client is None)")

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

def save_system_prompt(text: Optional[str]):
    """Saves the system prompt to file, updates current_system_prompt, and clears chat dicts."""
    global current_system_prompt
    
    # Clear all chat histories because system prompt change invalidates them
    gemini_chat_dict.clear()
    gemini_pro_chat_dict.clear()
    # 移除不再使用的字典引用
    # gemini_draw_dict.clear() 

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

# 移除不再使用的字典
# gemini_draw_dict = {}
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
        if not gemini_client:
            error_text = "CRITICAL ERROR: Gemini client not initialized in gemini.py. Please check main.py setup."
            print(error_text)
            await bot.reply_to(message, error_text)
            return

        sent_message = await bot.reply_to(message, get_message("generating_answers", user_id))

        chat_session_dict = gemini_chat_dict if model_type == model_1 else gemini_pro_chat_dict
        user_id_str = str(user_id)

        # Prepare the configuration for the send_message_stream call
        # This config will include system_instruction, safety_settings, and generation_config parameters
        pydantic_config_params = {}
        if current_system_prompt:
            pydantic_config_params['system_instruction'] = current_system_prompt

        if safety_settings: # Global safety_settings from config.py
            try:
                # Ensure safety_settings are converted to list of types.SafetySetting if they are dicts
                formatted_safety_settings = []
                for ss_item in safety_settings:
                    if isinstance(ss_item, dict):
                        formatted_safety_settings.append(types.SafetySetting(**ss_item))
                    elif isinstance(ss_item, types.SafetySetting):
                        formatted_safety_settings.append(ss_item)
                    # else: ignore or log warning for unexpected type
                if formatted_safety_settings:
                    pydantic_config_params['safety_settings'] = formatted_safety_settings
            except Exception as e_ss_format:
                print(f"Warning: Could not format safety_settings: {e_ss_format}. Safety settings may not be applied.")

        # Merge global generation_config (from config.py, currently an empty dict)
        if generation_config: # This is the global one from config.py
            pydantic_config_params.update(generation_config) # example: temperature, max_output_tokens etc.
        
        gen_config_for_api = None
        if pydantic_config_params: # Only create if there are params
            try:
                gen_config_for_api = types.GenerateContentConfig(**pydantic_config_params)
            except Exception as e_conf_create:
                print(f"Error creating GenerateContentConfig from params: {pydantic_config_params}. Error: {e_conf_create}")
                # Fallback: send without this specific GenerateContentConfig if creation fails
                # Alternatively, could construct a default/empty one or re-raise

        chat_session = None
        if user_id_str not in chat_session_dict:
            print(f"Creating new chat for {user_id_str} with model {model_type}.")
            # For the new SDK, system_instruction is part of GenerateContentConfig passed to send_message.
            # History can be passed here if needed for new chats.
            try:
                chat_session = gemini_client.aio.chats.create(model=model_type, history=[]) # history can be prepopulated if needed
                chat_session_dict[user_id_str] = chat_session
            except Exception as e_create_chat:
                print(f"Error creating chat session for {user_id_str} with model {model_type}: {e_create_chat}")
                await bot.edit_message_text(f"Error creating chat session: {e_create_chat}", chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                return
        else:
            chat_session = chat_session_dict[user_id_str]

        # Send message using the new SDK's chat session
        try:
            print(f"Sending message with config: {gen_config_for_api}")
            response_stream = await chat_session.send_message_stream(message=m, config=gen_config_for_api)
            
            full_response = ""
            last_update = time.time()
            update_interval = conf.get("streaming_update_interval", 0.5)

            async for chunk in response_stream:
                if hasattr(chunk, 'text') and chunk.text:
                    full_response += chunk.text
                    current_time = time.time()
                    if current_time - last_update >= update_interval:
                        try:
                            await bot.edit_message_text(
                                escape(full_response), # Ensure md2tgmd escape is still relevant
                                chat_id=sent_message.chat.id,
                                message_id=sent_message.message_id,
                                parse_mode="MarkdownV2"
                            )
                        except Exception as e_edit:
                            if "message is not modified" not in str(e_edit).lower():
                                # Attempt to send without MarkdownV2 if parsing fails
                                try:
                                    await bot.edit_message_text(
                                        full_response,
                                        chat_id=sent_message.chat.id,
                                        message_id=sent_message.message_id
                                    )
                                except Exception as e_edit_plain:
                                    print(f"Error updating message (plain): {e_edit_plain}")
                            # else: ignore "message not modified"
                        last_update = current_time
            
            # Final update for the message
            final_text_to_send = escape(full_response) if full_response else "No content generated."
            try:
                await bot.edit_message_text(
                    final_text_to_send,
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id,
                    parse_mode="MarkdownV2"
                )
            except Exception as e_final_md:
                if "parse markdown" in str(e_final_md).lower() or "message is not modified" not in str(e_final_md).lower():
                    await bot.edit_message_text(
                        full_response if full_response else "No content generated.",
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id
                    )
                else:
                    print(f"Error on final edit (MarkdownV2): {e_final_md}") # Log other errors
        
        except types.BlockedPromptException as bpe: # Specific error for new SDK from docs (may be errors.APIError or sub-class)
            print(f"Prompt blocked for user {user_id_str}: {bpe}")
            await bot.edit_message_text(f"Your request was blocked by safety settings. Details: {bpe.args[0] if bpe.args else 'Blocked'}", chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        except genai.types.StopCandidateException as sce: # if generation stops due to model instruction
            print(f"Generation stopped by model for user {user_id_str}: {sce}")
            await bot.edit_message_text(f"Content generation stopped as instructed. {sce.args[0] if sce.args else ''}", chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        except Exception as e_send:
            print(f"Error sending message or processing stream for user {user_id_str}: {e_send}")
            traceback.print_exc()
            await bot.edit_message_text(f"Error processing your request: {e_send}", chat_id=sent_message.chat.id, message_id=sent_message.message_id)

    except Exception as e_outer:
        traceback.print_exc()
        error_msg_key = 'error_info'
        error_details_key = 'error_details'
        try:
            error_message_text = f"{get_message(error_msg_key, user_id)}\n{get_message(error_details_key, user_id)}{str(e_outer)}"
        except Exception: 
             error_message_text = f"An unexpected error occurred: {str(e_outer)}"

        if sent_message:
            try:
                await bot.edit_message_text(error_message_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception as e_final_error_edit:
                print(f"Failed to edit message with final error: {e_final_error_edit}")
        else:
            try:
                await bot.reply_to(message, error_message_text)
            except Exception as e_final_error_reply:
                 print(f"Failed to send final error reply: {e_final_error_reply}")

async def gemini_edit(bot: TeleBot, message: Message, m: str, photo_file: bytes):
    user_id = message.from_user.id
    pil_image = Image.open(io.BytesIO(photo_file))
    sent_message = None
    
    try:
        sent_message = await bot.reply_to(message, get_message("generating_answers", user_id))
        print(f"Using system prompt for edit: {current_system_prompt}")
        
        # 尝试创建模型实例，并处理各种库版本差异
        try:
            # 构建一个带有系统提示的模型配置
            model_config = {
                "model_name": model_2,
                "generation_config": generation_config
            }
            
            # 如果有系统提示，添加它
            if current_system_prompt:
                model_config["system_instruction"] = current_system_prompt
            
            # 如果有安全设置，添加它
            if safety_settings:
                model_config["safety_settings"] = safety_settings
            
            # 尝试创建模型
            model = genai.GenerativeModel(**model_config)
            
            # 准备内容
            contents = []
            if m and m.strip():
                contents.append(m)
            contents.append(pil_image)
            
            # 尝试生成内容
            try:
                if hasattr(model, "generate_content_async"):
                    response = await model.generate_content_async(contents=contents)
                else:
                    # 如果不支持异步API，使用同步API
                    response = model.generate_content(contents=contents)
                
                # 提取文本
                text_response = ""
                if hasattr(response, "text"):
                    text_response = response.text
                elif hasattr(response, "parts") and len(response.parts) > 0:
                    for part in response.parts:
                        if hasattr(part, "text") and part.text:
                            text_response += part.text
                
                # 回复
                if text_response:
                    try:
                        await bot.edit_message_text(
                            escape(text_response),
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="MarkdownV2"
                        )
                    except Exception as md_err:
                        if "parse markdown" in str(md_err).lower():
                            await bot.edit_message_text(
                                text_response,
                                chat_id=sent_message.chat.id,
                                message_id=sent_message.message_id
                            )
                        else:
                            raise md_err
                else:
                    await bot.edit_message_text(
                        "No text response generated.",
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id
                    )
            except Exception as gen_err:
                print(f"Error generating content: {gen_err}")
                await bot.edit_message_text(
                    f"Error generating content: {str(gen_err)}",
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id
                )
        except Exception as model_err:
            print(f"Error creating model: {model_err}")
            await bot.edit_message_text(
                f"Error creating model: {str(model_err)}",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
    except Exception as e:
        traceback.print_exc()
        error_msg_key = 'error_info'
        # Attempt to get localized error messages
        try:
            error_message_text = f"{get_message(error_msg_key, user_id)}: {str(e)}"
        except Exception: # Fallback if get_message fails
             error_message_text = f"Error in gemini_edit: {str(e)}"
        
        if sent_message:
            await bot.edit_message_text(
                error_message_text,
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
        else:
            await bot.send_message(message.chat.id, error_message_text)

async def gemini_draw(bot:TeleBot, message:Message, m:str):
    user_id = message.from_user.id
    sent_message = None # To hold the "Drawing..." message
    try:
        sent_message = await bot.reply_to(message, get_message("drawing", user_id))
        
        # 获取配置的模型名称，如果未配置 model_3，则提供一个备用值或抛出错误
        # 这里我们假设 model_3 总是配置好的，因为用户刚刚添加了它
        draw_model_name = conf.get("model_3", "gemini-2.0-flash-exp") # 使用 model_3

        # 尝试创建模型实例
        try:
            model_config_params = {
                "model_name": draw_model_name,
                # generation_config 全局的可能为空，或者不包含 mime_type
            }
            
            # 如果有全局 safety_settings，添加它
            if safety_settings:
                model_config_params["safety_settings"] = safety_settings
            
            # 如果有系统提示，添加它 (虽然对于绘图可能不常用)
            if current_system_prompt:
                model_config_params["system_instruction"] = current_system_prompt
            
            model = genai.GenerativeModel(**model_config_params)
            
            # 准备生成图像的特定配置
            image_generation_config = genai.types.GenerationConfig(
                response_mime_type="image/png"
            )

            # 尝试生成内容
            try:
                # 确保内容是列表形式，即使只有一个文本提示
                contents_for_draw = [m]

                if hasattr(model, "generate_content_async"):
                    response = await model.generate_content_async(
                        contents=contents_for_draw,
                        generation_config=image_generation_config # 指定输出为图像
                    )
                else:
                    # 同步回退 (虽然对于bot通常希望异步)
                    response = model.generate_content(
                        contents=contents_for_draw,
                        generation_config=image_generation_config # 指定输出为图像
                    )
                
                # 处理图像响应
                if response.parts and response.parts[0].inline_data and response.parts[0].inline_data.mime_type == "image/png":
                    image_data = response.parts[0].inline_data.data
                    if sent_message: # 删除 "Drawing..." 消息
                        await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                        sent_message = None
                    await bot.send_photo(message.chat.id, photo=image_data, caption=f"🖼️: {m}")
                else:
                    # 如果没有有效的图像部分，则报告错误或意外的响应
                    no_image_message = "Failed to generate image or unexpected response format."
                    if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                        no_image_message += f" Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"
                    elif response.parts and response.parts[0].text: # 可能是模型返回了文本错误
                         no_image_message += f" Model said: {response.parts[0].text}"
                    
                    if sent_message:
                        await bot.edit_message_text(
                            no_image_message,
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id
                        )
                    else:
                        await bot.reply_to(message, no_image_message)

            except Exception as gen_err:
                print(f"Error generating image content: {gen_err}")
                error_text = f"Error generating image: {str(gen_err)}"
                if hasattr(gen_err, 'args') and len(gen_err.args) > 0 and isinstance(gen_err.args[0], str) and "Deadline Exceeded" in gen_err.args[0]:
                    error_text = "Image generation timed out. Please try a simpler prompt or try again later."

                if sent_message:
                    await bot.edit_message_text(
                        error_text,
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id
                    )
                else:
                    await bot.reply_to(message, error_text)
        
        except Exception as model_err:
            print(f"Error creating draw model: {model_err}")
            if sent_message:
                await bot.edit_message_text(
                    f"Error creating draw model: {str(model_err)}",
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id
                )
            else:
                await bot.reply_to(message, f"Error creating draw model: {str(model_err)}")

    except Exception as e:
        traceback.print_exc()
        error_msg_key = 'error_info'
        error_details_key = 'error_details'
        try:
            error_message_text = f"{get_message(error_msg_key, user_id)}\\n{get_message(error_details_key, user_id)}{str(e)}"
        except Exception:
             error_message_text = f"An error occurred in draw: {str(e)}"

        if sent_message:
            await bot.edit_message_text(
                error_message_text,
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
        else:
            await bot.reply_to(message, error_message_text)
