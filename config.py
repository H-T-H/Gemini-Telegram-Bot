from google.generativeai import types as genai_types # Updated import
conf = {
    "error_info":           "⚠️⚠️⚠️\nSomething went wrong !\nplease try to change your prompt or contact the admin !",
    "before_generate_info": "🤖Generating🤖",
    "download_pic_notify":  "🤖Loading picture🤖",
    "model_1":              "gemini-2.5-flash-preview-05-20",
    "model_2":              "gemini-2.5-pro-preview-05-06",
    "model_3":              "gemini-2.0-flash-preview-image-generation",#for draw
    "streaming_update_interval": 0.5,  # Streaming answer update interval (seconds)
}

# Old safety_settings and generation_config removed.

# New Safety Settings for google-genai SDK
# Valid thresholds: BLOCK_NONE, BLOCK_ONLY_HIGH, BLOCK_MEDIUM_AND_ABOVE, BLOCK_LOW_AND_ABOVE
NEW_SAFETY_SETTINGS = [
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    genai_types.SafetySetting(
        category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    # The old config also had HARM_CATEGORY_CIVIC_INTEGRITY. This is not in the standard 4 for Gemini.
    # If it's needed, it would require checking if it's supported by the specific models being used.
    # For now, focusing on the common 4.
]
