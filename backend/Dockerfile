###########################################################
# Builder stage. Build dependencies.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  UV_PYTHON_DOWNLOADS=0

WORKDIR /app
COPY ./pyproject.toml ./uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-install-project --no-dev


###########################################################
# Production stage.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS production

ENV PYTHONUNBUFFERED=1 \
  DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install --no-install-recommends -y \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libu2f-udev \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    xvfb \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app
COPY --from=builder /app/.venv /app/.venv

RUN mkdir -p /app/data/cloak-profiles \
  && uv run python -m cloakbrowser install

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "python", "-m", "src.api", "--host", "0.0.0.0", "--port", "8000", "--loop", "asyncio", "--proxy-headers", "--forwarded-allow-ips=*"]
