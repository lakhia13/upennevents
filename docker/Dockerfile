FROM python:3.10-slim

# libxml2/libxslt for lxml; libpq for psycopg's binary wheel needs no build deps,
# but curl is handy for container healthchecks / manual debugging.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Headless Chromium for the `playwright_html` feeder -- the small handful of sites
# behind a genuine Cloudflare "managed" JS challenge (confirmed: a stock headless
# browser executing real JS passes it; a plain HTTP client cannot). --with-deps
# pulls in the OS libraries Chromium needs on this base image, not just the browser
# binary, so this alone makes the feeder work with no other Dockerfile changes.
RUN playwright install --with-deps chromium

COPY penn_events ./penn_events
COPY alembic ./alembic
COPY alembic.ini .
# Same relative path as in the repo, so `import-registry docs/penn-calendars.csv`
# is one command that works both in this image and in a plain checkout (which is
# how the GitHub Actions migrate workflow invokes it).
COPY docs/penn-calendars.csv ./docs/penn-calendars.csv

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "penn_events.cli"]
CMD ["--help"]
