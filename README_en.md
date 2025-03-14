# Gemini_Telegram_Bot
A Telegram Bot using Gemini API
# Demo
[Click here](https://t.me/gemini_telegram_demo_bot)

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
### Use the built image(x86 only)
```
docker run -d --restart=always -e TELEGRAM_BOT_API_KEY={Telegram Bot API} -e GEMINI_API_KEYS={Gemini API Key} qwqhthqwq/gemini-telegram-bot:main
```
### build by yourself
1. Get Telegram Bot API at [BotFather](https://t.me/BotFather)
2. Get Gemini API keys on [Google AI Studio](https://makersuite.google.com/app/apikey)
3. Clone repository
```
git clone https://github.com/H-T-H/Gemini-Telegram-Bot.git
```
4. Enter repository directory.
```
cd Gemini-Telegram-Bot
```
5. Build images
```
docker build -t gemini_tg_bot .
```
6. run
```
docker run -d --restart=always -e TELEGRAM_BOT_API_KEY={Telegram Bot API} -e GEMINI_API_KEYS={Gemini API Key} gemini_tg_bot
```

## (3)Deploy on Railway
Click on the button below for a one-click deployment.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/HIsbMv?referralCode=4LyW6R)

## (4)Deploy on Zeabur
Click on the button below for a one-click deployment.

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/templates/V2870T)


# How to Use
1. Send your questions directly in a private chat.
2.  In a group chat, use **/gemini** or /gemini\_pro + your question. Multi-turn conversations are supported.
3. You can use the **/clear** command to delete the current conversation history.
4. You can use the **/switch** command to switch the model.
5. To generate images, use **/draw** + the image you want. Multi-turn conversations are supported.
6. To edit images, use **/edit** + the image you upload + the edits you want to make.


# Reference
1. [https://github.com/yihong0618/tg_bot_collections](https://github.com/yihong0618/tg_bot_collections)
2. [https://github.com/yym68686/md2tgmd](https://github.com/yym68686/md2tgmd)
