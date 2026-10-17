"""
utils/recorder.py
- يسجل كل خطوة فـ المتصفح
- يستعمل Playwright Tracing (screenshots + snapshots + sources)
"""
import os
import json
import asyncio
import zipfile
import io
from datetime import datetime
from utils.logger import get_logger

log = get_logger("Recorder")


class BrowserRecorder:
    def __init__(self, context, log_dir: str = "/tmp/recordings"):
        self.context = context
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.page = None
        self.trace_active = False
        self.step_counter = 0
        self.steps = []
        self.bot = None
        self.chat_id = None

    def set_bot(self, bot, chat_id):
        self.bot = bot
        self.chat_id = chat_id

    async def start_recording(self):
        """يبدأ التسجيل"""
        try:
            await self.context.tracing.start(
                screenshots=True,
                snapshots=True,
                sources=True,
            )
            self.trace_active = True
            log.info("🎬 Recording started")
        except Exception as e:
            log.error(f"❌ start_recording: {e}")

    async def stop_recording(self) -> str:
        """يوقف التسجيل ويرجع path ديال zip"""
        if not self.trace_active:
            return None
        try:
            path = os.path.join(self.log_dir, f"trace_{int(asyncio.get_event_loop().time()*1000)}.zip")
            await self.context.tracing.stop(path=path)
            self.trace_active = False
            log.info(f"✅ Recording stopped: {path}")
            return path
        except Exception as e:
            log.error(f"❌ stop_recording: {e}")
            return None

    async def add_step(self, action: str, selector: str = "", value: str = "", extra: dict = None):
        """يضيف خطوة للتقرير"""
        self.step_counter += 1
        step = {
            "num": self.step_counter,
            "time": datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "selector": selector,
            "value": value,
        }
        if extra:
            step.update(extra)
        self.steps.append(step)
        log.info(f"📝 Step {self.step_counter}: {action} {selector[:30] if selector else ''}")

    async def send_report(self):
        """يبعت التقرير + trace.zip"""
        if not self.bot or not self.chat_id:
            log.warning("⚠️ لا bot ولا chat_id — ما نقدروش نبعثو")
            return

        try:
            # ✅ نبنيو التقرير النصي
            lines = [
                "═" * 60,
                f"📊 Browser Recording Report",
                f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "═" * 60,
                "",
                f"📝 Total steps: {len(self.steps)}",
                "",
            ]

            for s in self.steps:
                lines.append(f"{s['num']:03d}. [{s['time']}] {s['action']}")
                if s['selector']:
                    lines.append(f"     Selector: {s['selector']}")
                if s['value']:
                    lines.append(f"     Value: {s['value'][:80]}")
                # extra keys
                for k, v in s.items():
                    if k not in ("num", "time", "action", "selector", "value"):
                        lines.append(f"     {k}: {str(v)[:150]}")
                lines.append("")

            lines.append("═" * 60)
            report_text = "\n".join(lines)

            # ✅ نبعتو txt
            bio = io.BytesIO(report_text.encode("utf-8"))
            bio.name = "browser_steps.txt"
            bio.seek(0)

            await self.bot.send_document(
                chat_id=self.chat_id,
                document=bio,
                filename="browser_steps.txt",
                caption=f"📊 تقرير الخطوات ({len(self.steps)} خطوة)",
            )

            # ✅ نبعتو trace.zip
            zip_path = await self.stop_recording()
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    await self.bot.send_document(
                        chat_id=self.chat_id,
                        document=f,
                        filename=os.path.basename(zip_path),
                        caption="🎬 Playwright Trace\n\nافتحه محلياً:\n`npx playwright show-trace trace_xxx.zip`",
                    )

            log.info(f"✅ Report sent ({len(self.steps)} steps)")

        except Exception as e:
            log.error(f"❌ send_report: {e}", exc_info=True)
