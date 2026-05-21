FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependencies directly
RUN pip install --no-cache-dir \
    aiogram==3.4.1 \
    sqlalchemy==2.0.28 \
    aiosqlite==0.20.0 \
    httpx==0.27.0 \
    pydantic==2.5.3 \
    python-dotenv==1.0.1 \
    gTTS==2.5.1 \
    pytest==8.1.1 \
    pytest-asyncio==0.23.6

COPY . /app/

CMD ["python", "-m", "app.main"]
