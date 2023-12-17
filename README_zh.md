# Gemini_Telegram_Bot
一个使用 Gemini API 的 Telegram 机器人
# 如何安装
## (1) Linux系统
1. 安装依赖
```
pip install -r requirements.txt
```
2. 在[BotFather](https://t.me/BotFather)获取Telegram Bot API
3. 在[Google AI Studio](https://makersuite.google.com/app/apikey)获取Gemini API keys
4. 运行机器人，执行以下命令：
```
python main.py ${Telegram 机器人 API} ${Gemini API 密钥}
```
## (2)使用 Docker 部署
### 1.在 x86 架构上
运行以下命令：
```
docker run -d -e TELEGRAM_BOT_API_KEY={Telegram 机器人 API} -e GEMINI_API_KEYS={Gemini API 密钥} qwqhthqwq/gemini_telegram_bot:latest
```
### 2.在 arm 架构上
运行以下命令：
```
docker run -d -e TELEGRAM_BOT_API_KEY={Telegram 机器人 API} -e GEMINI_API_KEYS={Gemini API 密钥} qwqhthqwq/gemini_telegram_bot_arm:latest
```

# 使用方法
1. 向机器人发送 /gemini {您的内容}（可以带图片）。
2. 也可以将机器人添加到群组中

# 参考信息
[https://github.com/yihong0618/tg_bot_collections](https://github.com/yihong0618/tg_bot_collections)
