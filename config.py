from google.genai import types
conf = {
    "error_info":           "⚠️⚠️⚠️\nЧто-то пошло не так!\nПопробуйте изменить запрос или свяжитесь с администратором!",
    "before_generate_info": "🤖Генерация🤖",
    "download_pic_notify":  "🤖Загружаю изображение🤖",
    "model_1":              "gemini-2.5-flash",
    "model_2":              "gemini-2.5-pro",
    "model_3":              "gemini-2.0-flash-preview-image-generation",#for draw
    "streaming_update_interval": 0.5,  # Интервал обновления потока ответа (секунды)
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
