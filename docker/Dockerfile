FROM python:3.10-slim

# libxml2/libxslt for lxml; libpq for psycopg's binary wheel needs no build deps,
# but curl is handy for container healthchecks / manual debugging.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY penn_events ./penn_events
COPY alembic ./alembic
COPY alembic.ini .
COPY penn-calendars.csv .

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "penn_events.cli"]
CMD ["--help"]
