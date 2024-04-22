FROM python:3.9.18-slim-bullseye
WORKDIR /app
COPY ./ /app/
RUN pip install --no-cache-dir -r requirements.txt
ENV TELEGRAM_BOT_API_KEY=""
ENV GEMINI_API_KEYS=""
CMD ["sh", "-c", "python main.py ${5624390876:AAFtmB-sV52rPNg3Ty6O1rPgmqUZDrLHViw} ${AIzaSyCI-AvQRiyEqjDNfvIQJwuPWqKQ2ySkPzI}"]
