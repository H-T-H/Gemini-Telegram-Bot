FROM python:3.14.0-slim-bookworm

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./src/ .

ENV TELEGRAM_BOT_API_KEY=""
ENV GEMINI_API_KEYS=""

CMD ["sh", "-c", "python -u main.py ${TELEGRAM_BOT_API_KEY} ${GEMINI_API_KEYS}"]
