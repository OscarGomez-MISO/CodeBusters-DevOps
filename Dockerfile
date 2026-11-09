FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    FLASK_APP=application.py \
    TRUST_PROXY_HEADERS=false \
    PROXY_HOPS=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check \
    && groupadd --system --gid 10001 blacklists \
    && useradd --uid 10001 --gid blacklists --no-create-home --shell /usr/sbin/nologin blacklists \
    && mkdir /data \
    && chown blacklists:blacklists /data

COPY --chown=blacklists:blacklists application.py ./
COPY --chown=blacklists:blacklists app/ ./app/

USER 10001:10001

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--access-logfile", "-", "--error-logfile", "-", "--no-control-socket", "application:application"]
