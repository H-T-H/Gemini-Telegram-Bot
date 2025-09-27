# Gemini_Telegram_Bot
一个使用 Gemini API 的 Telegram 机器人[English ducument](https://github.com/H-T-H/Gemini_Telegram_Bot/blob/main/README_en.md)

## 主要功能
- 支持私聊与群聊中的多轮对话，命令触发与自动续写均可。
- 提供 **/draw** 图像生成与 **/edit** 图像编辑能力，满足基础 AIGC 需求。
- 允许通过 **/switch** 切换默认模型，灵活控制生成效果与费用。
- 提供 **/clear** 命令重置会话状态，保障隐私与上下文干净。
- 支持使用 Docker、Railway、Zeabur 等多种方式快速部署。
# Demo
[点这里](https://t.me/gemini_telegram_demo_bot)  

# 如何安装
## (1) Linux系统
1. 安装依赖
```
pip install -r requirements.txt
```
2. 在[BotFather](https://t.me/BotFather)获取Telegram Bot API
3. 在[Google AI Studio](https://makersuite.google.com/app/apikey)获取Gemini API keys
4. 设置环境变量
```
export GOOGLE_GEMINI_KEY="${Gemini API 密钥}"
```
5. 运行机器人，执行以下命令：
```
python main.py ${Telegram 机器人 API}
```
## (2)使用 Docker 部署
### 使用构建好的镜像(x86 only)
```
docker run -d --restart=always -e TELEGRAM_BOT_API_KEY={Telegram 机器人 API} -e GOOGLE_GEMINI_KEY={Gemini API 密钥} qwqhthqwq/gemini-telegram-bot:main
```
### 自行构建
1. 在[BotFather](https://t.me/BotFather)获取Telegram Bot API
2. 在[Google AI Studio](https://makersuite.google.com/app/apikey)获取Gemini API keys
3. 克隆项目
```
git clone https://github.com/H-T-H/Gemini-Telegram-Bot.git
```
4. 进入项目目录
```
cd Gemini-Telegram-Bot
```
5. 构建镜像
```
docker build -t gemini_tg_bot .
```
6. 运行镜像
```
docker run -d --restart=always -e TELEGRAM_BOT_API_KEY={Telegram 机器人 API} -e GOOGLE_GEMINI_KEY={Gemini API 密钥} gemini_tg_bot
```

## (3)使用 Railway 部署
点击下方按钮一键部署

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/HIsbMv?referralCode=4LyW6R)

### 手动部署步骤
1. 在 Railway 新建项目并选择 **Deploy from GitHub repo** 或者导入本仓库模版。
2. 在项目的 **Variables** 中新增以下环境变量：
   - `TELEGRAM_BOT_API_KEY`：你的 Telegram 机器人 API。
   - `GOOGLE_GEMINI_KEY`：你的 Gemini API 密钥。
3. 打开 **Settings → Deployments**，将启动命令设置为：
   ```
   python main.py $TELEGRAM_BOT_API_KEY
   ```
4. 如果 Railway 要求填写 `PORT`，可以保留默认值并忽略，因为机器人不监听 HTTP 端口。
5. 触发部署后，等待构建完成即可在 Railway 上持续运行 Telegram 机器人。

## (4)使用 Zeabur 部署
点击下方按钮一键部署

[![Deploy on Zeabur](https://zeabur.com/button.svg)](https://zeabur.com/templates/V2870T)


# 使用方法
1. 私聊中直接发送你的问题即可
2. 群组中使用 **/gemini** 或者 **/gemini_pro +你的问题**，支持多轮对话
3. 删除对话的历史记录请使用 **/clear**
4. 切换私聊中默认调用的模型请使用 **/switch**
5. 绘图使用 **/draw+你要的图片**，支持多轮对话
6. 编辑图片使用 **/edit + 你上传的图片+你要修改的地方**

# 参考信息
1. [https://github.com/yihong0618/tg_bot_collections](https://github.com/yihong0618/tg_bot_collections)
2. [https://github.com/yym68686/md2tgmd](https://github.com/yym68686/md2tgmd)

## Star History
[![Star History Chart](https://api.star-history.com/svg?repos=H-T-H/Gemini-Telegram-Bot&type=Date)](https://star-history.com/#H-T-H/Gemini-Telegram-Bot&Date)
