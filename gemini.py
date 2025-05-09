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
        
        # 从配置中获取 Imagen 模型名称和相关参数
        imagen_model_to_use = conf.get("imagen_model_name", "imagen-3.0-generate-001") # 提供一个默认值
        num_images = conf.get("draw_num_images", 1)
        aspect_r = conf.get("draw_aspect_ratio", "1:1")
        output_mime = conf.get("draw_output_mime_type", "image/png")

        print(f"gemini_draw: 使用模型 {imagen_model_to_use} 进行绘图，提示: {m}")

        # 准备 GenerateImagesConfig
        # 注意：根据新SDK文档，一些参数如 safety_filter_level, person_generation 也可在此配置
        # 为简化，我们暂时只使用基础参数，您可以稍后根据需求在 config.py 中添加更多配置项
        try:
            img_gen_config = types.GenerateImagesConfig(
                number_of_images=num_images,
                aspect_ratio=aspect_r,
                output_mime_type=output_mime
                # 您可以在此处添加更多来自 types.GenerateImagesConfig 的参数
                # 例如：safety_filter_level="BLOCK_LOW_AND_ABOVE", person_generation="ALLOW_ADULT"
            )
        except Exception as e_conf_create:
            print(f"错误: 创建 GenerateImagesConfig 失败: {e_conf_create}")
            await bot.edit_message_text(f"绘图配置错误: {str(e_conf_create)}", chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            return

        # 使用新的 SDK 客户端进行 API 调用
        try:
            print(f"gemini_draw: 调用模型 {imagen_model_to_use}，配置: {img_gen_config}")
            response = await gemini_client.aio.models.generate_images(
                model=imagen_model_to_use, 
                prompt=m,
                config=img_gen_config
            )
            
            if response.generated_images:
                if sent_message: # 删除 "正在绘制..." 消息
                    try:
                        await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                    except Exception as e_del_msg:
                        print(f"警告: 删除消息失败 (gemini_draw): {e_del_msg}")
                    sent_message = None # 避免后续错误处理再次尝试编辑已删除消息
                
                for i, generated_image_obj in enumerate(response.generated_images):
                    if hasattr(generated_image_obj, 'image') and hasattr(generated_image_obj.image, 'image_bytes') and generated_image_obj.image.image_bytes:
                        image_data = generated_image_obj.image.image_bytes
                        caption = f"🖼️ (#{i+1}): {m[:100]}" # 限制标题长度
                        await bot.send_photo(message.chat.id, photo=image_data, caption=caption)
                    else:
                        print(f"gemini_draw: 生成的图像对象 {i+1} 缺少图像数据。")
                        await bot.send_message(message.chat.id, f"图像 {i+1} 生成数据不完整。")
            else:
                no_image_message = "未能生成图像。模型没有返回任何图像。"
                # 检查是否有 RAI (Responsible AI) 阻止原因
                # 新SDK的 GenerateImagesResponse 可能有不同的反馈结构，需要查阅
                # 例如，文档中 generate_images 的 config 有 include_rai_reason=True
                # 响应中可能有 response.positive_prompt_safety_attributes 或类似字段
                # 此处简化处理，实际应检查 response 结构以获取更详细的失败原因
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason: # 借用 generate_content 的结构，可能不适用
                    no_image_message += f" 原因: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"
                
                if sent_message:
                    await bot.edit_message_text(no_image_message, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                else:
                    await bot.reply_to(message, no_image_message)

        except Exception as e_gen_images:
            print(f"gemini_draw: generate_images 过程中出错: {e_gen_images}")
            traceback.print_exc()
            error_message = str(e_gen_images).lower()
            
            # 根据异常消息判断异常类型
            if "block" in error_message or "safety" in error_message or "harm" in error_message:
                error_text = f"您的绘图请求因安全设置被阻止。详情: {str(e_gen_images)}"
            elif "deadline" in error_message or "timeout" in error_message or "exceed" in error_message:
                error_text = "图像生成超时。请尝试更简单的提示或稍后再试。"
            else:
                error_text = f"处理您的绘图请求时出错: {str(e_gen_images)}"
            
            if sent_message: 
                await bot.edit_message_text(error_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                sent_message = None
            else: 
                await bot.reply_to(message, error_text)

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
