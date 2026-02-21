FROM python:3.12-slim

# System deps for Chromium and Firefox rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libgtk-3-0 libx11-xcb1 \
    libxshmfence1 libglu1-mesa fonts-liberation fonts-noto-color-emoji \
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install browser binaries
RUN patchright install chromium
RUN python -m camoufox fetch
RUN python -m browserforge update

COPY . .

EXPOSE 8888

# Single worker — browsers are process-scoped, asyncio handles concurrency
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888", "--workers", "1"]
