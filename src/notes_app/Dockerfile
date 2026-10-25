# The AFAW demo notes app (src/notes_app). Tagged with the commit by CI, never "latest".
# Build from the repository root: docker build -f src/notes_app/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN useradd --create-home --uid 10001 notes
WORKDIR /app

COPY src/notes_app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/notes_app/ src/notes_app/

USER notes
EXPOSE 8080
# Standard library only: the slim image has no curl.
HEALTHCHECK --interval=30s --timeout=3s \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/health', timeout=2)"]
CMD ["sh", "-c", "exec uvicorn notes_app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
