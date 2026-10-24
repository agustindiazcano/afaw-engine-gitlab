# The read-only AFAW web service (src/afaw_web). Tagged with the commit by CI, never "latest".
# build/web-data/ is assembled by the web_data CI job: live views, demo page and the records.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    AFAW_WEB_DATA_DIR=/app/data

RUN useradd --create-home --uid 10001 afaw
WORKDIR /app

COPY src/afaw_web/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/afaw_web/ src/afaw_web/
COPY build/web-data/ data/

USER afaw
EXPOSE 8080
# Cloud Run sets PORT; 8080 is the fallback for a local run.
CMD ["sh", "-c", "exec uvicorn afaw_web.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
