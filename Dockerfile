FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

RUN apt-get update && apt-get install -y \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    supervisor \
    net-tools \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

ENV DISPLAY=:99
ENV PORT=8080
EXPOSE 8080

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
