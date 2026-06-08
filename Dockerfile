FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml README.md ./
COPY underwrite/ underwrite/

RUN pip install --no-cache-dir build && \
    pip install --no-cache-dir cryptography pydantic typer && \
    python -m build --wheel && \
    pip install --no-cache-dir dist/*.whl[serve,postgres,otlp]

FROM python:3.12-slim

RUN addgroup --system --gid 1001 underwrite && \
    adduser --system --uid 1001 --ingroup underwrite underwrite

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/underwrite /usr/local/bin/underwrite

RUN mkdir -p /data && chown underwrite:underwrite /data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

USER underwrite

ENTRYPOINT ["underwrite"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]
