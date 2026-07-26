FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    gallery-dl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app app

ENTRYPOINT ["python","-m","app.main"]
