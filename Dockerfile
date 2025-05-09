FROM python:3.11-slim

# Встановлюємо оновлення і системні залежності
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Робоча директорія
WORKDIR /app

# Копіюємо файли
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Встановлюємо змінну середовища для токена (Fly підставить її при деплої)
ENV TELEGRAM_TOKEN=${TELEGRAM_TOKEN}

CMD ["python", "bot.py"]
