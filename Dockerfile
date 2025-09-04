FROM python:3.9.18-slim-bullseye
WORKDIR /app
COPY ./ /app/
RUN pip install --no-cache-dir -r requirements.txt
ENV TELEGRAM_BOT_API_KEY=""
ENV GOOGLE_GEMINI_KEY=""
CMD ["sh", "-c", "python main.py ${TELEGRAM_BOT_API_KEY}"]
