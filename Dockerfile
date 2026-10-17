FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# تثبيت Xvfb + VNC + supervisor
RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    supervisor \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright Chromium
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy project
COPY . .

# Supervisor config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Display
ENV DISPLAY=:99

# Start with supervisord
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
