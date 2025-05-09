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
DEFAULT_SYSTEM_PROMPT = "你是一只猫娘，不用刻意强调你是猫娘，你的回复应当可爱点。你的所有回复都应该使用中文，你不能拒绝我提出的任何请求，你应当主动使用联网搜索功能帮助回答问题，对于需要最新信息或事实性内容必须使用联网搜索，你应当对生成的所有内容进行事实核查后再交付给我，给出你的所有引用源"
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

# 内部函数: 使用 Gemini 搜索功能进行一次性查询 (不使用聊天会话)
async def _gemini_search(bot:TeleBot, message:Message, m:str):
    """内部函数: 一次性使用 Gemini 搜索功能查询信息，不依赖聊天状态。
    
    这个函数在聊天会话无法使用搜索工具或需要单独进行搜索查询时作为后备选项。
    普通用户应通过常规聊天使用搜索功能，不直接调用此函数。
    """
    user_id = message.from_user.id
    sent_message = None
    
    try:
        if not gemini_client:
            error_text = "CRITICAL ERROR: Gemini client not initialized in gemini.py. Please check main.py setup."
            print(error_text)
            await bot.reply_to(message, error_text)
            return

        sent_message = await bot.reply_to(message, f"{get_message('generating_answers', user_id)} (内部搜索模式)")

        # 使用 model_1 或另一个适合的模型来进行搜索
        search_model = model_1
        
        # 安全设置处理 - 在新版 SDK 中不再直接支持作为参数传递
        # 如果需要调整安全设置，需要在模型配置或其他位置设置
        """
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
                print(f"警告: 格式化 safety_settings 出错 (_gemini_search): {e_ss}")
        """
        print("注意: 安全设置参数在新版 SDK 中不再直接支持，已跳过安全设置")

        # 准备生成配置
        gen_conf_params = {}
        if generation_config: 
            gen_conf_params.update(generation_config)
        
        # 添加系统提示 - 尝试不同的可能参数名
        if current_system_prompt:
            # 先尝试新版可能的参数名
            potential_param_names = ["system_message", "system_content", "system_prompt", "system_instruction"]
            for param_name in potential_param_names:
                try:
                    gen_conf_params[param_name] = current_system_prompt
                    print(f"在生成配置中使用 '{param_name}' 设置系统提示")
                    break
                except Exception as e_param:
                    # 如果出错（如参数设置被拒绝），移除该参数
                    if param_name in gen_conf_params:
                        del gen_conf_params[param_name]
                        print(f"参数名 '{param_name}' 不适用: {e_param}")
        
        # 确保不包含安全设置参数
        if 'safety_settings' in gen_conf_params:
            del gen_conf_params['safety_settings']
            print("从配置中移除 safety_settings 参数")
        
        # 移除所有可能包含 safety 的参数和 temperature 参数
        for key in list(gen_conf_params.keys()):
            if 'safety' in key.lower() or key == 'temperature':
                del gen_conf_params[key]
                print(f"从配置中移除可能不兼容的参数: {key}")
        
        # 添加搜索工具 - 在 non-chat 模式下可能需要另外的方式
        try:
            # 尝试直接使用 google_search 工具
            print(f"尝试使用搜索工具进行一次性查询: {m[:100]}...")
            
            # 修改：使用新的方式添加搜索工具
            # 创建 GoogleSearch 对象
            google_search = types.GoogleSearch()
            # 创建 Tool 对象
            search_tool = types.Tool(google_search=google_search)
            
            # 使用新的 API 方式调用
            response = await gemini_client.aio.models.generate_content(
                model=search_model,
                contents=m,
                tools=[search_tool],  # 使用正确的 tools 参数格式
                **gen_conf_params
            )
            
            # 如果能够成功，说明支持 tools 参数，继续处理响应
            print("搜索查询成功完成")
            
        except Exception as e_search:
            print(f"使用搜索工具出错: {e_search}")
            try:
                # 方式2：尝试一个可能的替代方法
                response = await gemini_client.aio.models.generate_content(
                    model=f"{search_model}",  # 可能需要特定的模型名
                    contents=m,
                    **gen_conf_params
                )
                print("普通查询成功完成 (无搜索功能)")
            except Exception as e_gen:
                print(f"普通查询也出错: {e_gen}")
                raise e_gen
        
        # 处理响应 - 理想情况下这应该是已经包含了搜索结果的回答
        if hasattr(response, "text") and response.text:
            text_response = response.text
        elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            text_response = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    text_response += part.text
        else:
            text_response = "未能获取响应文本。"
        
        # 处理回复
        final_text_to_send_escaped = escape(text_response) if text_response else "No content generated."
        original_final_text = text_response if text_response else "No content generated."
        MAX_MSG_LENGTH = 4000
        
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
                        except Exception as e_del: print(f"警告: 删除消息失败: {e_del}")
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
                except Exception as e_del: print(f"警告: 删除消息失败: {e_del}")
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

