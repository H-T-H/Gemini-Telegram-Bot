import io
import time
import traceback
import sys
from PIL import Image
from telebot.types import Message
from md2tgmd import escape
from telebot import TeleBot
from config import conf, generation_config, draw_generation_config, lang_settings, DEFAULT_SYSTEM_PROMPT
from google import genai
from google.genai import types

gemini_draw_dict = {}
gemini_chat_dict = {}
gemini_pro_chat_dict = {}
default_model_dict = {}
user_language_dict = {}  # 新增：用户语言偏好字典
user_system_prompt_dict = {}  # 用户系统提示词字典

model_1                 =       conf["model_1"]
model_2                 =       conf["model_2"]
model_3                 =       conf["model_3"]
default_language        =       conf["default_language"]
error_info              =       conf["error_info"]
before_generate_info    =       conf["before_generate_info"]
download_pic_notify     =       conf["download_pic_notify"]

search_tool = {'google_search': {}}

client = genai.Client(api_key=sys.argv[2])

# 根据用户ID获取语言设置
def get_user_lang(user_id):
    user_id_str = str(user_id)
    if user_id_str not in user_language_dict:
        user_language_dict[user_id_str] = default_language
    return user_language_dict[user_id_str]

# 获取用户对应语言的提示文案
def get_user_text(user_id, text_key):
    lang = get_user_lang(user_id)
    return lang_settings[lang].get(text_key, lang_settings[default_language].get(text_key, ""))

# 切换用户语言
async def switch_language(bot: TeleBot, message: Message):
    user_id_str = str(message.from_user.id)
    current_lang = get_user_lang(user_id_str)
    
    # 切换语言
    new_lang = "en" if current_lang == "zh" else "zh"
    user_language_dict[user_id_str] = new_lang
    
    # 发送语言切换确认消息
    await bot.reply_to(message, lang_settings[new_lang]["language_switched"])

# 获取当前语言状态
async def get_language(bot: TeleBot, message: Message):
    user_id_str = str(message.from_user.id)
    current_lang = get_user_lang(user_id_str)
    await bot.reply_to(message, lang_settings[current_lang]["language_current"])

# 获取用户系统提示词，如果没有设置则返回默认值
def get_system_prompt(user_id):
    user_id_str = str(user_id)
    return user_system_prompt_dict.get(user_id_str, DEFAULT_SYSTEM_PROMPT)

# 设置用户系统提示词
async def set_system_prompt(bot: TeleBot, message: Message, prompt: str):
    user_id_str = str(message.from_user.id)
    user_system_prompt_dict[user_id_str] = prompt
    
    # 清除该用户的聊天历史，以便新的系统提示词生效
    if user_id_str in gemini_chat_dict:
        del gemini_chat_dict[user_id_str]
    if user_id_str in gemini_pro_chat_dict:
        del gemini_pro_chat_dict[user_id_str]
    
    confirmation_msg = f"{get_user_text(message.from_user.id, 'system_prompt_set')}\n{prompt}"
    await bot.reply_to(message, confirmation_msg)

# 删除用户系统提示词
async def delete_system_prompt(bot: TeleBot, message: Message):
    user_id_str = str(message.from_user.id)
    if user_id_str in user_system_prompt_dict:
        del user_system_prompt_dict[user_id_str]
    
    # 清除该用户的聊天历史，以便移除系统提示词生效
    if user_id_str in gemini_chat_dict:
        del gemini_chat_dict[user_id_str]
    if user_id_str in gemini_pro_chat_dict:
        del gemini_pro_chat_dict[user_id_str]
    
    await bot.reply_to(message, get_user_text(message.from_user.id, 'system_prompt_deleted'))

# 重置用户系统提示词为默认值
async def reset_system_prompt(bot: TeleBot, message: Message):
    user_id_str = str(message.from_user.id)
    user_system_prompt_dict[user_id_str] = DEFAULT_SYSTEM_PROMPT
    
    # 清除该用户的聊天历史，以便默认系统提示词生效
    if user_id_str in gemini_chat_dict:
        del gemini_chat_dict[user_id_str]
    if user_id_str in gemini_pro_chat_dict:
        del gemini_pro_chat_dict[user_id_str]
    
    await bot.reply_to(message, get_user_text(message.from_user.id, 'system_prompt_reset'))

