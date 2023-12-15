FROM python:3.9-alpine
WORKDIR /app
COPY ./ /app/
RUN pip install -r requirements.txt
ENV TELEGRAM_BOT_API_KEY=""
ENV GEMINI_API_KEYS=""
CMD ["sh", "-c", "python main.py ${TELEGRAM_BOT_API_KEY} ${GEMINI_API_KEYS}"]