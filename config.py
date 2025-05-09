from google import genai
from google.genai import types # Keep this for future use with new SDK
# Remove explicit imports of types which might not exist in the installed version
# from google.generativeai.types import SafetySetting, GenerateContentConfig, HarmCategory, BlockThreshold

# 中英文消息配置
messages = {
    "zh": {  # 中文消息
        "error_info": "⚠️⚠️⚠️\n出现错误！\n请尝试更改您的提示或联系管理员！",
        "before_generate_info": "🤖正在生成🤖",
        "download_pic_notify": "🤖正在加载图片🤖",
        "welcome_message": "欢迎，您现在可以向我提问。\n例如：`鲁迅是谁？`\n\n我已默认启用联网搜索功能，可以帮您查询最新信息。",
        "gemini_usage_tip": "请在 /gemini 后添加您想说的内容。\n例如：`/gemini 鲁迅是谁？`",
        "gemini_pro_usage_tip": "请在 /gemini_pro 后添加您想说的内容。\n例如：`/gemini_pro 鲁迅是谁？`",
        "history_cleared": "您的历史记录已被清除",
        "private_chat_only": "此命令仅适用于私聊！",
        "using_model": "您现在正在使用 ",
        "send_photo_request": "请发送一张照片",
        "draw_usage_tip": "请在 /draw 后添加您想绘制的内容。\n例如：`/draw 给我画一只猫娘。`",
        "drawing": "正在绘制...",
        "generating_answers": "🤖 正在生成回答...",
        "error_details": "错误详情: ",
        "language_switched": "已切换到中文",
        "language_usage_tip": "使用 /language 命令切换语言（中文/英文）",
        "system_prompt_set_usage": "请在 /set_system_prompt 后添加您的系统提示词。\n例如：`/set_system_prompt 你是一个乐于助人的助手。`",
        "system_prompt_set_success": "✅ 系统提示词已设置并应用。后续对话将使用新的提示词。",
        "system_prompt_current": "ℹ️ 当前系统提示词为：",
        "system_prompt_not_set": "ℹ️ 当前未设置系统提示词。",
        "system_prompt_deleted_success": "✅ 系统提示词已删除。后续对话将不使用系统提示词。"
    },
    "en": {  # 英文消息
        "error_info": "⚠️⚠️⚠️\nSomething went wrong!\nPlease try to change your prompt or contact the admin!",
        "before_generate_info": "🤖Generating🤖",
        "download_pic_notify": "🤖Loading picture🤖",
        "welcome_message": "Welcome, you can ask me questions now.\nFor example: `Who is Lu Xun?`\n\nInternet search is enabled by default to help you with the latest information.",
        "gemini_usage_tip": "Please add what you want to say after /gemini.\nFor example: `/gemini Who is Lu Xun?`",
        "gemini_pro_usage_tip": "Please add what you want to say after /gemini_pro.\nFor example: `/gemini_pro Who is Lu Xun?`",
        "history_cleared": "Your history has been cleared",
        "private_chat_only": "This command is only for private chat!",
        "using_model": "Now you are using ",
        "send_photo_request": "Please send a photo",
        "draw_usage_tip": "Please add what you want to draw after /draw.\nFor example: `/draw Draw me a cat girl.`",
        "drawing": "Drawing...",
        "generating_answers": "🤖 Generating answers...",
        "error_details": "Error details: ",
        "language_switched": "Switched to English",
        "language_usage_tip": "Use /language command to switch language (Chinese/English)",
        "system_prompt_set_usage": "Please add your system prompt after /set_system_prompt.\nFor example: `/set_system_prompt You are a helpful assistant.`",
        "system_prompt_set_success": "✅ System prompt has been set and applied. Subsequent conversations will use the new prompt.",
        "system_prompt_current": "ℹ️ Current system prompt is:",
        "system_prompt_not_set": "ℹ️ No system prompt is currently set.",
        "system_prompt_deleted_success": "✅ System prompt has been deleted. Subsequent conversations will not use a system prompt."
    }
}

# 命令描述
command_descriptions = {
    "zh": {  # 中文命令描述
        "start": "开始",
        "gemini": "使用 gemini-2.0-flash-exp",
        "gemini_pro": "使用 gemini-2.5-pro-exp-03-25",
        "draw": "绘制图片",
        "edit": "编辑照片",
        "clear": "清除所有历史记录",
        "switch": "切换默认模型",
        "language": "切换语言(中文/英文)",
        "set_system_prompt": "设置系统提示词",
        "view_system_prompt": "查看当前系统提示词",
        "delete_system_prompt": "删除当前系统提示词"
    },
    "en": {  # 英文命令描述
        "start": "Start",
        "gemini": "using gemini-2.0-flash-exp",
        "gemini_pro": "using gemini-2.5-pro-exp-03-25",
        "draw": "draw picture",
        "edit": "edit photo",
        "clear": "Clear all history",
        "switch": "switch default model",
        "language": "switch language(Chinese/English)",
        "set_system_prompt": "Set the system prompt",
        "view_system_prompt": "View the current system prompt",
        "delete_system_prompt": "Delete the current system prompt"
    }
}

# 基本配置
conf = {
    "model_1": "gemini-2.5-flash-preview-04-17",
    "model_2": "gemini-2.5-pro-exp-03-25",
    "model_3": "gemini-2.0-flash-exp", # for other uses or as a non-image default if needed
    "imagen_model_name": "serviceapi-imagegen@001", # 尝试使用常见的图像生成模型名称
    "draw_num_images": 1, # /draw 命令生成的图片数量
    "draw_aspect_ratio": "1:1", # /draw 命令生成图片的宽高比 (e.g., "1:1", "16:9", "3:4")
    "draw_output_mime_type": "image/png", # /draw 命令生成图片的MIME类型
    "streaming_update_interval": 0.5,  # Streaming answer update interval (seconds)
    "default_language": "zh"  # 默认语言
}

# 使用简单的字典结构定义安全设置，避免依赖特定类型
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    }
]

# 同样使用字典定义生成配置
generation_config = {
    # 移除可能不兼容的响应模态设置
    # "response_modalities": ['Text'],
    # 安全设置应直接传递给模型，而不是嵌套在这里
    # "safety_settings": safety_settings,
}
