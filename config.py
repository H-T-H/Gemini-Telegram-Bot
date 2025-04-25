from google.genai import types

# 中英文消息配置
messages = {
    "zh": {  # 中文消息
        "error_info": "⚠️⚠️⚠️\n出现错误！\n请尝试更改您的提示或联系管理员！",
        "before_generate_info": "🤖正在生成🤖",
        "download_pic_notify": "🤖正在加载图片🤖",
        "welcome_message": "欢迎，您现在可以向我提问。\n例如：`约翰·列侬是谁？`",
        "gemini_usage_tip": "请在 /gemini 后添加您想说的内容。\n例如：`/gemini 约翰·列侬是谁？`",
        "gemini_pro_usage_tip": "请在 /gemini_pro 后添加您想说的内容。\n例如：`/gemini_pro 约翰·列侬是谁？`",
        "history_cleared": "您的历史记录已被清除",
        "private_chat_only": "此命令仅适用于私聊！",
        "using_model": "您现在正在使用 ",
        "send_photo_request": "请发送一张照片",
        "draw_usage_tip": "请在 /draw 后添加您想绘制的内容。\n例如：`/draw 给我画一只猫。`",
        "drawing": "正在绘制...",
        "generating_answers": "🤖 正在生成回答...",
        "error_details": "错误详情: ",
        "language_switched": "已切换到中文",
        "language_usage_tip": "使用 /language 命令切换语言（中文/英文）"
    },
    "en": {  # 英文消息
        "error_info": "⚠️⚠️⚠️\nSomething went wrong!\nPlease try to change your prompt or contact the admin!",
        "before_generate_info": "🤖Generating🤖",
        "download_pic_notify": "🤖Loading picture🤖",
        "welcome_message": "Welcome, you can ask me questions now.\nFor example: `Who is John Lennon?`",
        "gemini_usage_tip": "Please add what you want to say after /gemini.\nFor example: `/gemini Who is John Lennon?`",
        "gemini_pro_usage_tip": "Please add what you want to say after /gemini_pro.\nFor example: `/gemini_pro Who is John Lennon?`",
        "history_cleared": "Your history has been cleared",
        "private_chat_only": "This command is only for private chat!",
        "using_model": "Now you are using ",
        "send_photo_request": "Please send a photo",
        "draw_usage_tip": "Please add what you want to draw after /draw.\nFor example: `/draw Draw me a cat.`",
        "drawing": "Drawing...",
        "generating_answers": "🤖 Generating answers...",
        "error_details": "Error details: ",
        "language_switched": "Switched to English",
        "language_usage_tip": "Use /language command to switch language (Chinese/English)"
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
        "language": "切换语言(中文/英文)"
    },
    "en": {  # 英文命令描述
        "start": "Start",
        "gemini": "using gemini-2.0-flash-exp",
        "gemini_pro": "using gemini-2.5-pro-exp-03-25",
        "draw": "draw picture",
        "edit": "edit photo",
        "clear": "Clear all history",
        "switch": "switch default model",
        "language": "switch language(Chinese/English)"
    }
}

# 基本配置
conf = {
    "model_1": "gemini-2.5-flash-preview-04-17",
    "model_2": "gemini-2.5-pro-exp-03-25",
    "streaming_update_interval": 0.5,  # Streaming answer update interval (seconds)
    "default_language": "zh"  # 默认语言
}

safety_settings = [
    types.SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_HATE_SPEECH",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_DANGEROUS_CONTENT",
        threshold="BLOCK_NONE",
    ),
    types.SafetySetting(
        category="HARM_CATEGORY_CIVIC_INTEGRITY",
        threshold="BLOCK_NONE",
    )
]

generation_config = types.GenerateContentConfig(
    response_modalities=['Text', 'Image'],
    safety_settings=safety_settings,
)
