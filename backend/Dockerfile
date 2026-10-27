# Production image for the API. Build: docker build -t kjs-api ./backend
# All our packages have ready-made wheels, so no compilers are needed (smaller, safer image).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Never run as root: if someone breaks in, they get a powerless user.
# /srv/kjs_files = uploaded files when STORAGE_DRIVER=local (a Docker volume in production)
RUN useradd --create-home --uid 10001 kjs \
    && mkdir -p /srv/kjs_files \
    && chown kjs:kjs /srv/kjs_files
USER kjs

ENV CONFIG_DIR=/config \
    FILE_STORAGE_PATH=/srv/kjs_files

EXPOSE 8000

# Docker marks the container unhealthy if the API stops answering (no curl in the image, so Python)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

# One worker: the background jobs loop runs inside this process.
# graceful shutdown: finish running requests (up to 25 s) before stopping; compose waits 30 s
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "25"]
