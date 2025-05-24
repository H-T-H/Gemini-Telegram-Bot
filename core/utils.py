import html

def escape_html(text: str) -> str:
    """Escapes text for use in Telegram HTML parse mode."""
    return html.escape(text, quote=False) # quote=False keeps " and ' as is, often fine for Telegram
