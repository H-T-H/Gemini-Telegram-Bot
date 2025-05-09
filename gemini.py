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
from typing import Optional

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
        sent_message = await bot.reply_to(message, get_message("generating_answers", user_id))

        chat_session_dict = gemini_chat_dict if model_type == model_1 else gemini_pro_chat_dict
        
        if str(user_id) not in chat_session_dict:
            print(f"Creating new chat for {user_id} with system prompt: {current_system_prompt}")
            
            # 尝试创建模型实例，并处理各种库版本差异
            try:
                # 构建一个带有系统提示的模型配置
                model_config = {
                    "model_name": model_type,
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
                
                # 尝试启动聊天会话
                try:
                    # 如果支持异步API，使用它
                    if hasattr(model, "start_chat"):
                        chat = model.start_chat(history=[])
                    else:
                        # 如果不支持聊天会话，使用生成内容API
                        # 这是一个降级方案，可能无法保持上下文
                        chat = model
                    
                    chat_session_dict[str(user_id)] = chat
                except Exception as chat_err:
                    print(f"Error starting chat: {chat_err}")
                    # 降级为简单模型
                    chat = model
                    chat_session_dict[str(user_id)] = chat
            except Exception as model_err:
                print(f"Error creating model: {model_err}")
                await bot.edit_message_text(
                    f"Error creating model: {str(model_err)}",
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id
                )
                return
        else:
            chat = chat_session_dict[str(user_id)]

        # 尝试发送消息并处理响应
        try:
            # 尝试使用流式API，如果可用
            if hasattr(chat, "send_message_async"):
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
            else:
                # 如果不支持流式API，使用普通API
                print("Streaming not available, using standard API")
                if hasattr(chat, "send_message"):
                    response = chat.send_message(m)
                elif hasattr(chat, "generate_content"):
                    response = chat.generate_content(m)
                else:
                    raise Exception("Neither send_message nor generate_content methods available")
                
                # 处理响应
                full_response = ""
                if hasattr(response, "text"):
                    full_response = response.text
                elif hasattr(response, "parts") and len(response.parts) > 0:
                    for part in response.parts:
                        if hasattr(part, "text"):
                            full_response += part.text
            
            # 最终更新消息
            try:
                await bot.edit_message_text(
                    escape(full_response) if full_response else "No content generated.",
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
        except Exception as stream_err:
            print(f"Error in streaming: {stream_err}")
            await bot.edit_message_text(
                f"Error processing response: {str(stream_err)}",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )

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
