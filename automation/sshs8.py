"""
automation/sshs8.py
- أتمتة موقع sshs8.com
- تصليح مشاكل الضغط (force click) + تخطي إعلانات
- تصوير فـ كل خطوة
"""
import asyncio
import random
import string
import os
from utils.logger import get_logger

log = get_logger("SSHS8")
BASE_URL = "https://sshs8.com"

def generate_password():
    return "".join(random.choices(string.ascii_letters + string.digits, k=10))

class SSHS8:
    def __init__(self, context, bot=None, chat_id=None):
        self.context = context
        self.page = None
        self.bot = bot
        self.chat_id = chat_id
        self.counter = 0

    async def _screenshot(self, name: str):
        if not self.page or not self.bot or not self.chat_id:
            return
        try:
            self.counter += 1
            path = f"/tmp/shot_{self.counter}_{int(asyncio.get_event_loop().time()*1000)}.png"
            await self.page.screenshot(path=path, full_page=False, timeout=10000)
            with open(path, "rb") as f:
                try:
                    await self.bot.send_photo(chat_id=self.chat_id, photo=f, caption=f"📸 {name}")
                except Exception: pass
            try: os.remove(path)
            except: pass
        except Exception: pass

    async def _close_ads(self):
        """إغلاق الإعلانات وحذف الـ Overlays"""
        try:
            await self.page.evaluate("""
                () => {
                    document.querySelectorAll('iframe').forEach(f => {
                        if(f.src && (f.src.includes('ads') || f.src.includes('google') || f.src.includes('doubleclick') || f.src.includes('fluid'))) f.remove();
                    });
                    document.querySelectorAll('[class*="popup"], [class*="modal"], [class*="overlay"]').forEach(el => {
                        try { if (window.getComputedStyle(el).zIndex > 100) el.remove(); } catch(e) {}
                    });
                }
            """)
            await self.page.wait_for_timeout(500)
        except Exception: pass

    async def _click(self, selector: str, desc: str = ""):
        """تصليح الضغط بـ force=True"""
        try:
            await self._close_ads()
            el = self.page.locator(selector).first
            if await el.count() > 0:
                await el.click(timeout=5000, force=True)
                await self.page.wait_for_timeout(2500)
                return True
        except Exception: pass
        return False

    async def open_home(self) -> bool:
        self.page = await self.context.new_page()
        try:
            await self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(4000)
            await self._close_ads()
            await self._screenshot("1. Home Page")
            return True
        except Exception: return False

    async def open_protocol(self, proto_name: str) -> list:
        await self._click(f'a:has-text("{proto_name}")', proto_name)
        await self.page.wait_for_timeout(3000)
        await self._screenshot(f"2. Protocol: {proto_name}")
        
        return await self.page.evaluate(r"""
            () => {
                const out = [];
                const kw = ["أوروبا", "آسيا", "أمريكا الشمالية", "أمريكا الجنوبية", "أفريقيا", "Europe", "Asia", "North America", "South America", "Africa"];
                document.querySelectorAll('a').forEach(a => {
                    const t = (a.innerText || '').trim();
                    for (const k of kw) {
                        if (t.includes(k) && !out.find(x => x.name === k)) out.push({ name: k });
                    }
                });
                return out;
            }
        """)

    async def open_continent(self, cont_name: str) -> list:
        await self._click(f'a:has-text("{cont_name}")', cont_name)
        await self.page.wait_for_timeout(3000)
        await self._screenshot(f"3. Continent: {cont_name}")

        return await self.page.evaluate(r"""
            () => {
                const out = [];
                const exclude = ["Menu", "Home", "SSH Websocket", "V2Ray", "OpenVPN", "TROJAN"];
                document.querySelectorAll('h2, h3, h4').forEach(h => {
                    const t = (h.innerText || '').trim();
                    if (t && t.length < 50 && !exclude.includes(t) && !out.find(x => x.name === t)) out.push({ name: t });
                });
                return out;
            }
        """)

    async def open_country(self, country_name: str) -> list:
        await self._click(f'text="{country_name}"', country_name)
        await self.page.wait_for_timeout(3000)
        await self._click('text="قائمة الخوادم"')
        await self.page.wait_for_timeout(2000)
        await self._screenshot(f"4. Country: {country_name}")

        return await self.page.evaluate(r"""
            () => {
                const out = [];
                document.querySelectorAll('[class*="card"]').forEach(card => {
                    const m = (card.innerText || '').match(/E\d{2,3}/);
                    if (!m) return;
                    const btn = Array.from(card.querySelectorAll('a, button')).find(b => b.innerText.includes('إنشاء') || b.innerText.includes('Create'));
                    if (btn) out.push({ id: m[0], href: btn.href || '' });
                });
                return out;
            }
        """)

    async def create_account(self, href: str) -> dict:
        password = generate_password()
        try:
            await self.page.goto(href, wait_until="domcontentloaded", timeout=60000)
            await self.page.wait_for_timeout(3000)
            await self._close_ads()
            await self._screenshot("5. Server Page")

            for sel in ['input[name*="user" i]', 'input[type="password"]']:
                el = self.page.locator(sel).first
                if await el.count() > 0:
                    await el.fill(password if 'pass' in sel else f"u{random.randint(1000,9999)}")

            await self._click('button:has-text("إنشاء حساب")')
            await self.page.wait_for_timeout(5000)
            await self._screenshot("6. Account Created")

            data = await self.page.evaluate(r"""
                () => {
                    const out = { ip: null, user: null, link: null };
                    document.querySelectorAll('input, textarea').forEach(inp => {
                        const v = (inp.value || '').trim();
                        if (/^\d+\.\d+\.\d+\.\d+$/.test(v)) out.ip = v;
                        else if (v.startsWith('vmess://') || v.startsWith('vless://') || v.startsWith('trojan://')) out.link = v;
                    });
                    return out;
                }
            """)
            data["password"] = password
            data["success"] = True
            return data
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def close(self):
        if self.page:
            try: await self.page.close()
            except: pass
