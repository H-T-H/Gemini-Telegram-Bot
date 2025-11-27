import argparse
import asyncio
import telebot
from telebot.async_telebot import AsyncTeleBot
import handlers

# Inicializar argumentos
parser = argparse.ArgumentParser()
parser.add_argument("token_tg", help="token do telegram")
parser.add_argument("CHAVE_GOOGLE_GEMINI", help="chave da API do Google Gemini")
opcoes = parser.parse_args()
print("Análise de argumentos concluída.")


async def principal():
    # Inicializar bot
    bot = AsyncTeleBot(opcoes.token_tg)
    await bot.delete_my_commands(scope=None, language_code=None)
    await bot.set_my_commands(
        commands=[
            telebot.types.BotCommand("iniciar", "Iniciar"),
            telebot.types.BotCommand("gemini", "Conversar com gemini"),
            telebot.types.BotCommand("limpar", "Limpar todo o histórico"),
            telebot.types.BotCommand("reiniciar", "Reiniciar modelo"),
        ]
    )
    print("Bot inicializado.")

    # Registrar manipuladores
    handlers.registrar_manipuladores(bot, opcoes.CHAVE_GOOGLE_GEMINI)
    print("Manipuladores registrados.")

    # Executar bot
    await bot.infinity_polling()


if __name__ == "__main__":
    asyncio.run(principal())
