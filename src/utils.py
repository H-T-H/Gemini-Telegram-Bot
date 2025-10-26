from config import conf, chat_dict, client, search_tool
from google.genai.chats import AsyncChat

async def init_user(user_id: int) -> AsyncChat:
    """if user not exist in chat_dict, create one
    
    Args:
        user_id: (int): user's id

    Returns:
        AsyncChat: user's chat session
    """
    if user_id not in chat_dict:#if not find user's chat
        chat = client.aio.chats.create(model=conf["model_1"], config={'tools': [search_tool]})
        chat_dict[user_id] = chat
    else:
        chat = chat_dict[user_id]
    return chat

async def get_model(user_id: int) -> str:
    """Get user's current model by deal with message. If chat no found, create one.
    
    Args:
        user_id: (int): user's id

    Returns:
        str: the model name
    """
    chat = await init_user(user_id)
    return chat._model

async def update_chat(user_id: int, model_name: str) -> AsyncChat:
    """Update user's chat session, keep the history
    
    Args:
        user_id (int): user's id
        model_name (str): target model

    Returns:
        AsyncChat: async chat session
    """
    old_chat = await init_user(user_id)
    history = old_chat.get_history()
    new_chat = client.aio.chats.create(model=model_name, history = history, config={'tools': [search_tool]})
    chat_dict[user_id] = new_chat

    return new_chat
