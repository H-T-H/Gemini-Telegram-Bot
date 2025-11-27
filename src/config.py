from google.genai import types

conf = {
    "error_info": "⚠⚠⚠\nAlgo deu errado!\nPor favor, tente alterar seu prompt ou contate o administrador!",
    "before_generate_info": "⏳Gerando⏳",
    "download_pic_notify": "🖼Carregando imagem🖼",
    "model_1": "gemini-2.5-flash",
    "model_2": "gemini-2.5-flash",
    "streaming_update_interval": 0.5,  # Intervalo de atualização de streaming (segundos)
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
]
