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
        "system_prompt_deleted_success": "✅ 系统提示词已删除。后续对话将不使用系统提示词。",
        "search_enabled": "✅ 联网搜索功能已启用",
        "search_disabled": "✅ 联网搜索功能已禁用",
        "search_in_progress": "🔍 正在进行联网搜索，请稍候...",
        "search_failed": "❌ 联网搜索失败，将尝试使用模型知识回答",
        "search_results": "🔍 搜索结果："
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
        "system_prompt_deleted_success": "✅ System prompt has been deleted. Subsequent conversations will not use a system prompt.",
        "search_enabled": "✅ Web search enabled",
        "search_disabled": "✅ Web search disabled",
        "search_in_progress": "🔍 Searching the web, please wait...",
        "search_failed": "❌ Web search failed, will try to answer with model knowledge",
        "search_results": "🔍 Search results:"
    }
}

# 命令描述
command_descriptions = {
    "cn": {  # 中文命令描述
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
        "delete_system_prompt": "删除当前系统提示词",
        "search": "启用/禁用联网搜索",
        "testsearch": "测试 Google 搜索功能"
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
        "delete_system_prompt": "Delete the current system prompt",
        "search": "Enable/disable web search",
        "testsearch": "Test Google search functionality"
    }
}

# 基本配置
conf = {
    "model_1": "gemini-2.5-flash-preview-04-17",
    "model_2": "gemini-2.5-pro-exp-03-25",
    "model_3": "gemini-2.0-flash-exp", # for other uses or as a non-image default if needed
    "imagen_model_name": "gemini-2.0-flash-preview-image-generation", # 使用更新的图像生成模型
    "draw_num_images": 1, # /draw 命令生成的图片数量
    "draw_aspect_ratio": "1:1", # /draw 命令生成图片的宽高比 (e.g., "1:1", "16:9", "3:4")
    "draw_output_mime_type": "image/png", # /draw 命令生成图片的MIME类型
    "streaming_update_interval": 0.5,  # Streaming answer update interval (seconds)
    "default_language": "cn",  # 默认语言 (改回 cn 以保持一致性)
    "enable_search": True,  # 默认启用联网搜索
    "search_temperature": 0.2,  # 搜索时使用较低的温度以获得更准确的回答
    "search_max_results": 5,  # 搜索返回的最大结果数
    "force_search_for_time_queries": True,  # 对时间相关查询强制使用搜索
    "search_debug_mode": True,  # 启用搜索调试模式，打印更多日志
    "search_retry_count": 2,  # 搜索失败时的重试次数
    "search_always_provide_current_time": True,  # 在搜索结果中始终提供当前时间
    "online_search_enabled": True,  # 是否启用网络搜索功能
    "force_search_keywords": [
        # 中文关键词
        "今天", "现在", "最近", "最新", "新闻", "天气", "价格", "股票", 
        "比赛", "时间", "日期", "几点", "几月", "几号", "星期", "周几",
        # 英文关键词
        "today", "now", "recent", "latest", "news", "weather", "price",
        "time", "date", "when", "what day", "what time"
    ]
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
    "temperature": 0.7,  # 默认温度
    "top_p": 0.95,       # 默认 top_p
    "top_k": 40,         # 默认 top_k
    "max_output_tokens": 8192,  # 默认最大输出token数
}

# 搜索特定的生成配置，当执行搜索时使用
search_generation_config = {
    "temperature": 0.2,  # 搜索时使用较低的温度以获得更准确的回答
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

# 搜索关键词配置
search_keywords = {
    "cn": [  # 中文搜索关键词
        '最新', '最近', '今天', '昨天', '本周', '本月', '新闻', '消息', 
        '发布', '发表', '公布', '宣布', '公告', '更新', '升级', '版本',
        '现在', '目前', '当前', '现状', '如今', '时事', '实时', '最新进展',
        '今日', '发生了什么', '查一下', '搜一下', '帮我找', '价格', '股票',
        '天气', '预报', '比赛', '赛程', '比分', '获奖', '获得', '成绩',
        '是谁', '多少', '什么时候', '在哪里', '怎么样', '为什么', '如何',
        '时间', '地点', '人物', '事件', '数据', '统计', '排名', '排行',
        '几月', '几号', '几点', '周几', '星期几', '几周', '几天', '几小时', 
        '日期', '几年', '年份', '月份', '日子', '几分', '几秒', '上午', '下午',
        '凌晨', '上周', '下周', '上个月', '下个月', '去年', '今年', '明年',
        '刚刚', '刚才', '方才', '几分钟前', '几小时前', '几天前', '几周前',
        '节日', '节假日', '假期', '放假', '几点钟', '几时', '几分'
    ],
    "en": [  # 英文搜索关键词
        'latest', 'recent', 'today', 'yesterday', 'current', 'news',
        'update', 'release', 'version', 'weather', 'price', 'stock',
        'match', 'score', 'award', 'result', 'who', 'how', 'why', 'when',
        'where', 'what', 'rank', 'stat', 'data', 'time', 'now', 'date',
        'hour', 'minute', 'second', 'day', 'month', 'year', 'week',
        'morning', 'afternoon', 'evening', 'night', 'holiday', 'schedule',
        'current', 'present', 'moment', 'instant', 'immediately', 'soon',
        'launch', 'release', 'start', 'end', 'open', 'close', 'begin',
        'finish', 'just now', 'minutes ago', 'hours ago', 'days ago',
        "what's the time", "what time is it", "what day is today", "what's today's date"
    ]
}

# 强制搜索关键词配置 - 含有这些关键词的查询将始终进行搜索
force_search_keywords = {
    "cn": ['今天', '现在', '时间', '日期', '几月', '几号', '几点', '星期', '当前'],
    "en": ['today', 'now', 'time', 'date', 'current time', "what's the time", "what day is it"]
}
