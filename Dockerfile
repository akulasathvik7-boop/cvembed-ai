# CV Embed — Flask UI + ML stack (image is large due to torch/transformers).
FROM python:3.12-slim-bookworm

WORKDIR /app

# Minimal build deps for some wheels; NLTK may download corpora at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# Render/Heroku/Fly set PORT; default 8000 for local docker run -p 8000:8000
EXPOSE 8000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 1 --timeout 180 --graceful-timeout 60 app:app"]
