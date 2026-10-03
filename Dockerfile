FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ✅ xvfb + VNC + websockify + noVNC
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    supervisor \
    fonts-liberation \
    fonts-noto-color-emoji \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mkdir -p /tmp/logs /tmp/chrome_profile

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY . .

# ✅ supervisor config
RUN cat > /etc/supervisor/conf.d/services.conf <<'EOF'
[supervisord]
nodaemon=true
user=root
logfile=/dev/null
logfile_maxbytes=0

[program:xvfb]
command=/usr/bin/Xvfb :99 -screen 0 1280x720x24 -ac +extension GLX +render -noreset
autostart=true
autorestart=true
stdout_logfile=/dev/null
stderr_logfile=/dev/null

[program:x11vnc]
command=/usr/bin/x11vnc -display :99 -forever -nopw -rfbport 5900 -shared -quiet
autostart=true
autorestart=true
stdout_logfile=/dev/null
stderr_logfile=/dev/null

[program:novnc]
command=/usr/bin/websockify --web=/usr/share/novnc/ 0.0.0.0:6080 localhost:5900
autostart=true
autorestart=true
stdout_logfile=/dev/null
stderr_logfile=/dev/null

[program:bot]
command=python main.py
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
EOF

EXPOSE 6080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/services.conf"]