# 显示当前系统提示词
async def show_system_prompt(bot: TeleBot, message: Message):
    user_id = message.from_user.id
    prompt = get_system_prompt(user_id)
    await bot.reply_to(message, f"{get_user_text(user_id, 'system_prompt_current')}\n{prompt}")

async def gemini_stream(bot:TeleBot, message:Message, m:str, model_type:str):
    sent_message = None
    try:
        sent_message = await bot.reply_to(message, "🤖 Generating answers...")

        chat = None
        if model_type == model_1:
            chat_dict = gemini_chat_dict
        else:
            chat_dict = gemini_pro_chat_dict

        if str(message.from_user.id) not in chat_dict:
            # 获取用户系统提示词
            system_prompt = get_system_prompt(message.from_user.id)
            
            # 创建聊天会话，并使用系统提示词
            try:
                chat = client.aio.chats.create(
                    model=model_type,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[search_tool]
                    )
                )
                chat_dict[str(message.from_user.id)] = chat
            except Exception as e:
                print(f"Failed to set system prompt in chat creation: {e}")
                # 如果设置系统提示词失败，尝试创建没有系统提示词的聊天
                chat = client.aio.chats.create(
                    model=model_type, 
                    config={'tools': [search_tool]}
                )
                chat_dict[str(message.from_user.id)] = chat
        else:
            chat = chat_dict[str(message.from_user.id)]
            
        # 根据用户语言添加中文回复请求
        lang = get_user_lang(message.from_user.id)
        if lang == "zh" and "用中文回复" not in m and "中文回答" not in m:
            m += "，请用中文回复"

        response = await chat.send_message_stream(m)

        full_response = ""
        last_update = time.time()
        update_interval = conf["streaming_update_interval"]

        async for chunk in response:
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
                        else:
                            if "message is not modified" not in str(e).lower():
                                print(f"Error updating message: {e}")
                    last_update = current_time

        try:
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

async def gemini_edit(bot: TeleBot, message: Message, m: str, photo_file: bytes):
    image = Image.open(io.BytesIO(photo_file))
    try:
        response = await client.aio.models.generate_content(
            model=model_3,
            contents=[m, image],
            config=types.GenerateContentConfig(**generation_config)
        )
    except Exception as e:
        await bot.send_message(message.chat.id, e.str())
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            await bot.send_message(message.chat.id, escape(part.text), parse_mode="MarkdownV2")
        elif part.inline_data is not None:
            photo = part.inline_data.data
            await bot.send_photo(message.chat.id, photo)

