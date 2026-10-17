import asyncio
import os
from utils.logger import get_logger
from utils.recorder import BrowserRecorder

log = get_logger("SSHS8")


BASE_URL = "https://sshs8.com"


class SSHS8:
    def __init__(self, context, sender=None, user_tag="@user"):
        self.context = context
        self.sender = sender
        self.user_tag = user_tag or "@user"
        self.page = None
        self.chat_id = None
        self.bot = None
        self.recorder = BrowserRecorder(context)

    def set_chat(self, chat_id):
        self.chat_id = chat_id

    def set_bot(self, bot):
        self.bot = bot
        if self.chat_id:
            self.recorder.set_bot(bot, self.chat_id)

    async def start_recording(self):
        return await self.recorder.start()

    async def open_url(self, url: str = BASE_URL) -> bool:
        log.info(f"🌐 فتح: {url}")
        self.page = await self.context.new_page()
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(3000)
            return True
        except Exception as e:
            log.error(f"❌ open_url: {e}")
            return False

    async def stop_and_send(self):
        await self.recorder.stop()
        await self.recorder.send_report()

    async def close(self):
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
