from google.genai import types

conf = {
    "error_info":           "⚠️⚠️⚠️\nSomething went wrong !\nplease try to change your prompt or contact the admin !",
    "before_generate_info": "🤖Generating🤖",
    "download_pic_notify":  "🤖Loading picture🤖",
    "model_1":              "gemini-3-flash-preview",
    "model_2":              "gemini-2.5-pro",
    "streaming_update_interval": 0.5,  # Streaming answer update interval (seconds)
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
