# Gemini_Telegram_Bot
A Telegram Bot using Gemini API  [中文文档](https://github.com/H-T-H/Gemini_Telegram_Bot/blob/main/README_zh.md)
# How to Install
## (1) On Linux
1. Install dependencies
```
pip install -r requirements.txt
```
2. Obtain Telegram Bot API at [BotFather](https://t.me/BotFather)
3. Get Gemini API keys from [Google AI Studio](https://makersuite.google.com/app/apikey)
4. To run the bot, execute:
```
python main.py ${Telegram Bot API} ${Gemini API keys}
```
## (2)Deploy Using Docker
### 1.With x86
Run the following command:
```
docker run -d -e TELEGRAM_BOT_API_KEY={replace with your Telegram Bot API} -e GEMINI_API_KEYS={replace with your Gemini API keys} qwqhthqwq/gemini_telegram_bot:latest
```
### 2.With arm
Run the following command:
```
docker run -d -e TELEGRAM_BOT_API_KEY={replace with your Telegram Bot API} -e GEMINI_API_KEYS={replace with your Gemini API keys} qwqhthqwq/gemini_telegram_bot_arm:latest
```

# How to Use
1. If you want to communicate with the bot in a group, your chat must start with '/gemini'.

![1](assets/1.png)
![2](assets/2.png)
2. If you are having a private chat with the bot, you can directly send what you want.

![3](assets/3.png)
![4](assets/4.png)

# Reference
[https://github.com/yihong0618/tg_bot_collections](https://github.com/yihong0618/tg_bot_collections)
