FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium (required)
RUN playwright install chromium --with-deps

# Install Firefox (optional — anti-detection fallback, build continues if download fails)
RUN playwright install firefox --with-deps || echo "Firefox install failed, continuing with Chromium only"

# Copy application
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
