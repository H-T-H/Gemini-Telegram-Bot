# Gemini_Telegram_Bot
使用Gemini API的Telegram Bot
# 如何安装
## (一)Linux环境下
1. 安装依赖
```
pip install -r requirements.txt
```
2. 在[BotFather](https://t.me/BotFather)处获取Telegram Bot API
3. 在[Google AI Studio](https://makersuite.google.com/app/apikey)处获取Gemini API keys
4. 运行
```
python main.py ${Telegram Bot API} ${Gemini API keys}
```
## (二)使用docker部署
```
docker run -d -e TELEGRAM_BOT_API_KEY={更换为你的Telegram Bot API} -e GEMINI_API_KEYS={更换为你的Gemini API keys} qwqhthqwq/gemini_telegram_bot:latest
```
# 如何使用
1. 直接向机器人发送/gemini {你的内容}  (可带图片)
2. 也可以将机器人添加至群组内使用

# 参考内容
[https://github.com/yihong0618/tg_bot_collections](https://github.com/yihong0618/tg_bot_collections)
