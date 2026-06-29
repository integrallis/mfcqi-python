# MFCQI (Python edition) — a runnable CLI image.
# Entry point is `mfcqi-py`, so: docker run --rm -v "$PWD":/src ghcr.io/integrallis/mfcqi-python analyze /src
FROM python:3.12-slim

LABEL org.opencontainers.image.title="mfcqi" \
      org.opencontainers.image.description="Multi-Factor Code Quality Index — single code-quality score for Python" \
      org.opencontainers.image.source="https://github.com/integrallis/mfcqi-python" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir . \
    && rm -rf /root/.cache

# Analyze the bind-mounted project by default.
WORKDIR /src
ENTRYPOINT ["mfcqi-py"]
CMD ["--help"]
