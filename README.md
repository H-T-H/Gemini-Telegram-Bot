# Gemini_Telegram_Bot
A Telegram Bot using Gemini API
# How to Install
## (1) Under Linux Environment
1. Install dependencies
```
pip install -r requirements.txt
```
2. Obtain Telegram Bot API at [BotFather](https://t.me/BotFather)
3. Get Gemini API keys from [Google AI Studio](https://makersuite.google.com/app/apikey)
4. Run
```
python main.py ${Telegram Bot API} ${Gemini API keys}
```
## (二)Deploy using docker
```
docker run -d -e TELEGRAM_BOT_API_KEY={replace with your Telegram Bot API} -e GEMINI_API_KEYS={replace with your Gemini API keys} qwqhthqwq/gemini_telegram_bot:latest
```
# How to Use
1. send /gemini {your content} to the bot (images can be included)
2. You can also add the bot to a group 

# Reference
[https://github.com/yihong0618/tg_bot_collections](https://github.com/yihong0618/tg_bot_collections)
