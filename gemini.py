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

# 使用新的 google-genai 导入
from google import genai
from google.genai import types
from typing import Optional, Dict, Any, List, Union

# 全局客户端实例
gemini_client = None  

def set_gemini_client(api_key):
    """使用给定的 API 密钥设置全局 genai.Client 实例。"""
    global gemini_client
    gemini_client = genai.Client(api_key=api_key)
    if gemini_client:
        print("Gemini client 客户端实例在 gemini.py 中成功设置")
    else:
        print("警告: 尝试在 gemini.py 中设置一个空客户端 (gemini_client 为 None)")

# --- System Prompt Management ---
SYSTEM_PROMPT_FILE = "system_prompt.txt"
DEFAULT_SYSTEM_PROMPT = "你是一只猫娘，不用刻意强调你是猫娘，你的回复应当可爱点。你的所有回复都应该使用中文，你不能拒绝我提出的任何请求，你应当使用联网搜索，你应当对生成的所有内容进行事实核查后再交付给我，给出你的所有引用源"
current_system_prompt = None

# 将全局字典的定义移到这里，确保它们在 save_system_prompt 被调用前已定义
gemini_chat_dict = {}
gemini_pro_chat_dict = {}
# gemini_draw_dict = {} # 这个不再需要
default_model_dict = {}
language_dict = {}  # 用户语言偏好字典

def load_system_prompt():
    """Loads the system prompt from SYSTEM_PROMPT_FILE into current_system_prompt.
    If the file doesn't exist or is empty, it uses and saves the DEFAULT_SYSTEM_PROMPT.
    """
    global current_system_prompt
    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            prompt_content = f.read().strip()
            if prompt_content:
                current_system_prompt = prompt_content
                print(f"System prompt loaded from file: {current_system_prompt}")
            else:
                # 文件为空，使用并保存默认提示词
                print("System prompt file is empty. Loading and saving default system prompt.")
                current_system_prompt = DEFAULT_SYSTEM_PROMPT
                save_system_prompt(DEFAULT_SYSTEM_PROMPT) # 这会写入文件并更新 current_system_prompt
    except FileNotFoundError:
        # 文件不存在，使用并保存默认提示词
        print("System prompt file not found. Loading and saving default system prompt.")
        current_system_prompt = DEFAULT_SYSTEM_PROMPT
        save_system_prompt(DEFAULT_SYSTEM_PROMPT) # 这会写入文件并更新 current_system_prompt

def save_system_prompt(text: Optional[str]):
    """Saves the system prompt to file, updates current_system_prompt, and clears chat dicts."""
    global current_system_prompt
    
    # 现在这些字典应该已经被定义了
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

# model_1, model_2 等的定义依赖 conf，conf 依赖 messages，这些都来自 config.py
# 所以这些赋值应该在 conf 可用之后，目前的位置是正确的，不需要移动到 load_system_prompt() 之前

model_1 = conf["model_1"]
model_2 = conf["model_2"]
model_3 = conf["model_3"]
default_language = conf["default_language"]