async def gemini_image_understand(bot: TeleBot, message: Message, photo_file: bytes, prompt: str = ""):
    sent_message = None
    current_model_name_for_error_msg = "configured model" # Placeholder for error messages
    try:
        # Determine the model and chat dictionary based on user's default setting
        current_model_name = model_1 # Default to model_1
        chat_dict_to_use = gemini_chat_dict
        if str(message.from_user.id) in default_model_dict and not default_model_dict[str(message.from_user.id)]:
            current_model_name = model_2
            chat_dict_to_use = gemini_pro_chat_dict
        current_model_name_for_error_msg = current_model_name

        # 使用本地化的提示
        understanding_msg = f"🤖 {get_user_text(message.from_user.id, 'before_generate_info')} {current_model_name}..."
        sent_message = await bot.reply_to(message, understanding_msg)
        
        # Load and optimize the image to reduce server load
        image_pil = Image.open(io.BytesIO(photo_file))
        
        # Resize large images to reduce processing load
        max_dimension = 1024  # Maximum dimension for either width or height
        if max(image_pil.width, image_pil.height) > max_dimension:
            # Calculate new dimensions while preserving aspect ratio
            if image_pil.width > image_pil.height:
                new_width = max_dimension
                new_height = int(image_pil.height * (max_dimension / image_pil.width))
            else:
                new_height = max_dimension
                new_width = int(image_pil.width * (max_dimension / image_pil.height))
            # Resize the image
            image_pil = image_pil.resize((new_width, new_height), Image.LANCZOS)
        
        # Prepare contents for the chat session: a list containing the PIL Image object and the prompt string.
        current_contents_for_chat = [image_pil] # Start with the image
        
        # 根据用户语言选择默认提示和回复语言请求
        lang = get_user_lang(message.from_user.id)
        if prompt: # If user provided a caption, add it to the contents
            # 如果用户提供了描述，就直接使用
            if lang == "zh":
                # 中文用户：如果提示中没有包含语言请求，自动添加中文回复请求
                if "用中文回复" not in prompt and "中文回答" not in prompt:
                    prompt += "，请用中文回复"
            current_contents_for_chat.append(prompt)
        else: # If no caption, add a generic prompt based on user language
            if lang == "zh":
                current_contents_for_chat.append("描述这张图片，请用中文回复")
            else:
                current_contents_for_chat.append("Describe this image")
        
        # Get or create chat session for the selected model
        chat_session = None
        if str(message.from_user.id) not in chat_dict_to_use:
            # 获取用户系统提示词
            system_prompt = get_system_prompt(message.from_user.id)
            
            # 创建聊天会话，使用系统提示词
            try:
                # 创建聊天会话，并正确设置系统提示词
                chat_session = client.aio.chats.create(
                    model=current_model_name, 
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        **generation_config
                    )
                )
                chat_dict_to_use[str(message.from_user.id)] = chat_session
            except Exception as e:
                print(f"Failed to set system prompt for image understanding: {e}")
                # 如果设置系统提示词失败，尝试不使用系统提示词创建聊天会话
                chat_session = client.aio.chats.create(
                    model=current_model_name, 
                    config=generation_config
                )
                chat_dict_to_use[str(message.from_user.id)] = chat_session
        else:
            chat_session = chat_dict_to_use[str(message.from_user.id)]
        
        # Use `content` (singular) keyword for send_message_stream with a list of parts.
        response_stream = await chat_session.send_message_stream(current_contents_for_chat)
        
        full_response_text = ""
        last_update_time = time.time()
        update_interval = conf.get("streaming_update_interval", 1.0) # Default to 1 second
        last_block_reason = None
        last_finish_reason_safety = False

        async for chunk in response_stream:
            if hasattr(chunk, 'text') and chunk.text:
                full_response_text += chunk.text
            
            # Check for blocking information in the chunk
            if hasattr(chunk, 'prompt_feedback') and chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                last_block_reason = chunk.prompt_feedback.block_reason
                # You might want to break here if a block_reason is found, depending on desired behavior
                # For now, we just record it and let the text accumulate or not.
            if hasattr(chunk, 'candidates') and chunk.candidates and hasattr(chunk.candidates[0], 'finish_reason') and str(chunk.candidates[0].finish_reason).upper() == 'SAFETY':
                last_finish_reason_safety = True
                # Similar to block_reason, decide if to break or just note.

            current_time = time.time()
            if current_time - last_update_time >= update_interval and full_response_text: # Only edit if there is text to show
                try:
                    await bot.edit_message_text(
                        escape(full_response_text + "..."), # Indicate streaming with ellipses
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id,
                        parse_mode="MarkdownV2"
                    )
                    last_update_time = current_time
                except Exception as e_stream:
                    if "message is not modified" not in str(e_stream).lower() and "parse markdown" not in str(e_stream).lower():
                        print(f"Streaming update error for image understanding: {e_stream}")
                    elif "parse markdown" in str(e_stream).lower(): # Attempt to send raw text if markdown parsing fails
                        await bot.edit_message_text(full_response_text + "...", chat_id=sent_message.chat.id, message_id=sent_message.message_id)
                        last_update_time = current_time # Ensure this line is indented correctly under the elif

        # Final update for the completed response
        if full_response_text:
            try:
                await bot.edit_message_text(
                    escape(full_response_text), # Send the fully accumulated and escaped text
                    chat_id=sent_message.chat.id,
                    message_id=sent_message.message_id,
                    parse_mode="MarkdownV2"
                )
            except Exception: # Fallback to sending raw text if markdown parsing fails on the final message
                await bot.edit_message_text(full_response_text, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        elif last_block_reason or last_finish_reason_safety: # If no text, but we detected a block/safety stop
            block_message = "🤖 The response for the image was blocked."
            if last_block_reason:
                block_message += f" Reason: {last_block_reason}."
            if last_finish_reason_safety and not last_block_reason:
                block_message += " Finished due to safety settings."
            await bot.edit_message_text(block_message, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        else: # No text and no specific block reason found on chunks
            await bot.edit_message_text(
                f"🤖 Model {current_model_name} did not provide a text response for the image.",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )

    # Removed specific catch for BlockedPromptException due to AttributeError
    # General API errors will be caught by the Exception block below.
    # If specific API errors for blocking need to be handled, they should be instances of genai.errors.APIError.

    except Exception as e: # General exception handler, including genai.errors.APIError
        traceback.print_exc()
        error_detail_str = str(e)
        # Check for the specific API error about text-only output
        specific_api_error_check = ("This model only supports text output." in error_detail_str or \
                                      "only supports text and HHFM function calling" in error_detail_str) and \
                                     ("INVALID_ARGUMENT" in error_detail_str.upper() or isinstance(e, getattr(genai.errors, 'InvalidArgumentError', Exception)))
        
        error_message = f"{get_user_text(message.from_user.id, 'error_info')}\nError details: {error_detail_str}"
        if specific_api_error_check: # If it is the text-only error, provide a more helpful message
            lang = get_user_lang(message.from_user.id)
            if lang == "zh":
                error_message = (
                    f"{get_user_text(message.from_user.id, 'error_info')}\n" 
                    f"API错误: {error_detail_str}\n" 
                    f"此错误表明模型 '{current_model_name_for_error_msg}'（如在config.py中配置的）"
                    f"不支持直接图像输入，或输入格式/部分对该模型不正确。"
                    f"请确保 '{model_1}' 和 '{model_2}' 在config.py中是多模态模型名称（例如 'gemini-1.5-flash-latest'），"
                    f"能够以这种方式处理图像和文本组合。如果您使用的是旧模型如 'gemini-pro'，它将无法处理图像。"
                )
            else:
                error_message = (
                    f"{get_user_text(message.from_user.id, 'error_info')}\n" 
                    f"API Error: {error_detail_str}\n" 
                    f"This error suggests that the model '{current_model_name_for_error_msg}' (as configured in your config.py) "
                    f"does not support direct image input as attempted, or the input format/parts are incorrect for this model. "
                    f"Please ensure that '{model_1}' and '{model_2}' in your config.py are multimodal model names (e.g., 'gemini-1.5-flash-latest') "
                    f"that can process images and text combined in this manner. If you are using an older model like 'gemini-pro', it will not work with images."
                )
        
        if sent_message: # If a message was already sent to the user, edit it with the error
            await bot.edit_message_text(error_message, chat_id=sent_message.chat.id, message_id=sent_message.message_id)
        else: # Otherwise, reply to the original message with the error
            await bot.reply_to(message, error_message)

async def gemini_draw(bot:TeleBot, message:Message, m:str):
    chat_dict = gemini_draw_dict
    if str(message.from_user.id) not in chat_dict:
        chat = client.aio.chats.create(
            model=model_3,
            config=draw_generation_config,
        )
        chat_dict[str(message.from_user.id)] = chat
    else:
        chat = chat_dict[str(message.from_user.id)]

    response = await chat.send_message(m)
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            text = part.text
            while len(text) > 4000:
                await bot.send_message(message.chat.id, escape(text[:4000]), parse_mode="MarkdownV2")
                text = text[4000:]
            if text:
                await bot.send_message(message.chat.id, escape(text), parse_mode="MarkdownV2")
        elif part.inline_data is not None:
            photo = part.inline_data.data
            await bot.send_photo(message.chat.id, photo)
