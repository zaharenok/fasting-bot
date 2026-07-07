FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for SQLite DB
RUN mkdir -p /data

ENV DB_PATH=/data/fasting.db

CMD ["python", "-m", "bot.main"]