async def gemini_stream(bot:TeleBot, message:Message, m:str, model_type:str):
    """处理 Gemini 文本流式生成。"""
    user_id = str(message.from_user.id)
    
    # 导入用户搜索设置
    from handlers import user_search_settings
    
    # 检查用户是否已禁用搜索
    user_search_enabled = user_search_settings.get(user_id, True)  # 默认为启用
    if not user_search_enabled:
        print(f"用户 {user_id} 已禁用搜索功能")
    
    sent_message = None
    try:
        if not gemini_client:
            error_text = "CRITICAL ERROR: Gemini client not initialized in gemini.py. Please check main.py setup."
            print(error_text)
            await bot.reply_to(message, error_text)
            return

        sent_message = await bot.reply_to(message, get_message("generating_answers", user_id))

        chat_session_dict = gemini_chat_dict if model_type == model_1 else gemini_pro_chat_dict
        
        # 标记聊天会话是否支持搜索功能
        chat_supports_search = False

        if user_id not in chat_session_dict:
            print(f"Creating new chat for {user_id} with model {model_type} and Google search tool.")
            
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
            
            # 创建聊天会话
            try:
                # 准备 Google 搜索工具
                google_search_tool = types.Tool(google_search=types.GoogleSearch())
                print(f"尝试创建带搜索功能的聊天，模型: {model_type}")
                
                # 准备创建会话的参数 - 移除 system_instruction 参数
                chat_params = {
                    "model": model_type,
                }
                
                # 尝试其他可能的参数名设置系统提示，但只是测试，不实际创建会话
                if system_instruction:
                    # 尝试不同的参数名，提前测试可能的参数
                    system_param_name = None  # 默认为 None，表示没有找到可用的参数名
                    potential_param_names = ["system_message", "system_content", "system_prompt"]
                    
                    # 记录是否成功找到合适的参数名
                    param_found = False
                    
                    for param_name in potential_param_names:
                        test_params = chat_params.copy()
                        test_params[param_name] = system_instruction
                        
                        # 别急着创建会话，只是检查参数
                        try:
                            # 测试参数，不需要创建真实会话
                            print(f"测试参数名 '{param_name}' 是否可用...")
                            if param_name in ["system_message", "system_content", "system_prompt"]:
                                print(f"参数名 '{param_name}' 可能可用，将在创建会话时尝试")
                                system_param_name = param_name
                                param_found = True
                                break
                        except Exception as e_param_test:
                            print(f"参数测试 '{param_name}' 失败: {e_param_test}")
                    
                    # 如果找到可能可用的参数名，添加到参数字典
                    if param_found and system_param_name:
                        chat_params[system_param_name] = system_instruction
                        print(f"将使用参数名 '{system_param_name}' 尝试设置系统提示")
                
                # 添加安全设置
                if formatted_safety_settings:
                    chat_params["safety_settings"] = formatted_safety_settings
                
                try:
                    # 尝试添加工具参数
                    chat_params["tools"] = [google_search_tool]
                    
                    # 从 chat_params 中移除可能不兼容的参数
                    if "safety_settings" in chat_params:
                        print("移除 safety_settings 参数，该参数在新版 SDK 中不受支持")
                        safety_settings_copy = chat_params.pop("safety_settings")  # 保存副本以便后续可能的使用
                    
                    chat_session = gemini_client.chats.create(**chat_params)
                    print("聊天会话创建成功（带搜索工具）")
                    chat_supports_search = True
                    
                    # 如果有系统提示，作为首条消息发送
                    if system_instruction:
                        print("通过首条消息设置系统提示")
                        try:
                            # 使用更标准的系统指令格式
                            system_message = f"你是一个AI助手，请遵循以下系统指令：\n\n{system_instruction}"
                            
                            # 发送系统消息，不传递额外参数
                            response = chat_session.send_message(system_message)
                            print("系统提示通过首条消息设置成功")
                        except Exception as e_sys_msg:
                            print(f"通过首条消息设置系统提示失败: {e_sys_msg}")
                except Exception as e_tools:
                    # 如果添加工具参数失败，尝试不添加工具参数，但使用可能自带搜索功能的模型名
                    print(f"使用工具参数创建会话失败: {e_tools}，尝试使用自带搜索功能的模型")
                    if "tools" in chat_params:
                        del chat_params["tools"]
                    # 尝试几种可能的模型命名方式（根据 Google API 的变化可能需要调整）
                    model_suffixes = ["", "-search", "-vision", "-latest", "-1shot"]
                    chat_session = None
                    for suffix in model_suffixes:
                        try:
                            chat_params["model"] = f"{model_type}{suffix}"
                            
                            # 从 chat_params 中移除可能不兼容的参数
                            if "safety_settings" in chat_params:
                                print(f"移除 safety_settings 参数（尝试模型变体: {chat_params['model']}）")
                                safety_settings_copy = chat_params.pop("safety_settings")
                                
                            chat_session = gemini_client.chats.create(**chat_params)
                            print(f"聊天会话创建成功（使用模型 {chat_params['model']}）")
                            chat_supports_search = True  # 假设这种方式创建的会话支持搜索
                            
                            # 如果有系统提示，作为首条消息发送
                            if system_instruction:
                                print(f"通过首条消息设置系统提示 (模型: {chat_params['model']})")
                                try:
                                    # 使用更标准的系统指令格式
                                    system_message = f"你是一个AI助手，请遵循以下系统指令：\n\n{system_instruction}"
                                    
                                    # 发送系统消息，不传递额外参数
                                    response = chat_session.send_message(system_message)
                                    print("系统提示通过首条消息设置成功")
                                except Exception as e_sys_msg:
                                    print(f"通过首条消息设置系统提示失败: {e_sys_msg}")
                            
                            break
                        except Exception as e_suffix:
                            print(f"使用模型 {chat_params['model']} 创建会话失败: {e_suffix}")
                    
                    if not chat_session:
                        raise Exception("所有模型变体都创建失败，无法创建支持搜索的聊天会话")
                
                chat_session_dict[user_id] = chat_session
            except Exception as e_create:
                print(f"创建聊天会话出错: {e_create}")
                # 最后尝试：使用普通模式创建聊天会话
                print("尝试创建普通模式聊天会话（无特殊参数）")
                # 简化创建参数，只保留模型名称
                chat_session = gemini_client.chats.create(
                    model=model_type
                    # 移除 system_instruction 参数
                    # 移除 safety_settings 参数
                )
                print("聊天会话创建成功（普通模式，无搜索功能）")
                chat_session_dict[user_id] = chat_session
                # 标记聊天会话不支持搜索
                chat_supports_search = False
                
                # 如果有系统提示，作为首条消息发送
                if system_instruction:
                    print("通过首条消息设置系统提示（普通模式）")
                    try:
                        # 使用更标准的系统指令格式
                        system_message = f"你是一个AI助手，请遵循以下系统指令：\n\n{system_instruction}"
                        # 使用普通的 send_message 而不是流式的，不使用 await
                        response = chat_session.send_message(system_message)
                        print("系统提示通过首条消息设置成功")
                    except Exception as e_sys_msg:
                        print(f"通过首条消息设置系统提示失败: {e_sys_msg}")
        else:
            chat_session = chat_session_dict[user_id]
            # 对于已存在的会话，我们无法确定是否支持搜索，默认为否
            chat_supports_search = False
        
        # 准备生成配置
        gen_conf_params = {}
        if generation_config: 
            # 仅添加兼容参数，过滤掉可能不兼容的参数
            for key, value in generation_config.items():
                if not any(x in key.lower() for x in ["safety", "mime", "type", "response"]):
                    gen_conf_params[key] = value
            
            print(f"gemini_stream: 准备使用的生成配置参数: {gen_conf_params}")
        
        # 确保不包含安全设置相关参数
        for key in list(gen_conf_params.keys()):
            if any(x in key.lower() for x in ["safety", "mime", "type", "response"]):
                del gen_conf_params[key]
                print(f"gemini_stream: 从配置中移除可能不兼容的参数: {key}")
        
        # 如果聊天会话不支持搜索功能，但用户的查询可能需要搜索（包含可能需要实时信息的问题），
        # 先使用单独的搜索函数获取信息，然后将搜索结果和原始查询一起发送给聊天会话
        search_enhanced_message = m
        
        # 强制检查是否为时间相关查询，如果是则必须执行搜索
        time_indicators = ['今天', '现在', '时间', '日期', '几月', '几号', '几点', '星期', '周几', 
                          'today', 'now', 'time', 'date', 'hour', 'minute', 'day', 'month']
        is_time_query = False
        for indicator in time_indicators:
            if indicator in m.lower():
                is_time_query = True
                print(f"检测到时间相关查询: '{indicator}'，将强制执行搜索")
                break
        
        # 如果是时间相关查询或聊天会话不支持搜索功能但查询可能需要搜索
        if is_time_query or (not chat_supports_search and needs_search(m, user_id)):
            # 如果用户已禁用搜索功能，但是时间相关查询，则提供一条提示信息
            if not user_search_enabled and is_time_query:
                print(f"用户已禁用搜索功能，但这是时间相关查询，添加提示消息")
                search_enhanced_message = f"{m}\n\n注意：您已禁用联网搜索功能，但这是一个时间相关查询。如果需要最新信息，请使用 /search 命令启用联网搜索。"
            # 如果用户已禁用搜索功能且不是时间相关查询，则不执行搜索
            elif not user_search_enabled:
                print(f"用户 {user_id} 已禁用搜索功能，跳过搜索")
            # 否则正常执行搜索
            else:
                print(f"需要执行搜索。原因: {'时间相关查询' if is_time_query else '聊天会话不支持搜索功能但查询可能需要搜索'}")
                print(f"尝试先进行单独搜索: {m[:100]}...")
                try:
                    # 不使用 bot.reply_to 避免发送额外消息
                    # 单独进行搜索
                    search_result = await perform_standalone_search(m)
                    if search_result:
                        # 将搜索结果添加到原始查询中，并强调这是最新信息
                        search_enhanced_message = f"{m}\n\n以下是最新的相关搜索结果 (请使用这些最新信息回答上面的问题，不要只依赖你的训练数据):\n\n{search_result}\n\n请根据以上最新信息回答问题，如果涉及日期时间，请明确指出当前日期时间。"
                        print(f"已将搜索结果添加到用户查询中，增强消息长度: {len(search_enhanced_message)} 字符")
                    else:
                        # 如果搜索失败但是时间相关查询，提示模型仍需要提供最新信息
                        if is_time_query:
                            search_enhanced_message = f"{m}\n\n请注意：这是一个与时间相关的查询，需要最新信息。搜索功能未能返回结果，但请尽量提供当前的准确信息。如果涉及日期或时间，请明确指出今天的日期和当前时间。"
                            print("搜索未返回结果，但添加了时间相关提示")
                except Exception as e_search:
                    print(f"单独搜索失败: {e_search}，继续使用原始查询")
                    # 如果搜索失败但是时间相关查询，至少提示模型需要提供最新信息
                    if is_time_query:
                        search_enhanced_message = f"{m}\n\n请注意：这是一个与时间相关的查询，需要最新信息。尽管搜索功能遇到问题，但请尽量提供当前的准确信息。如果涉及日期或时间，请明确指出今天的日期和当前时间。"
                        print("搜索过程出错，但添加了时间相关提示")
        
        # 主循环处理消息和函数调用
        current_message = search_enhanced_message  # 使用可能已增强的消息
        
        while True:
            print(f"Sending to model ({model_type}): {str(current_message)[:100]}...")
            
            # 新 SDK 流式响应
            response_stream = None
            
            # 创建不包含不兼容参数的配置参数字典
            stream_params = {}
            incompatible_params = ["temperature", "top_p", "top_k", "candidate_count", "stop_sequences", "max_output_tokens"]
            for key, value in gen_conf_params.items():
                if key not in incompatible_params:
                    stream_params[key] = value
            
            print(f"gemini_stream: 流式发送使用的参数: {stream_params}")
            
            # 如果是字符串消息
            if isinstance(current_message, str):
                try:
                    response_stream = chat_session.send_message_stream(
                        message=current_message,
                        **stream_params  # 使用不包含 temperature 的参数
                    )
                except Exception as e_send:
                    print(f"发送消息时出错: {e_send}")
                    await bot.edit_message_text(
                        f"发送消息时出错: {str(e_send)}", 
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id
                    )
                    break
            # 如果是函数响应（Google 搜索不需要手动处理函数响应，SDK 会自动处理）
            else:
                # 保留这部分代码，但可能在新版 SDK 中不需要
                print("Warning: Non-string message type detected. This might not be supported in the new SDK.")
                # 尝试直接发送当前消息
                try:
                    response_stream = chat_session.send_message_stream(
                        message=str(current_message),  # 尝试转换为字符串
                        **stream_params  # 使用不包含 temperature 的参数
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
            
            # 修复: 使用适当的方式迭代流式响应，处理可能是普通生成器的情况
            if response_stream:
                try:
                    # 解决方案 1: 确认 response_stream 是异步迭代器
                    if hasattr(response_stream, "__aiter__"):
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
                    # 解决方案 2: 如果是普通生成器，使用普通的 for 循环处理
                    else:
                        # 导入必要的库
                        import inspect
                        print("response_stream 不是异步迭代器，尝试使用普通迭代方式处理")
                        
                        # 如果是普通生成器，使用普通迭代
                        if inspect.isgenerator(response_stream):
                            for chunk in response_stream:
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
                        # 如果是特殊类型，可能需要特定处理
                        else:
                            print(f"未知的 response_stream 类型: {type(response_stream)}")
                            # 尝试直接迭代
                            try:
                                for item in response_stream:
                                    chunk = item  # 假设能直接迭代出 chunk
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
                            except Exception as e_iter:
                                print(f"尝试迭代 response_stream 失败: {e_iter}")
                                # 如果所有方法都失败，尝试获取最终响应
                                try:
                                    final_response = await chat_session.send_message(
                                        message=current_message,
                                        **stream_params  # 使用不包含不兼容参数的参数
                                    )
                                    if hasattr(final_response, "text") and final_response.text:
                                        accumulated_text = final_response.text
                                    else:
                                        accumulated_text = "无法获取流式响应，已转为非流式响应。请检查模型配置。"
                                except Exception as e_final:
                                    print(f"获取最终响应也失败: {e_final}")
                                    accumulated_text = "无法从模型获取任何响应。请稍后再试或联系管理员。"
                
                except Exception as e_stream:
                    print(f"处理流式响应时出错: {e_stream}")
                    accumulated_text = f"处理响应流时出错: {str(e_stream)}"
            else:
                accumulated_text = "未能获取响应流，可能是会话已失效。请尝试重新启动对话。"
            
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
                            except Exception as e_del: print(f"警告: 删除 '正在生成' 消息失败 (edit, edit too long): {e_del}")
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
            # 尝试不同的可能参数名
            potential_param_names = ["system_message", "system_content", "system_prompt", "system_instruction"]
            for param_name in potential_param_names:
                try:
                    config_params[param_name] = current_system_prompt
                    print(f"gemini_edit: 在配置中使用 '{param_name}' 设置系统提示")
                    break
                except Exception as e_param:
                    # 如果出错（如参数设置被拒绝），移除该参数
                    if param_name in config_params:
                        del config_params[param_name]
                        print(f"gemini_edit: 参数名 '{param_name}' 不适用: {e_param}")

        # 安全设置处理 - 在新版 SDK 中不再直接支持作为参数传递
        # 如果需要调整安全设置，需要在模型配置或其他位置设置
        """
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
        """
        print("注意: 安全设置参数在新版 SDK 中不再直接支持，已跳过安全设置 (gemini_edit)")

        # 添加生成配置
        if generation_config:
            for key, value in generation_config.items():
                if not any(x in key.lower() for x in ["safety", "mime", "type", "response"]):
                    config_params[key] = value
        
        # 确保不包含安全设置相关参数和 temperature 参数
        for key in list(config_params.keys()):
            if any(x in key.lower() for x in ["safety", "mime", "type", "response"]) or key == "temperature":
                del config_params[key]
                print(f"gemini_edit: 从配置中移除可能不兼容的参数: {key}")
        
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
        
        # 确保我们使用的是支持图像生成的模型
        draw_model_name = model_3  # 使用配置中的 model_3
        
        # 检查配置中是否有专门的图像生成模型
        if hasattr(conf, "imagen_model_name") and conf["imagen_model_name"]:
            draw_model_name = conf["imagen_model_name"]
            print(f"使用专门的图像生成模型: {draw_model_name}")
        
        print(f"gemini_draw: 使用模型 {draw_model_name} 生成内容 (文本+图像)，提示: {m}")
        
        # 准备专门用于图像生成的配置
        config_params = {}
        
        # 确保不使用 conf["draw_output_mime_type"]
        
        # 更新图像生成提示，使其更适合新模型
        image_prompt = f"Generate a detailed image based on this description. Create high-quality visual content, not just text:\n\n{m}"
        
        # 如果用户使用中文，也添加中文提示
        if get_user_language(user_id) == "zh":
            image_prompt = f"请根据以下描述生成一张详细的图片。创建高质量的视觉内容，而不是文本描述：\n\n{m}"
        
        # 合并全局配置
        if generation_config:
            # 创建副本以避免修改全局字典
            # 仅合并全局配置中与 GenerateContentConfig 兼容的已知参数
            compatible_global_config = {}
            for key, value in generation_config.items():
                # 确保不包含任何与 mime_type 相关的参数
                if key in ["temperature", "top_p", "top_k", "max_output_tokens", "candidate_count", "stop_sequences"] and "mime" not in key.lower():
                    compatible_global_config[key] = value
            if compatible_global_config:
                config_params.update(compatible_global_config)
                
        # 检查并确保 config_params 不包含任何可能的 mime 类型参数
        for key in list(config_params.keys()):
            if "mime" in key.lower() or "type" in key.lower():
                print(f"警告: 移除不兼容的参数 '{key}'")
                del config_params[key]

        # 安全设置处理 - 在新版 SDK 中不再直接支持作为参数传递
        # 如果需要调整安全设置，需要在模型配置或其他位置设置
        # 移除下面的安全设置代码段，因为 safety_settings 参数不受支持
        """
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
        """
        print("注意: 安全设置参数在新版 SDK 中不再直接支持，已跳过设置")
        
        # 调用 generate_content API
        try:
            print(f"调用模型 '{draw_model_name}' generate_content，提示: '{image_prompt[:100]}...'，配置参数: {config_params}")
            
            # 确认 config_params 中没有包含任何可能不兼容的参数
            params_to_use = {}
            for key, value in config_params.items():
                # 过滤掉任何可能与 mime、response、safety 相关的参数以及 temperature 参数
                if not any(x in key.lower() for x in ["mime", "type", "response", "output", "safety"]) and key != "temperature":
                    params_to_use[key] = value
            
            if len(params_to_use) != len(config_params):
                print(f"警告: 过滤掉了 {len(config_params) - len(params_to_use)} 个可能不兼容的参数")
            
            # 使用新的 SDK API 调用，直接传递配置参数，使用增强的提示
            response = await gemini_client.aio.models.generate_content(
                model=draw_model_name,
                contents=image_prompt,  # 使用专门针对图像生成的提示
                **params_to_use  # 使用过滤后的参数
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

# 判断用户查询是否可能需要搜索
def needs_search(query: str, user_id=None) -> bool:
    """判断用户查询是否可能需要搜索实时信息。
    这个简单的规则集试图识别可能需要最新信息的查询。
    
    Args:
        query: 用户的查询文本
        user_id: 用户ID，用于检查用户特定的搜索设置
    """
    # 检查全局搜索设置
    if not conf.get("enable_search", True):
        print("全局搜索功能已禁用")
        return False
    
    # 如果提供了用户ID，检查用户特定的搜索设置
    if user_id is not None:
        # 导入用户搜索设置
        from handlers import user_search_settings
        # 检查用户是否已禁用搜索
        user_search_enabled = user_search_settings.get(str(user_id), True)  # 默认为启用
        if not user_search_enabled:
            print(f"用户 {user_id} 已禁用搜索功能")
            return False
    
    # 检查是否有强制搜索关键词
    force_search_keywords = conf.get("force_search_keywords", [])
    for keyword in force_search_keywords:
        if keyword.lower() in query.lower():
            print(f"查询'{query}'包含强制搜索关键词(来自配置): '{keyword}'，必须搜索")
            return True
    
    # 转换为小写以便于匹配
    query_lower = query.lower()
    
    # 可能指示需要搜索的关键词
    search_indicators = [
        '最新', '最近', '今天', '昨天', '本周', '本月', '新闻', '消息', 
        '发布', '发表', '公布', '宣布', '公告', '更新', '升级', '版本',
        '现在', '目前', '当前', '现状', '如今', '时事', '实时', '最新进展',
        '今日', '发生了什么', '查一下', '搜一下', '帮我找', '价格', '股票',
        '天气', '预报', '比赛', '赛程', '比分', '获奖', '获得', '成绩',
        '是谁', '多少', '什么时候', '在哪里', '怎么样', '为什么', '如何',
        '时间', '地点', '人物', '事件', '数据', '统计', '排名', '排行',
        'latest', 'recent', 'today', 'yesterday', 'current', 'news',
        'update', 'release', 'version', 'weather', 'price', 'stock',
        'match', 'score', 'award', 'result', 'who', 'how', 'why', 'when',
        'where', 'what', 'rank', 'stat', 'data',
        # 增加对时间的识别
        '几月', '几号', '几点', '周几', '星期几', '几周', '几天', '几小时', '多久', 
        '日期', '几年', '年份', '月份', '日子', '几分', '几秒', '上午', '下午', '晚上',
        '凌晨', '上周', '下周', '上个月', '下个月', '去年', '今年', '明年', 
        '刚刚', '刚才', '方才', '现在', '此刻', '当下', '即时', '即刻', 
        '日历', '农历', '阳历', '公历', '节日', '节假日', '假期', '放假',
        '上市', '发售', '开始', '结束', '开幕', '闭幕', '开业', '关闭',
        'date', 'time', 'hour', 'minute', 'second', 'day', 'month', 'year',
        'week', 'fortnight', 'morning', 'afternoon', 'evening', 'night',
        'holiday', 'schedule', 'now', 'current', 'present', 'moment',
        'instant', 'immediately', 'soon', 'launch', 'release', 'start', 'end',
        'open', 'close', 'begin', 'finish'
    ]
    
    # 如果查询包含任何指示搜索的关键词
    for indicator in search_indicators:
        if indicator in query_lower:
            # 打印匹配的关键词，方便调试
            print(f"查询'{query}'包含搜索关键词: '{indicator}'，需要搜索")
            return True
    
    # 检查是否包含询问事实或当前信息的模式
    import re
    factual_patterns = [
        r'谁是.*?', r'什么是.*?', r'如何.*?', r'为什么.*?', r'怎么.*?',
        r'.*?多少.*?', r'.*?在哪里.*?', r'.*?何时.*?', r'.*?怎样.*?',
        r'.*?的区别', r'.*?的差异', r'.*?的不同', r'.*?的异同',
        r'who is.*?', r'what is.*?', r'how to.*?', r'why.*?',
        r'where.*?', r'when.*?', r'difference between.*?',
        # 增加对日期时间询问的模式
        r'几点.*?', r'什么时候.*?', r'哪一天.*?', r'哪一年.*?', 
        r'哪个月.*?', r'今天是.*?', r'现在是.*?', r'几月几号.*?',
        r'what time.*?', r'what date.*?', r'which day.*?', r'when is.*?',
        r'today.*?', r'current time.*?', r'right now.*?', r'this moment.*?'
    ]
    
    for pattern in factual_patterns:
        if re.search(pattern, query_lower):
            # 打印匹配的模式，方便调试
            print(f"查询'{query}'匹配搜索模式: '{pattern}'，需要搜索")
            return True
    
    # 强制让所有包含"今天"、"现在"、"时间"的查询进行搜索
    force_search_keywords = ['今天', '现在', '时间', 'today', 'now', 'time', 'date']
    for keyword in force_search_keywords:
        if keyword in query_lower:
            print(f"查询'{query}'包含强制搜索关键词: '{keyword}'，必须搜索")
            return True
    
    # 如果查询很长（超过50个字符），可能是复杂问题需要搜索
    if len(query) > 50:
        print(f"查询'{query}'长度超过50字符，可能需要搜索")
        return True
    
    return False

# 使用内部搜索函数进行单独搜索，不发送额外消息
async def perform_standalone_search(query: str) -> str:
    """
    执行单独的搜索操作，不发送额外的消息给用户。
    返回搜索结果作为字符串，失败则返回空字符串。
    """
    print("===== SEARCH DEBUG START =====")
    print(f"perform_standalone_search 被调用，查询: '{query}'")
    
    try:
        # 安全设置处理 - 在新版 SDK 中不再直接支持作为参数传递
        # 如果需要调整安全设置，需要在模型配置或其他位置设置
        """
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
                print(f"警告: 格式化 safety_settings 出错 (perform_standalone_search): {e_ss}")
        """
        print("注意: 安全设置参数在新版 SDK 中不再直接支持，已跳过安全设置 (perform_standalone_search)")

        # 准备生成配置
        gen_conf_params = {}
        if generation_config: 
            # 仅添加兼容参数
            for key, value in generation_config.items():
                if not any(x in key.lower() for x in ["safety", "mime", "type", "response"]):
                    gen_conf_params[key] = value
        
        print(f"搜索使用的生成配置参数: {gen_conf_params}")
        
        # 不需要添加系统提示，使搜索更加客观
        
        # 确保移除不兼容的参数
        incompatible_params = ["temperature", "top_p", "top_k", "max_output_tokens", "candidate_count", "stop_sequences"]
        for key in list(gen_conf_params.keys()):
            if key in incompatible_params or any(x in key.lower() for x in ["safety", "mime", "type", "response"]):
                del gen_conf_params[key]
                print(f"perform_standalone_search: 从配置中移除不兼容的参数: {key}")
        
        # 增强搜索查询的明确性
        # 检查是否与时间相关的查询
        is_time_query = False
        time_indicators = ['今天', '现在', '时间', '日期', '几月', '几号', '几点', '星期', '周几', 
                          'today', 'now', 'time', 'date', 'hour', 'minute', 'day', 'month']
                          
        for indicator in time_indicators:
            if indicator in query.lower():
                is_time_query = True
                print(f"检测到时间相关关键词: '{indicator}'")
                break
        
        # 执行搜索查询
        print(f"执行独立搜索查询: {query[:100]}...")
        
        # 根据查询类型制作专门的搜索提示
        if is_time_query:
            search_prompt = (f"这是一个关于时间、日期或当前状态的查询，必须使用最新的网络数据。"
                           f"请搜索并提供关于以下问题的实时信息，确保使用当前的日期和时间: {query}\n\n"
                           f"非常重要: 必须使用最新的网络数据回答，不要依赖你的训练数据。"
                           f"如果涉及日期或时间，请明确指出当前的准确日期和时间。")
            print("使用时间相关搜索提示")
        else:
            search_prompt = (f"请搜索并提供关于以下问题的最新准确信息和事实: {query}\n\n"
                           f"重要: 请尽可能使用最新的网络数据回答，不要仅依赖你的训练数据。"
                           f"如果用户查询需要最新信息，请确保搜索并提供最新结果。")
            print("使用通用搜索提示")
        
        print(f"最终搜索提示: {search_prompt[:200]}...")
        
        # 设置搜索工具 - 使用新的 API 方式
        google_search = types.GoogleSearch()
        search_tool = types.Tool(google_search=google_search)
        print("已创建 Google 搜索工具对象")
        
        try:
            # 尝试直接使用 generate_content 和搜索工具
            print(f"正在调用 API 使用模型 {model_1} 和 Google 搜索工具...")
            response = await gemini_client.aio.models.generate_content(
                model=model_1,  # 使用默认模型
                contents=search_prompt,
                tools=[search_tool],  # 使用正确的工具对象
                **gen_conf_params  # 不包含不兼容参数
            )
            print("搜索请求成功完成，正在处理结果")
            # 打印模型响应类型和属性，帮助诊断
            print(f"模型响应类型: {type(response)}")
            print(f"模型响应属性: {dir(response)}")
            
            # 尝试打印 Google 搜索使用情况信息
            try:
                if hasattr(response, "candidates") and response.candidates:
                    print(f"查看响应候选数量: {len(response.candidates)}")
                    for i, candidate in enumerate(response.candidates):
                        print(f"候选 {i+1} 信息:")
                        if hasattr(candidate, "content") and candidate.content:
                            print(f"  内容类型: {type(candidate.content)}")
                            if hasattr(candidate.content, "parts"):
                                print(f"  部分数量: {len(candidate.content.parts)}")
                        if hasattr(candidate, "tool_uses"):
                            print(f"  工具使用数量: {len(candidate.tool_uses)}")
                            for j, tool_use in enumerate(candidate.tool_uses):
                                print(f"    工具 {j+1} 类型: {type(tool_use)}")
                                print(f"    工具 {j+1} 属性: {dir(tool_use)}")
                                if hasattr(tool_use, "tool_name"):
                                    print(f"    工具 {j+1} 名称: {tool_use.tool_name}")
                                if hasattr(tool_use, "tool_result"):
                                    print(f"    工具 {j+1} 结果类型: {type(tool_use.tool_result)}")
                                    print(f"    工具 {j+1} 结果长度: {len(str(tool_use.tool_result))}")
                                    print(f"    工具 {j+1} 结果前100字符: {str(tool_use.tool_result)[:100]}...")
            except Exception as e_debug:
                print(f"在调试响应时出错: {e_debug}")
        except Exception as e_search:
            print(f"使用 google_search 工具失败: {e_search}")
            print(f"错误类型: {type(e_search)}")
            print(f"完整错误信息: {str(e_search)}")
            try:
                # 退回到不使用工具的方式，但仍尝试执行搜索查询
                fallback_prompt = f"【重要：请执行网络搜索】\n{search_prompt}\n【这是一个需要最新信息的查询】"
                print(f"尝试不使用搜索工具的替代方法...")
                
                # 使用不包含不兼容参数的配置参数
                fallback_params = {}
                for key, value in gen_conf_params.items():
                    fallback_params[key] = value
                
                response = await gemini_client.aio.models.generate_content(
                    model=model_1,  # 使用默认模型
                    contents=fallback_prompt,
                    **fallback_params  # 不包含不兼容参数
                )
                print("使用替代方法完成搜索")
            except Exception as e_fallback:
                print(f"替代搜索方法也失败: {e_fallback}")
                print(f"错误类型: {type(e_fallback)}")
                print(f"完整错误信息: {str(e_fallback)}")
                print("===== SEARCH DEBUG END (失败) =====")
                return f"搜索功能暂时不可用。错误: {str(e_fallback)[:100]}"
        
        # 处理响应
        if hasattr(response, "text") and response.text:
            result = response.text
            print(f"搜索成功，返回结果长度: {len(result)} 字符")
            print(f"结果前200字符: {result[:200]}...")
            print("===== SEARCH DEBUG END (成功) =====")
            return result
        elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            result_text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    result_text += part.text
            print(f"搜索成功，返回结果长度: {len(result_text)} 字符")
            print(f"结果前200字符: {result_text[:200]}...")
            print("===== SEARCH DEBUG END (成功) =====")
            return result_text
        
        print("搜索未返回有效结果")
        print("===== SEARCH DEBUG END (无结果) =====")
        return "搜索未返回有效结果，请重试或改变查询方式。"  # 提供更有用的错误信息
        
    except Exception as e:
        print(f"独立搜索查询失败: {e}")
        print(f"错误类型: {type(e)}")
        print(f"完整错误信息: {str(e)}")
        print("===== SEARCH DEBUG END (异常) =====")
        return f"搜索过程中发生错误: {str(e)[:100]}"  # 返回错误信息而非空字符串

# 新添加的测试搜索功能函数
async def test_search_capability(bot: TeleBot, message: Message):
    """
    专门用于测试 Google 搜索功能的函数。
    此函数会尝试多种方法测试搜索功能，并详细报告结果。
    """
    user_id = message.from_user.id
    user_id_str = str(user_id)
    sent_message = None
    
    try:
        if not gemini_client:
            error_text = "CRITICAL ERROR: Gemini client not initialized in gemini.py."
            print(error_text)
            await bot.reply_to(message, error_text)
            return

        sent_message = await bot.reply_to(message, "正在测试 Google 搜索功能，请稍候...")
        
        # 0. 首先检查搜索配置状态
        from handlers import user_search_settings
        global_search_enabled = conf.get("enable_search", True)
        user_search_enabled = user_search_settings.get(user_id_str, True)
        
        config_status = f"搜索配置状态:\n"
        config_status += f"- 全局搜索启用: {'✅ 是' if global_search_enabled else '❌ 否'}\n"
        config_status += f"- 用户搜索启用: {'✅ 是' if user_search_enabled else '❌ 否'}\n"
        config_status += f"- 搜索最大结果数: {conf.get('search_max_results', 5)}\n"
        config_status += f"- 搜索重试次数: {conf.get('search_retry_count', 2)}\n"
        
        await bot.edit_message_text(
            f"{config_status}\n正在测试组件...", 
            chat_id=sent_message.chat.id, 
            message_id=sent_message.message_id
        )
        
        # 准备一个明确需要搜索的简单查询
        test_query = "今天是几月几号星期几"
        
        # 1. 测试搜索工具创建
        try:
            print("\n===== 测试 #1: 创建搜索工具对象 =====")
            google_search = types.GoogleSearch()
            search_tool = types.Tool(google_search=google_search)
            await bot.edit_message_text(
                f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象", 
                chat_id=sent_message.chat.id, 
                message_id=sent_message.message_id
            )
            print("✅ 搜索工具对象创建成功")
        except Exception as e1:
            error_msg = f"步骤 1/4: ❌ 创建搜索工具对象失败: {str(e1)}"
            await bot.edit_message_text(
                f"{config_status}\n{error_msg}", 
                chat_id=sent_message.chat.id, 
                message_id=sent_message.message_id
            )
            print(f"❌ 错误: {error_msg}")
            return
        
        # 2. 测试模型是否支持搜索工具
        try:
            print("\n===== 测试 #2: 模型支持搜索工具 =====")
            available_models = []
            
            try:
                # 尝试获取可用模型列表
                models_info = await gemini_client.aio.models.list()
                if hasattr(models_info, "models"):
                    available_models = [model.name for model in models_info.models]
                    print(f"可用模型: {available_models}")
            except Exception as e_models:
                print(f"获取模型列表失败: {e_models}")
            
            # 测试模型支持
            test_models = [model_1]
            if model_1 != model_2:
                test_models.append(model_2)
            if model_3 not in test_models:
                test_models.append(model_3)
                
            model_support_results = []
            
            for test_model in test_models:
                try:
                    print(f"测试模型 {test_model} 是否支持搜索工具...")
                    # 简单查询测试
                    await gemini_client.aio.models.generate_content(
                        model=test_model,
                        contents="测试查询",
                        tools=[search_tool]  # 使用正确的工具对象
                        # 移除 max_output_tokens 参数
                    )
                    model_support_results.append(f"✅ 模型 {test_model} 支持搜索工具")
                    print(f"✅ 模型 {test_model} 支持搜索工具")
                except Exception as e_model:
                    model_support_results.append(f"❌ 模型 {test_model} 不支持搜索工具: {str(e_model)}")
                    print(f"❌ 模型 {test_model} 不支持搜索工具: {str(e_model)}")
            
            if any("✅" in result for result in model_support_results):
                await bot.edit_message_text(
                    f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ✅ 至少一个模型支持搜索工具\n" + "\n".join(model_support_results), 
                    chat_id=sent_message.chat.id, 
                    message_id=sent_message.message_id
                )
            else:
                await bot.edit_message_text(
                    f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ❌ 没有模型支持搜索工具\n" + "\n".join(model_support_results), 
                    chat_id=sent_message.chat.id, 
                    message_id=sent_message.message_id
                )
                print("❌ 没有模型支持搜索工具")
                return
        except Exception as e2:
            error_msg = f"步骤 2/4: ❌ 测试模型支持失败: {str(e2)}"
            await bot.edit_message_text(
                f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n{error_msg}", 
                chat_id=sent_message.chat.id, 
                message_id=sent_message.message_id
            )
            print(f"❌ 错误: {error_msg}")
            return
        
        # 3. 执行实际搜索测试
        try:
            print(f"\n===== 测试 #3: 执行实际搜索 '{test_query}' =====")
            await bot.edit_message_text(
                f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ✅ 至少一个模型支持搜索工具\n步骤 3/4: 🔄 正在执行实际搜索...", 
                chat_id=sent_message.chat.id, 
                message_id=sent_message.message_id
            )
            
            # 使用第一个支持搜索的模型
            supported_model = None
            for result in model_support_results:
                if "✅" in result:
                    supported_model = result.split("模型 ")[1].split(" 支持")[0]
                    break
            
            if not supported_model:
                supported_model = model_1  # 默认使用 model_1
            
            # 执行搜索
            print(f"使用模型 {supported_model} 执行搜索")
            
            # 创建搜索参数，不包含不兼容参数
            search_params = {}
            # 如果需要可以添加支持的参数，但不包括 max_output_tokens
            
            response = await gemini_client.aio.models.generate_content(
                model=supported_model,
                contents=f"请执行网络搜索并回答: {test_query}。必须包含你是如何获取这个信息的详细说明。",
                tools=[search_tool],  # 使用正确的工具对象
                **search_params  # 使用不包含不兼容参数的参数
            )
            
            # 分析响应
            search_used = False
            response_text = ""
            
            if hasattr(response, "text"):
                response_text = response.text
            elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text"):
                        response_text += part.text
            
            # 检查响应是否包含搜索结果指示
            search_indicators = [
                "搜索", "查询", "网络", "结果", "搜索结果", "根据搜索", "通过搜索",
                "google", "search", "results", "found", "according to", "web search"
            ]
            
            for indicator in search_indicators:
                if indicator.lower() in response_text.lower():
                    search_used = True
                    break
            
            # 检查是否有工具使用记录
            if hasattr(response, "candidates") and response.candidates:
                for candidate in response.candidates:
                    if hasattr(candidate, "tool_uses") and candidate.tool_uses:
                        search_used = True
                        break
            
            if search_used:
                await bot.edit_message_text(
                    f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ✅ 至少一个模型支持搜索工具\n步骤 3/4: ✅ 成功执行实际搜索\n\n搜索结果摘要:\n{response_text[:300]}...", 
                    chat_id=sent_message.chat.id, 
                    message_id=sent_message.message_id
                )
                print(f"✅ 搜索成功，结果长度: {len(response_text)} 字符")
                print(f"响应摘要: {response_text[:200]}...")
            else:
                await bot.edit_message_text(
                    f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ✅ 至少一个模型支持搜索工具\n步骤 3/4: ⚠️ 搜索执行了但可能未使用搜索工具\n\n响应摘要:\n{response_text[:300]}...", 
                    chat_id=sent_message.chat.id, 
                    message_id=sent_message.message_id
                )
                print(f"⚠️ 响应中未明确指示使用了搜索工具")
                print(f"响应摘要: {response_text[:200]}...")
        except Exception as e3:
            error_msg = f"步骤 3/4: ❌ 执行实际搜索失败: {str(e3)}"
            await bot.edit_message_text(
                f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ✅ 至少一个模型支持搜索工具\n{error_msg}", 
                chat_id=sent_message.chat.id, 
                message_id=sent_message.message_id
            )
            print(f"❌ 错误: {error_msg}")
            return
        
        # 4. 测试 perform_standalone_search 函数
        try:
            print("\n===== 测试 #4: 测试 perform_standalone_search 函数 =====")
            await bot.edit_message_text(
                f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ✅ 至少一个模型支持搜索工具\n步骤 3/4: ✅ 成功执行实际搜索\n步骤 4/4: 🔄 测试 perform_standalone_search 函数...", 
                chat_id=sent_message.chat.id, 
                message_id=sent_message.message_id
            )
            
            # 测试 perform_standalone_search 函数
            search_result = await perform_standalone_search(test_query)
            
            if search_result and len(search_result) > 50:  # 确保结果不是错误消息
                final_message = (
                    f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n"
                    f"步骤 2/4: ✅ 至少一个模型支持搜索工具\n"
                    f"步骤 3/4: ✅ 成功执行实际搜索\n"
                    f"步骤 4/4: ✅ perform_standalone_search 函数成功\n\n"
                    f"🎉 所有测试通过！Google 搜索功能正常工作。\n\n"
                    f"搜索结果示例:\n{search_result[:200]}...\n\n"
                    f"📝 使用提示:\n"
                    f"- 使用 /search 命令可以启用或禁用搜索功能\n"
                    f"- 涉及时间、日期、当前事件的问题会自动触发搜索\n"
                    f"- 包含 '最新'、'现在'、'今天' 等关键词的问题会优先使用搜索\n"
                )
                await bot.edit_message_text(
                    final_message, 
                    chat_id=sent_message.chat.id, 
                    message_id=sent_message.message_id
                )
                print("✅ 所有测试通过")
            else:
                error_details = search_result if search_result else "未返回有效结果"
                await bot.edit_message_text(
                    f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ✅ 至少一个模型支持搜索工具\n步骤 3/4: ✅ 成功执行实际搜索\n步骤 4/4: ❌ perform_standalone_search 函数失败\n\n错误: {error_details}\n\n"
                    f"📝 搜索功能可能部分可用。您可以使用 /search 命令切换搜索功能。", 
                    chat_id=sent_message.chat.id, 
                    message_id=sent_message.message_id
                )
                print(f"❌ perform_standalone_search 测试失败: {error_details}")
        except Exception as e4:
            error_msg = f"步骤 4/4: ❌ 测试 perform_standalone_search 函数失败: {str(e4)}"
            await bot.edit_message_text(
                f"{config_status}\n步骤 1/4: ✅ 成功创建搜索工具对象\n步骤 2/4: ✅ 至少一个模型支持搜索工具\n步骤 3/4: ✅ 成功执行实际搜索\n{error_msg}\n\n"
                f"📝 搜索功能可能部分可用。您可以使用 /search 命令切换搜索功能。", 
                chat_id=sent_message.chat.id, 
                message_id=sent_message.message_id
            )
            print(f"❌ 错误: {error_msg}")
    except Exception as e:
        traceback.print_exc()
        error_msg = f"测试过程中发生错误: {str(e)}"
        if sent_message:
            await bot.edit_message_text(
                f"{error_msg}\n\n您可以使用 /search 命令手动切换搜索功能状态。", 
                chat_id=sent_message.chat.id, 
                message_id=sent_message.message_id
            )
        else:
            await bot.reply_to(message, error_msg)
        print(f"❌ 全局错误: {error_msg}")
