from config import conf
from google.genai.chats import AsyncChat
from google import genai
import sys
from asyncio import Lock
from typing import Tuple

chat_dict: dict[int, list[AsyncChat, Lock]] = {}
client = genai.Client(api_key=sys.argv[2])
search_tool = {'google_search': {}}

async def init_user(user_id: int) -> Tuple[AsyncChat, Lock]:
    """if user not exist in chat_dict, create one
    
    Args:
        user_id: (int): user's id

    Returns:
        AsyncChat: user's chat session
        Lock:      user's chat lock
    """
    if user_id not in chat_dict:#if not find user's chat
        chat = client.aio.chats.create(model=conf["model_1"], config={'tools': [search_tool]})
        lock = Lock()
        chat_dict[user_id] = [chat, lock]
    else:
        chat, lock = chat_dict[user_id]
    return chat, lock

async def switch_model(user_id: int) -> str:
    """Update user's chat session, keep the history
    
    Args:
        user_id (int): user's id

    Returns:
        str: chat's current model
    """
    old_chat, lock = await init_user(user_id)

    await lock.acquire()

    if(old_chat._model == conf["model_1"]):
        new_model = conf["model_2"]
    else:
        new_model = conf["model_1"]
    history = old_chat.get_history()
    new_chat = client.aio.chats.create(model=new_model, history = history, config={'tools': [search_tool]})
    chat_dict[user_id] = [new_chat, lock]

    lock.release()

    return new_model

async def clear_history(user_id: int) -> None:
    """clear user's history
    
    Args:
        user_id (int): user's id

    Returns:
        None
    """
    old_chat, lock = await init_user(user_id)

    await lock.acquire()

    model = old_chat._model
    new_chat = client.aio.chats.create(model=model, config={'tools': [search_tool]})
    chat_dict[user_id] = [new_chat, lock]
    
    lock.release()
