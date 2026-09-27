FROM python:3.11-slim

# تثبيت المتطلبات النظامية لـ Chrome و Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    xvfb \
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
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# تثبيت Google Chrome الرسمي
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y /tmp/chrome.deb \
    && rm /tmp/chrome.deb

# إعداد مجلد العمل
WORKDIR /app

# تثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت متصفح Playwright واعتمادياته
RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

# نسخ كود البوت
COPY GC.py .

# أمر التشغيل عبر Xvfb (وضع مرئي وهمي)
CMD ["xvfb-run", "-a", "python3", "GC.py"]
