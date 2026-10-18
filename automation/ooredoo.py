import asyncio
import os
from utils.logger import get_logger

log = get_logger("Ooredoo")

class OoredooChecker:
    def __init__(self, context, chat_id, bot):
        self.context = context
        self.chat_id = chat_id
        self.bot = bot
        self.page = None
        self.shot_count = 0

    async def _shot(self, name: str):
        if not self.page: return
        try:
            self.shot_count += 1
            # نمسحو الصور القديمة باش ما نعمروش السيرفر
            if self.shot_count > 5:
                return
            
            path = f"/tmp/ooredoo_{self.shot_count}.png"
            await self.page.screenshot(path=path, full_page=False, timeout=10000)
            with open(path, "rb") as f:
                await self.bot.send_photo(chat_id=self.chat_id, photo=f, caption=f"📸 {name}")
            try: os.remove(path)
            except: pass
        except Exception as e:
            log.warning(f"⚠️ screenshot: {e}")

    async def check_account(self, user, password) -> dict:
        """يدخل لحساب واحد ويجيب الرصيد"""
        if not self.page:
            self.page = await self.context.new_page()
            
        res = {"user": user, "pass": password, "balance": "فشل الدخول", "success": False}
        
        try:
            await self.page.goto("https://my.ooredoo.dz/sign-in", wait_until="domcontentloaded", timeout=40000)
            await self.page.wait_for_timeout(3000)
            
            # التصوير عند الدخول للموقع
            if self.shot_count == 0:
                await self._shot("صفحة الدخول")

            # كتابة اسم المستخدم
            try:
                await self.page.locator('input[type="text"], input[name="username"], input[id="username"]').first.fill(user)
            except: pass

            # كتابة كلمة السر
            try:
                await self.page.locator('input[type="password"]').first.fill(password)
            except: pass

            # التصوير بعد كتابة المعلومات
            await self._shot("بعد كتابة المعلومات")

            # الضغط على دخول
            try:
                btn = self.page.locator('button[type="submit"], button:has-text("تسجيل الدخول"), button:has-text("Login"), button:has-text("Sign in")').first
                await btn.click(force=True)
            except: pass

            await self.page.wait_for_timeout(5000)

            # محاولة قراءة الرصيد
            body = await self.page.evaluate("() => document.body.innerText")
            if "الرصيد" in body or "Solde" in body or "DA" in body:
                # استخراج الرصيد بالتقريب
                import re
                m = re.search(r'([\d\.\,]+)\s*(?:DA|DZD)', body, re.IGNORECASE)
                if m:
                    res["balance"] = f"{m.group(1)} DA"
                else:
                    res["balance"] = "تم الدخول (الرصيد غير مقروء)"
                res["success"] = True
            else:
                res["balance"] = "كلمة سر خاطئة"

        except Exception as e:
            log.error(f"❌ check_account {user}: {e}")
            res["balance"] = "خطأ في المتصفح"
            
        return res

    async def close(self):
        if self.page:
            try: await self.page.close()
            except: pass
