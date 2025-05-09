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
    
    gemini_chat_dict.clear()
    gemini_pro_chat_dict.clear()
    # gemini_draw_dict.clear()  # 不再需要 gemini_draw_dict

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

# 恢复不再使用的字典，实际上是需要的
# gemini_draw_dict = {}
gemini_chat_dict = {}
gemini_pro_chat_dict = {}
default_model_dict = {}
language_dict = {}  # 用户语言偏好字典

model_1 = conf["model_1"]
model_2 = conf["model_2"]
model_3 = conf["model_3"]
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
        
        except Exception as e_send:
            print(f"Error sending message or processing stream for user {user_id_str}: {e_send}")
            traceback.print_exc()
            
            error_message = str(e_send).lower()
            if "block" in error_message or "safety" in error_message or "harm" in error_message:
                print(f"Prompt blocked for user {user_id_str}: {e_send}")
                await bot.edit_message_text(f"Your request was blocked by safety settings. Details: {str(e_send)}", 
                                           chat_id=sent_message.chat.id, 
                                           message_id=sent_message.message_id)
            elif "stop" in error_message and "candidate" in error_message:
                print(f"Generation stopped by model for user {user_id_str}: {e_send}")
                await bot.edit_message_text(f"Content generation stopped as instructed. {str(e_send)}", 
                                           chat_id=sent_message.chat.id, 
                                           message_id=sent_message.message_id)
            else:
                await bot.edit_message_text(f"Error processing your request: {str(e_send)}", 
                                          chat_id=sent_message.chat.id, 
                                          message_id=sent_message.message_id)

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
    sent_message = None
    try:
        if not gemini_client:
            error_text = "非常严重的错误: Gemini 客户端尚未在 gemini.py 中初始化。请检查 main.py 中的设置。"
            print(error_text)
            await bot.reply_to(message, error_text)
            return

        pil_image = Image.open(io.BytesIO(photo_file))
        sent_message = await bot.reply_to(message, get_message("generating_answers", user_id))
        
        edit_model_name = model_2 # 来自全局 conf["model_2"]
        print(f"gemini_edit: 使用模型 {edit_model_name}，系统提示: {current_system_prompt}")

        # 准备 API 调用的 contents 参数
        contents_for_api = []
        if m and m.strip(): # 如果提供了文本提示，则添加
            contents_for_api.append(m)
        contents_for_api.append(pil_image) # 添加图片

        if not contents_for_api or (not m and not pil_image): # 确保至少有内容
            await bot.edit_message_text("没有提供用于编辑的提示或图片。", chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            return

        # 准备 generate_content 调用的配置参数
        pydantic_config_params = {}
        if current_system_prompt:
            pydantic_config_params['system_instruction'] = current_system_prompt

        if safety_settings: # 来自 config.py 的全局 safety_settings
            try:
                formatted_safety_settings = []
                for ss_item in safety_settings:
                    if isinstance(ss_item, dict):
                        formatted_safety_settings.append(types.SafetySetting(**ss_item))
                    elif isinstance(ss_item, types.SafetySetting):
                        formatted_safety_settings.append(ss_item)
                if formatted_safety_settings:
                    pydantic_config_params['safety_settings'] = formatted_safety_settings
            except Exception as e_ss_format:
                print(f"警告: 格式化 safety_settings 出错 (gemini_edit): {e_ss_format}。安全设置可能未生效。")

        if generation_config: # 来自 config.py 的全局 generation_config
            pydantic_config_params.update(generation_config)
        
        gen_config_for_api = None
        if pydantic_config_params:
            try:
                gen_config_for_api = types.GenerateContentConfig(**pydantic_config_params)
            except Exception as e_conf_create:
                print(f"错误: 创建 GenerateContentConfig 失败 (gemini_edit): {e_conf_create}。配置参数: {pydantic_config_params}")

        # 使用新的 SDK 客户端进行 API 调用
        try:
            print(f"gemini_edit: 调用模型 {edit_model_name}，配置: {gen_config_for_api}")
            response = await gemini_client.aio.models.generate_content(
                model=edit_model_name, 
                contents=contents_for_api,
                config=gen_config_for_api
            )
            
            text_response = ""
            # 新 SDK 的 generate_content 直接在 response 对象上有 text 属性 (如果响应是文本)
            # 或者在 response.candidates[0].content.parts[0].text
            # 根据用户提供的文档，response.text 是一个便捷访问方式
            if hasattr(response, "text") and response.text:
                text_response = response.text
            elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                 for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        text_response += part.text
            # 旧的 parts 检查方式，保留以防万一，但新SDK推荐用 candidate 结构
            elif hasattr(response, "parts") and response.parts: # Fallback for older possible structure or direct parts
                for part in response.parts:
                    if hasattr(part, "text") and part.text:
                        text_response += part.text
            
            if text_response:
                final_md_response = escape(text_response)
                try:
                    await bot.edit_message_text(
                        final_md_response,
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id,
                        parse_mode="MarkdownV2"
                    )
                except Exception as md_err:
                    if "parse markdown" in str(md_err).lower():
                        await bot.edit_message_text(text_response, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                    else:
                        raise md_err # 重新抛出其他类型的编辑错误
            else:
                await bot.edit_message_text("编辑后未能生成文本响应。", chat_id=sent_message.chat.id, message_id=sent_message.message_id)

        except Exception as e_gen_content:
            print(f"gemini_edit: generate_content 过程中出错: {e_gen_content}")
            traceback.print_exc()
            error_message = str(e_gen_content).lower()
            
            # 根据异常消息内容判断异常类型
            if "block" in error_message or "safety" in error_message or "harm" in error_message:
                print(f"gemini_edit: 用户 {user_id} 的提示可能因安全设置被阻止")
                await bot.edit_message_text(f"您的编辑请求因安全设置被阻止。详情: {str(e_gen_content)}", 
                                          chat_id=sent_message.chat.id, 
                                          message_id=sent_message.message_id)
            elif "stop" in error_message and "candidate" in error_message:
                print(f"gemini_edit: 用户 {user_id} 的生成可能被模型中止")
                await bot.edit_message_text(f"内容生成已按指示停止。{str(e_gen_content)}", 
                                          chat_id=sent_message.chat.id, 
                                          message_id=sent_message.message_id)
            else:
                await bot.edit_message_text(f"处理您的编辑请求时出错: {str(e_gen_content)}", 
                                          chat_id=sent_message.chat.id, 
                                          message_id=sent_message.message_id)

    except Exception as e_outer:
        traceback.print_exc()
        error_msg_key = 'error_info'
        error_details_key = 'error_details' 
        try:
            error_message_text = f"{get_message(error_msg_key, user_id)}\n{get_message(error_details_key, user_id)}{str(e_outer)}"
        except Exception: 
             error_message_text = f"gemini_edit 中发生意外错误: {str(e_outer)}"
        
        if sent_message:
            try:
                await bot.edit_message_text(error_message_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception as e_final_error_edit:
                print(f"gemini_edit: 编辑最终错误消息失败: {e_final_error_edit}")
        else:
            try:
                await bot.reply_to(message, error_message_text)
            except Exception as e_final_error_reply:
                print(f"gemini_edit: 回复最终错误消息失败: {e_final_error_reply}")

async def gemini_draw(bot:TeleBot, message:Message, m:str):
    user_id = message.from_user.id
    sent_message = None
    try:
        if not gemini_client:
            error_text = "非常严重的错误: Gemini 客户端尚未在 gemini.py 中初始化。"
            print(error_text)
            await bot.reply_to(message, error_text)
            return

        sent_message = await bot.reply_to(message, get_message("drawing", user_id))
        
        draw_model_name = model_3  # 使用配置中的 model_3 (gemini-2.0-flash-preview-image-generation)
        
        print(f"gemini_draw: 使用模型 {draw_model_name} 生成内容 (文本+图像)，提示: {m}")
        
        # 准备专门用于图像生成的配置
        image_gen_specific_config = {
            "response_modalities": ['TEXT', 'IMAGE']
        }
        # 合并全局的 generation_config (例如 temperature 等，如果存在且适用)
        # 注意：需要检查哪些全局配置与图像生成兼容
        if generation_config: 
            # 创建副本以避免修改全局字典
            # 仅合并全局配置中与 GenerateContentConfig 兼容的已知参数
            compatible_global_config = {}
            for key, value in generation_config.items():
                if key in ["temperature", "top_p", "top_k", "max_output_tokens", "candidate_count", "stop_sequences"]:
                    compatible_global_config[key] = value
            if compatible_global_config:
                 image_gen_specific_config.update(compatible_global_config)

        # 添加安全设置
        if safety_settings:
            try:
                formatted_safety_settings = []
                for ss_item in safety_settings:
                    if isinstance(ss_item, dict):
                        formatted_safety_settings.append(types.SafetySetting(**ss_item))
                    elif isinstance(ss_item, types.SafetySetting):
                        formatted_safety_settings.append(ss_item)
                if formatted_safety_settings:
                    image_gen_specific_config['safety_settings'] = formatted_safety_settings
            except Exception as e_ss:
                print(f"警告: 格式化 safety_settings 出错 (gemini_draw): {e_ss}")
        
        final_gen_config_for_api = None
        if image_gen_specific_config:
            try:
                final_gen_config_for_api = types.GenerateContentConfig(**image_gen_specific_config)
            except Exception as e_conf:
                print(f"错误: 创建 GenerateContentConfig 失败 (gemini_draw): {e_conf}。配置: {image_gen_specific_config}")
        
        # 调用 generate_content API
        try:
            print(f"调用模型 '{draw_model_name}' generate_content，提示: '{m}'，配置: {final_gen_config_for_api}")
            # contents 参数应该是可迭代的，通常是 Parts 列表，但对于简单文本提示，直接传递字符串也可以
            # 根据您提供的示例，直接传递提示字符串是可行的
            response = await gemini_client.aio.models.generate_content(
                model=draw_model_name,
                contents=m, # 用户提供的提示字符串
                config=final_gen_config_for_api
            )
            
            # 检查是否有临时消息需要删除
            if sent_message:
                try:
                    await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                except Exception as e_del:
                    print(f"警告: 删除临时消息失败: {e_del}")
                sent_message = None # 避免后续错误处理再次尝试编辑已删除消息
            
            # 处理响应
            has_content_sent = False
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    # 文本部分
                    if hasattr(part, "text") and part.text is not None: # 确保 text 存在且不为 None
                        text_content = part.text
                        print(f"模型返回文本部分: {text_content[:200]}...")
                        # 分段发送长文本
                        while len(text_content) > 4000:
                            try:
                                await bot.send_message(message.chat.id, escape(text_content[:4000]), parse_mode="MarkdownV2")
                            except Exception as e_md_chunk:
                                await bot.send_message(message.chat.id, text_content[:4000])
                                print(f"Markdown 发送分块失败，已用纯文本发送: {e_md_chunk}")
                            text_content = text_content[4000:]
                        if text_content: # 发送剩余部分
                            try:
                                await bot.send_message(message.chat.id, escape(text_content), parse_mode="MarkdownV2")
                            except Exception as e_md_final:
                                await bot.send_message(message.chat.id, text_content)
                                print(f"Markdown 发送最后部分失败，已用纯文本发送: {e_md_final}")
                        has_content_sent = True
                    
                    # 图片部分
                    elif hasattr(part, "inline_data") and part.inline_data is not None: # 确保 inline_data 存在且不为 None
                        if hasattr(part.inline_data, "data") and part.inline_data.data:
                            photo_bytes = part.inline_data.data
                            print(f"模型返回图像数据，大小: {len(photo_bytes)} bytes")
                            try:
                                # PIL 用于验证图像是否有效 (可选)
                                # img_verify = Image.open(io.BytesIO(photo_bytes))
                                # img_verify.verify() # 可能会抛出异常如果图像损坏
                                await bot.send_photo(message.chat.id, photo=photo_bytes, caption=f"🖼️ (gemini-2.0-flash-preview-image-generation): {m[:100]}")
                                has_content_sent = True
                            except Exception as e_send_photo:
                                print(f"发送图片失败: {e_send_photo}")
                                await bot.send_message(message.chat.id, "模型返回了图像数据，但发送图片时出错。")
                        else:
                            print("inline_data 对象存在，但其 data 属性为空或不存在")
            
            if not has_content_sent:
                print("generate_content 响应中未找到有效的文本或图像部分。检查模型响应结构。")
                # 尝试打印整个响应以便调试 (如果响应不太大)
                try:
                    print(f"完整响应详情: {response}")
                except Exception as e_print_resp:
                    print(f"打印完整响应失败: {e_print_resp}")
                await bot.send_message(message.chat.id, "模型未能生成预期的内容 (文本或图像)。请检查提示或模型能力。")
            
        except Exception as e_gen_content:
            print(f"gemini_draw: generate_content 过程中出错: {e_gen_content}")
            traceback.print_exc()
            error_message_str = str(e_gen_content).lower()
            if "block" in error_message_str or "safety" in error_message_str or "harm" in error_message_str:
                error_text_reply = f"您的绘图请求因安全设置被阻止。详情: {str(e_gen_content)}"
            else:
                error_text_reply = f"绘图过程中出错: {str(e_gen_content)}"
            
            if sent_message: # 如果临时消息还在，编辑它
                await bot.edit_message_text(error_text_reply, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            else: # 否则回复新的错误消息
                await bot.reply_to(message, error_text_reply)

    except Exception as e_outer:
        traceback.print_exc()
        error_msg_key = 'error_info'
        error_details_key = 'error_details'
        try:
            error_message_text = f"{get_message(error_msg_key, user_id)}\n{get_message(error_details_key, user_id)}{str(e_outer)}"
        except Exception: 
             error_message_text = f"gemini_draw 中发生意外错误: {str(e_outer)}"
        
        if sent_message:
            try:
                await bot.edit_message_text(error_message_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception as e_final_error_edit:
                print(f"gemini_draw: 编辑最终错误消息失败: {e_final_error_edit}")
        else:
            try:
                await bot.reply_to(message, error_message_text)
            except Exception as e_final_error_reply:
                print(f"gemini_draw: 回复最终错误消息失败: {e_final_error_reply}")
