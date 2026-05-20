FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependencies directly
RUN pip install --no-cache-dir \
    aiogram==3.4.1 \
    sqlalchemy==2.0.28 \
    asyncpg==0.29.0 \
    redis==5.0.3 \
    httpx==0.27.0 \
    pydantic==2.6.4 \
    python-dotenv==1.0.1

COPY . /app/

CMD ["python", "-m", "app.main"]
