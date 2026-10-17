"""
utils/recorder.py
- يسجل كل خطوة + Trace
"""
import os
import asyncio
import io
from datetime import datetime
from utils.logger import get_logger

log = get_logger("Recorder")


class BrowserRecorder:
    def __init__(self, context, log_dir: str = "/tmp/recordings"):
        self.context = context
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.trace_active = False
        self.step_counter = 0
        self.steps = []
        self.bot = None
        self.chat_id = None

    def set_bot(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id

    async def start_recording(self):
        try:
            await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
            self.trace_active = True
            log.info("🎬 Recording started")
        except Exception as e:
            log.error(f"❌ start_recording: {e}")

    async def stop_recording(self) -> str:
        if not self.trace_active:
            return None
        try:
            path = os.path.join(self.log_dir, f"trace_{int(asyncio.get_event_loop().time()*1000)}.zip")
            await self.context.tracing.stop(path=path)
            self.trace_active = False
            return path
        except Exception as e:
            log.error(f"❌ stop_recording: {e}")
            return None

    async def add_step(self, action: str, selector: str = "", value: str = "", extra: dict = None):
        self.step_counter += 1
        step = {"num": self.step_counter, "time": datetime.now().strftime("%H:%M:%S"), "action": action, "selector": selector, "value": value}
        if extra:
            step.update(extra)
        self.steps.append(step)
        log.info(f"📝 Step {self.step_counter}: {action}")

    async def send_report(self):
        if not self.bot or not self.chat_id:
            return
        try:
            lines = [f"📊 Browser Report", f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f"📝 Steps: {len(self.steps)}", ""]
            for s in self.steps:
                lines.append(f"{s['num']:03d}. [{s['time']}] {s['action']}")
                if s['selector']:
                    lines.append(f"     → {s['selector']}")
                if s['value']:
                    lines.append(f"     → {s['value'][:80]}")
                for k, v in s.items():
                    if k not in ("num", "time", "action", "selector", "value"):
                        lines.append(f"     {k}: {str(v)[:150]}")
                lines.append("")
            report_text = "\n".join(lines)
            bio = io.BytesIO(report_text.encode("utf-8"))
            bio.name = "browser_steps.txt"
            bio.seek(0)
            await self.bot.send_document(chat_id=self.chat_id, document=bio, filename="browser_steps.txt", caption=f"📊 تقرير ({len(self.steps)} خطوة)")
            zip_path = await self.stop_recording()
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    await self.bot.send_document(chat_id=self.chat_id, document=f, filename=os.path.basename(zip_path), caption="🎬 Playwright Trace")
            log.info(f"✅ Report sent")
        except Exception as e:
            log.error(f"❌ send_report: {e}")
