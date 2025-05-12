from google.genai import types

# 语言配置
lang_settings = {
    "zh": {
        "error_info": "⚠️⚠️⚠️\n出现错误！\n请尝试更改您的提示或联系管理员！",
        "before_generate_info": "🤖正在生成回答🤖",
        "download_pic_notify": "🤖正在加载图片🤖",
        "welcome_message": "欢迎，您现在可以向我提问。\n例如：`谁是约翰列侬？`",
        "gemini_prompt_help": "请在 /gemini 后添加您想说的内容。\n例如：`/gemini 谁是约翰列侬？`",
        "gemini_pro_prompt_help": "请在 /gemini_pro 后添加您想说的内容。\n例如：`/gemini_pro 谁是约翰列侬？`",
        "history_cleared": "您的聊天历史已清除",
        "private_chat_only": "此命令仅适用于私人聊天！",
        "now_using_model": "现在您正在使用",
        "send_photo_prompt": "请发送一张照片",
        "drawing_message": "正在绘图...",
        "draw_prompt_help": "请在 /draw 后添加您想绘制的内容。\n例如：`/draw 给我画一只猫娘。`",
        "language_switched": "已切换到中文",
        "language_current": "当前语言：中文"
    },
    "en": {
        "error_info": "⚠️⚠️⚠️\nSomething went wrong!\nPlease try to change your prompt or contact the admin!",
        "before_generate_info": "🤖Generating🤖",
        "download_pic_notify": "🤖Loading picture🤖",
        "welcome_message": "Welcome, you can ask me questions now.\nFor example: `Who is john lennon?`",
        "gemini_prompt_help": "Please add what you want to say after /gemini.\nFor example: `/gemini Who is john lennon?`",
        "gemini_pro_prompt_help": "Please add what you want to say after /gemini_pro.\nFor example: `/gemini_pro Who is john lennon?`",
        "history_cleared": "Your history has been cleared",
        "private_chat_only": "This command is only for private chat!",
        "now_using_model": "Now you are using",
        "send_photo_prompt": "Please send a photo",
        "drawing_message": "Drawing...",
        "draw_prompt_help": "Please add what you want to draw after /draw.\nFor example: `/draw draw me a cat.`",
        "language_switched": "Switched to English",
        "language_current": "Current language: English"
    }
}

conf = {
    "default_language": "zh",  # 默认使用中文
    "model_1": "gemini-1.5-flash",
    "model_2": "gemini-2.5-pro-exp-03-25",  # 恢复默认模型
    "model_3": "gemini-2.0-flash-exp",  # for draw
    "streaming_update_interval": 0.5,  # Streaming answer update interval (seconds)
}

# 从默认语言中获取提示文案
default_lang = conf["default_language"]
conf.update(lang_settings[default_lang])

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
    response_modalities=['Text'],
    safety_settings=safety_settings,
)
