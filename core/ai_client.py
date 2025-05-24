import os
from google import genai
from google.genai import types # type: ignore

# Model names updated based on previous plan's findings and current config.
_MODELS = {
    "flash": "gemini-2.5-flash-preview-05-20", # Was model_1
    "pro":   "gemini-2.5-pro-preview-05-06",   # Was model_2
    "image": "gemini-2.0-flash-preview-image-generation", # Was model_3
}

def get_gemini_client() -> genai.Client:
    # Assuming GOOGLE_GEMINI_KEY will be set as an environment variable.
    api_key = os.getenv("GOOGLE_GEMINI_KEY")
    if not api_key:
        raise ValueError("GOOGLE_GEMINI_KEY environment variable not set.")
    return genai.Client(
        api_key=api_key
    )

def get_model(kind: str, client: genai.Client | None = None) -> genai.GenerativeModel:
    if client is None:
        client = get_gemini_client()
    
    model_name = _MODELS.get(kind)
    if not model_name:
        raise ValueError(f"Unknown model kind: {kind}. Available kinds are: {list(_MODELS.keys())}")

    return client.generative_model(model_name)