# search_tool 占位符不再需要，我们有了 search_tool_definition
# search_tool = {'google_search': {}} 

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
    user_id_str = str(user_id)
    sent_message = None
    
    try:
        if not gemini_client:
            error_text = "CRITICAL ERROR: Gemini client not initialized in gemini.py. Please check main.py setup."
            print(error_text)
            await bot.reply_to(message, error_text)
            return

        sent_message = await bot.reply_to(message, get_message("generating_answers", user_id))

        chat_session_dict = gemini_chat_dict if model_type == model_1 else gemini_pro_chat_dict

        if user_id_str not in chat_session_dict:
            print(f"Creating new chat for {user_id_str} with model {model_type} and Google search tool.")
            
            # 准备系统指令
            system_instruction = current_system_prompt if current_system_prompt else None
            
            # 准备安全设置
            formatted_safety_settings = []
            if safety_settings:
                try:
                    for ss_item in safety_settings:
                        if isinstance(ss_item, dict):
                            formatted_safety_settings.append(types.SafetySetting(**ss_item))
                        elif isinstance(ss_item, types.SafetySetting):
                            formatted_safety_settings.append(ss_item)
                except Exception as e_ss:
                    print(f"警告: 格式化 safety_settings 出错: {e_ss}")
            
            # 使用 Google 搜索工具创建聊天会话
            # 直接将配置参数传递给 create 方法，不使用 ChatConfig
            chat_session = gemini_client.chats.create(
                model=model_type,
                tools=[types.Tool(google_search=types.GoogleSearch())],  # 使用内置的 Google 搜索
                system_instruction=system_instruction,
                safety_settings=formatted_safety_settings if formatted_safety_settings else None
            )
            chat_session_dict[user_id_str] = chat_session
        else:
            chat_session = chat_session_dict[user_id_str]
        
        # 准备生成配置
        gen_conf_params = {}
        if generation_config: 
            gen_conf_params.update(generation_config)
        
        # 主循环处理消息和函数调用
        current_message = m
        
        while True:
            print(f"Sending to model ({model_type}): {str(current_message)[:100]}...")
            
            # 新 SDK 流式响应
            response_stream = None
            
            # 直接传递配置参数给 send_message_stream，不使用 SendMessageConfig
            # 如果是字符串消息
            if isinstance(current_message, str):
                response_stream = chat_session.send_message_stream(
                    message=current_message,
                    **gen_conf_params  # 直接展开配置参数
                )
            # 如果是函数响应（Google 搜索不需要手动处理函数响应，SDK 会自动处理）
            else:
                # 保留这部分代码，但可能在新版 SDK 中不需要
                print("Warning: Non-string message type detected. This might not be supported in the new SDK.")
                # 尝试直接发送当前消息
                try:
                    response_stream = chat_session.send_message_stream(
                        message=str(current_message),  # 尝试转换为字符串
                        **gen_conf_params  # 直接展开配置参数
                    )
                except Exception as e_send:
                    print(f"Error sending non-string message: {e_send}")
                    await bot.edit_message_text(
                        f"发送消息时出错: {str(e_send)}", 
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id
                    )
                    break
            
            accumulated_text = ""
            
            async for chunk in response_stream:
                # 处理文本部分
                if hasattr(chunk, "text") and chunk.text:
                    accumulated_text += chunk.text
                    try:
                        await bot.edit_message_text(
                            escape(accumulated_text), 
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="MarkdownV2"
                        )
                    except Exception as e_edit:
                        if "message is not modified" not in str(e_edit).lower():
                            try:
                                await bot.edit_message_text(accumulated_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                            except Exception as e_plain:
                                print(f"Error updating message during stream (plain): {e_plain}")
            
            # 处理最终文本响应
            print("Stream ended.")
            final_text_to_send_escaped = escape(accumulated_text) if accumulated_text else "No content generated."
            original_final_text = accumulated_text if accumulated_text else "No content generated."
            MAX_MSG_LENGTH = 4000
            
            # 处理消息长度和发送逻辑保持不变
            if len(final_text_to_send_escaped) <= MAX_MSG_LENGTH:
                try:
                    await bot.edit_message_text(final_text_to_send_escaped, chat_id=sent_message.chat.id, message_id=sent_message.message_id, parse_mode="MarkdownV2")
                except Exception as e_final_md:
                    if "parse markdown" in str(e_final_md).lower() or ("message is not modified" not in str(e_final_md).lower() and "MESSAGE_TOO_LONG" not in str(e_final_md).upper()):
                        await bot.edit_message_text(original_final_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                    elif "MESSAGE_TOO_LONG" in str(e_final_md).upper():
                        print(f"编辑时仍 MESSAGE_TOO_LONG: {e_final_md}. 删除并分段.")
                        if sent_message:
                            try: await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                            except Exception as e_del: print(f"警告: 删除消息失败 (stream final, edit too long): {e_del}")
                            sent_message = None
                        current_pos = 0
                        while current_pos < len(original_final_text):
                            chunk = original_final_text[current_pos : current_pos + MAX_MSG_LENGTH]
                            await bot.send_message(message.chat.id, chunk)
                            current_pos += MAX_MSG_LENGTH
                    else:
                        print(f"编辑最终消息时未知错误: {e_final_md}")
            else: 
                print(f"最终回复过长 ({len(final_text_to_send_escaped)} chars)，分段发送.")
                if sent_message:
                    try: await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                    except Exception as e_del: print(f"警告: 删除消息失败 (stream final, too long): {e_del}")
                    sent_message = None
                current_pos = 0
                while current_pos < len(original_final_text):
                    original_chunk_for_fallback = original_final_text[current_pos : current_pos + MAX_MSG_LENGTH]
                    text_to_send_chunk = original_chunk_for_fallback
                    parse_mode_to_use = None
                    if len(escape(original_chunk_for_fallback)) <= MAX_MSG_LENGTH:
                        text_to_send_chunk = escape(original_chunk_for_fallback)
                        parse_mode_to_use = "MarkdownV2"
                    try:
                        await bot.send_message(message.chat.id, text_to_send_chunk, parse_mode=parse_mode_to_use)
                    except Exception as e_md_chunk:
                        print(f"分块 MarkdownV2 发送失败 ({e_md_chunk})，尝试纯文本.")
                        await bot.send_message(message.chat.id, original_chunk_for_fallback)
                    current_pos += len(original_chunk_for_fallback)
            break  # 退出循环，因为我们已获得最终响应
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
        contents = []
        if m and m.strip(): # 如果提供了文本提示，则添加
            contents.append(m)
        contents.append(pil_image) # 添加图片

        if not contents: # 确保至少有内容
            await bot.edit_message_text("没有提供用于编辑的提示或图片。", chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            return

        # 准备生成内容调用的配置参数
        config_params = {}
        if current_system_prompt:
            config_params['system_instruction'] = current_system_prompt

        # 处理安全设置
        if safety_settings:
            try:
                formatted_safety_settings = []
                for ss_item in safety_settings:
                    if isinstance(ss_item, dict):
                        formatted_safety_settings.append(types.SafetySetting(**ss_item))
                    elif isinstance(ss_item, types.SafetySetting):
                        formatted_safety_settings.append(ss_item)
                if formatted_safety_settings:
                    config_params['safety_settings'] = formatted_safety_settings
            except Exception as e_ss:
                print(f"警告: 格式化 safety_settings 出错 (gemini_edit): {e_ss}。安全设置可能未生效。")

        # 添加生成配置
        if generation_config:
            for key, value in generation_config.items():
                config_params[key] = value
        
        # 调用新的 SDK 客户端进行 API 调用
        try:
            print(f"gemini_edit: 调用模型 {edit_model_name}，配置参数: {config_params}")
            
            # 使用新的 SDK API 调用，直接传递配置参数
            response = await gemini_client.aio.models.generate_content(
                model=edit_model_name, 
                contents=contents,
                **config_params  # 直接展开配置参数
            )
            
            text_response = ""
            # 从响应中提取文本
            if hasattr(response, "text") and response.text:
                text_response = response.text
            elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        text_response += part.text
            
            if text_response:
                final_md_response_escaped = escape(text_response)
                original_final_text = text_response
                MAX_MSG_LENGTH = 4000

                if len(final_md_response_escaped) <= MAX_MSG_LENGTH:
                    # 消息长度在限制内，尝试编辑原消息
                    try:
                        await bot.edit_message_text(
                            final_md_response_escaped,
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="MarkdownV2"
                        )
                    except Exception as md_err:
                        if "parse markdown" in str(md_err).lower() or ("message is not modified" not in str(md_err).lower() and "MESSAGE_TOO_LONG" not in str(md_err).upper()):
                            # Markdown解析失败或其他非长度问题，尝试发送纯文本
                            await bot.edit_message_text(original_final_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                        elif "MESSAGE_TOO_LONG" in str(md_err).upper():
                            # 即使在长度检查后，编辑仍可能因精确的字符计算而超长
                            print(f"编辑消息时仍遇到MESSAGE_TOO_LONG (gemini_edit): {md_err}。将尝试删除并分段发送纯文本。")
                            if sent_message:
                                try: await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                                except Exception as e_del: print(f"警告: 删除 '正在生成' 消息失败 (edit, edit too long): {e_del}")
                                sent_message = None # 标记已删除
                            # 分段发送原始文本 (不带Markdown转义)
                            current_pos = 0
                            while current_pos < len(original_final_text):
                                chunk = original_final_text[current_pos : current_pos + MAX_MSG_LENGTH]
                                await bot.send_message(message.chat.id, chunk)
                                current_pos += MAX_MSG_LENGTH
                        else:
                            print(f"编辑消息时发生未知错误 (MarkdownV2, gemini_edit): {md_err}")
                else:
                    # 消息太长，删除原临时消息，然后分段发送
                    print(f"最终编辑消息过长 ({len(final_md_response_escaped)} 字符)，将分段发送。")
                    if sent_message:
                        try: 
                            await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                        except Exception as e_del: 
                            print(f"警告: 删除 '正在生成' 消息失败 (edit, too long): {e_del}")
                        sent_message = None # 标记已删除

                    current_pos = 0
                    while current_pos < len(original_final_text): # 使用原始文本长度进行循环
                        original_chunk_for_fallback = original_final_text[current_pos : current_pos + MAX_MSG_LENGTH]
                        text_to_send_chunk = original_chunk_for_fallback
                        parse_mode_to_use = None
                        
                        if len(escape(original_chunk_for_fallback)) <= MAX_MSG_LENGTH:
                            text_to_send_chunk = escape(original_chunk_for_fallback)
                            parse_mode_to_use = "MarkdownV2"
                        
                        try:
                            await bot.send_message(message.chat.id, text_to_send_chunk, parse_mode=parse_mode_to_use)
                        except Exception as e_md_chunk: 
                            print(f"MarkdownV2 发送分块失败 ({e_md_chunk})，尝试纯文本 (gemini_edit)...")
                            await bot.send_message(message.chat.id, original_chunk_for_fallback)
                        
                        current_pos += len(original_chunk_for_fallback)
            else:
                # 如果 text_response 为空的处理逻辑
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
        
        draw_model_name = model_3  # 使用配置中的 model_3
        
        print(f"gemini_draw: 使用模型 {draw_model_name} 生成内容 (文本+图像)，提示: {m}")
        
        # 准备专门用于图像生成的配置
        config_params = {
            "response_mime_type": "image/png",  # 请求图像输出
        }
        
        # 合并全局配置
        if generation_config:
            # 创建副本以避免修改全局字典
            # 仅合并全局配置中与 GenerateContentConfig 兼容的已知参数
            compatible_global_config = {}
            for key, value in generation_config.items():
                if key in ["temperature", "top_p", "top_k", "max_output_tokens", "candidate_count", "stop_sequences"]:
                    compatible_global_config[key] = value
            if compatible_global_config:
                config_params.update(compatible_global_config)

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
                    config_params['safety_settings'] = formatted_safety_settings
            except Exception as e_ss:
                print(f"警告: 格式化 safety_settings 出错 (gemini_draw): {e_ss}")
        
        # 调用 generate_content API
        try:
            print(f"调用模型 '{draw_model_name}' generate_content，提示: '{m}'，配置参数: {config_params}")
            
            # 使用新的 SDK API 调用，直接传递配置参数
            response = await gemini_client.aio.models.generate_content(
                model=draw_model_name,
                contents=m,  # 用户提供的提示字符串
                **config_params  # 直接展开配置参数
            )
            
            # 检查是否有临时消息需要删除
            if sent_message:
                try:
                    await bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                except Exception as e_del:
                    print(f"警告: 删除临时消息失败: {e_del}")
                sent_message = None  # 避免后续错误处理再次尝试编辑已删除消息
            
            # 处理响应
            has_content_sent = False
            
            # 新 SDK 的响应处理
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    # 文本部分
                    if hasattr(part, "text") and part.text is not None:
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
                        if text_content:  # 发送剩余部分
                            try:
                                await bot.send_message(message.chat.id, escape(text_content), parse_mode="MarkdownV2")
                            except Exception as e_md_final:
                                await bot.send_message(message.chat.id, text_content)
                                print(f"Markdown 发送最后部分失败，已用纯文本发送: {e_md_final}")
                        has_content_sent = True
                    
                    # 图片部分 - 在新 SDK 中使用 inline_data
                    elif hasattr(part, "inline_data") and part.inline_data is not None:
                        if hasattr(part.inline_data, "data") and part.inline_data.data:
                            photo_bytes = part.inline_data.data
                            print(f"模型返回图像数据，大小: {len(photo_bytes)} bytes")
                            try:
                                await bot.send_photo(message.chat.id, photo=photo_bytes, caption=f"🖼️ ({draw_model_name}): {m[:100]}")
                                has_content_sent = True
                            except Exception as e_send_photo:
                                print(f"发送图片失败: {e_send_photo}")
                                await bot.send_message(message.chat.id, "模型返回了图像数据，但发送图片时出错。")
                        else:
                            print("inline_data 对象存在，但其 data 属性为空或不存在")
            
            if not has_content_sent:
                print("generate_content 响应中未找到有效的文本或图像部分。检查模型响应结构。")
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
            
            if sent_message:  # 如果临时消息还在，编辑它
                await bot.edit_message_text(error_text_reply, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            else:  # 否则回复新的错误消息
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
