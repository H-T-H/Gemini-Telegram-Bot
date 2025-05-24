from core.ai_client import get_model
from google.generativeai import types as genai_types # Ensure this import is present
from google.api_core import exceptions as google_exceptions # For specific error types
from config import NEW_SAFETY_SETTINGS # Added import

async def stream_text(kind: str, prompt: str, history: list[dict[str, any]] | None = None):
    model = get_model(kind)
    
    contents_payload = []
    if history:
        contents_payload.extend(history)
    contents_payload.append({'role': 'user', 'parts': [{'text': prompt}]})
    
    # Define request_options, e.g., with a timeout.
    # This should ideally be configurable or passed in if it varies.
    request_options = genai_types.RequestOptions(timeout=90) # Default timeout
    
    # Using generate_content_async with stream=True for async streaming
    async for chunk in await model.generate_content_async(
        contents=contents_payload, # Changed from just 'prompt'
        stream=True,
        request_options=request_options,
        safety_settings=NEW_SAFETY_SETTINGS # Added safety_settings
    ):
        # Ensure the chunk has text and it's not empty
        if hasattr(chunk, 'text') and chunk.text:
            yield chunk.text

async def safe_generate_stream(prompt: str, history: list[dict[str, any]] | None = None):
    """
    Attempts to stream content using the 'pro' model, with a fallback to the 'flash' model
    if a PermissionDeniedError (or similar access issue) occurs with the 'pro' model.
    Includes history, safety settings, and timeout.
    """
    current_kind = "pro"
    model = get_model(kind=current_kind)
    
    contents_payload = []
    if history:
        contents_payload.extend(history)
    contents_payload.append({'role': 'user', 'parts': [{'text': prompt}]})

    request_options = genai_types.RequestOptions(timeout=90)

    try:
        async for chunk in await model.generate_content_async(
            contents=contents_payload,
            stream=True,
            request_options=request_options,
            safety_settings=NEW_SAFETY_SETTINGS
        ):
            if hasattr(chunk, 'text') and chunk.text: # Ensure text exists and is not empty
                yield chunk.text
    except google_exceptions.PermissionDenied as e: # Catching PermissionDenied
        print(f"Permission denied for 'pro' model: {e}. Falling back to 'flash' model.")
        # Fallback to 'flash' model
        current_kind = "flash"
        model = get_model(kind=current_kind)
        try: # Nested try for the fallback call
            async for chunk in await model.generate_content_async(
                contents=contents_payload, # Re-use the same payload
                stream=True,
                request_options=request_options, # Re-use same options
                safety_settings=NEW_SAFETY_SETTINGS 
            ):
                if hasattr(chunk, 'text') and chunk.text: # Ensure text exists and is not empty
                    yield chunk.text
        except Exception as fallback_e: # Handle potential errors in fallback
            print(f"Error during fallback to '{current_kind}' model: {fallback_e}")
            # Optionally, re-raise or yield a specific error message chunk
            # For now, just prints and ends the stream if fallback fails.
            # Or, yield an error message:
            yield f"\n⚠️ An error occurred with the fallback model: {str(fallback_e)}\n"
    # Note: The original plan mentioned catching a more specific error from google.generativeai.errors.
    # `google.api_core.exceptions.PermissionDenied` is used here as a common and suitable choice.
