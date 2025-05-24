FROM python:3.12-slim-bullseye

ENV PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# These ENV are for documentation / default values if not overridden at runtime.
# main.py expects these to be passed as command line arguments.
ENV TELEGRAM_BOT_API_KEY="" 
ENV GOOGLE_GEMINI_KEY="" 

# The main.py script takes TG_TOKEN as argv[1] and GOOGLE_GEMINI_KEY as argv[2].
# GOOGLE_GEMINI_KEY is then set as an ENV var by main.py for core.ai_client to use.
CMD ["sh", "-c", "python main.py ${TELEGRAM_BOT_API_KEY} ${GOOGLE_GEMINI_KEY}"]
