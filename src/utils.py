from config import conf
from google.genai.chats import AsyncChat
from google import genai
import sys
from asyncio import Lock
from typing import Tuple

dict_chat: dict[int, list[AsyncChat, Lock]] = {}
cliente = genai.Client(api_key=sys.argv[2])
ferramenta_busca = {'google_search': {}}


async def iniciar_usuario(id_usuario: int) -> Tuple[AsyncChat, Lock]:
    """Se o usuário não existir no dict_chat, cria um

    Args:
        id_usuario: (int): id do usuário

    Returns:
        AsyncChat: sessão de chat do usuário
        Lock:      lock do chat do usuário
    """
    if id_usuario not in dict_chat:#Se não encontrar o chat do usuário
        chat = cliente.aio.chats.create(model=conf['modelo_1'], config={'tools': [ferramenta_busca]})
        lock = Lock()
        dict_chat[id_usuario] = [chat, lock]  
        return chat, lock
    else:
        return dict_chat[id_usuario][0], dict_chat[id_usuario][1]
