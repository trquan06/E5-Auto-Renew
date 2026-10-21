FROM node:25-alpine AS webui
WORKDIR /src
COPY package.json package-lock.json tailwind.config.js ./
COPY scripts ./scripts
COPY app/static ./app/static
RUN npm ci --ignore-scripts && npm run build

FROM python:3.12-slim AS runtime
ARG VCS_REF=unknown
ARG BUILD_DATE=unknown
ARG VERSION=2.0.0
LABEL org.opencontainers.image.title="MS365 Auto Renew" \
      org.opencontainers.image.description="Self-hosted delegated Microsoft Graph development scheduler" \
      org.opencontainers.image.version="$VERSION" \
      org.opencontainers.image.revision="$VCS_REF" \
      org.opencontainers.image.created="$BUILD_DATE" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/trquan06/E5-Auto-Renew"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data \
    HOST=0.0.0.0 \
    PORT=8080 \
    FORWARDED_ALLOW_IPS=127.0.0.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app app ./app
COPY --chown=app:app run.py ./run.py
COPY --from=webui --chown=app:app /src/app/static ./app/static
RUN mkdir -p /app/data && chown app:app /app/data

USER 10001:10001
VOLUME ["/app/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD curl --fail --silent http://127.0.0.1:8080/health || exit 1
CMD ["python", "run.py"]
