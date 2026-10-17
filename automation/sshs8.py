"""
automation/sshs8.py
- أتمتة موقع sshs8.com
- إضافة Scroll قوي (window.scrollTo) + Wait + Close Ads
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
        """تصوير الصفحة وإرسالها للمستخدم"""
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
        """يفتح البروتوكول (SSH/VMESS/VLESS/TROJAN) ويضغط على السهم باش تبان القارات"""
        try:
            await self._close_ads()
            await self.page.wait_for_timeout(1000)

            clicked = False
            for sel in [
                f'a:has-text("{proto_name}")',
                f'span:has-text("{proto_name}")',
                f'li:has-text("{proto_name}")',
            ]:
                try:
                    el = self.page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=5000, force=True)
                        clicked = True
                        await self.page.wait_for_timeout(2000)
                        break
                except Exception: continue

            if not clicked:
                await self.page.evaluate(r"""
                    (name) => {
                        const all = document.querySelectorAll('a, span, li');
                        for (const el of all) {
                            const t = (el.innerText || el.textContent || '').trim();
                            if (t === name) { el.click(); return; }
                        }
                    }
                """, proto_name)
                await self.page.wait_for_timeout(2000)

            # نضغطو على السهم (▼) إلا كان
            try:
                arrow_clicked = await self.page.evaluate(r"""
                    (name) => {
                        const all = document.querySelectorAll('a, li, span');
                        for (const el of all) {
                            const t = (el.innerText || el.textContent || '').trim();
                            if (t.includes(name) && t.length < name.length + 30) {
                                const arrow = el.querySelector('.dropdown-toggle, [class*="arrow"], [class*="caret"], svg, i');
                                if (arrow) { arrow.click(); return true; }
                                const parent = el.closest('li, div');
                                if (parent) {
                                    const arrow2 = parent.querySelector('.dropdown-toggle, [class*="arrow"], [class*="caret"], svg');
                                    if (arrow2) { arrow2.click(); return true; }
                                }
                            }
                        }
                        return false;
                    }
                """, proto_name)
                if arrow_clicked:
                    await self.page.wait_for_timeout(2000)
            except Exception: pass

            await self._screenshot(f"2. Protocol: {proto_name}")

            continents = await self.page.evaluate(r"""
                () => {
                    const out = [];
                    const keywords = ["أوروبا", "آسيا", "أمريكا الشمالية", "أمريكا الجنوبية", "أفريقيا", "Europe", "Asia", "North America", "South America", "Africa"];
                    const all = document.querySelectorAll('a, li, span');
                    for (const el of all) {
                        const t = (el.innerText || el.textContent || '').trim();
                        if (!t || t.length > 60) continue;
                        for (const kw of keywords) {
                            if (t.includes(kw)) {
                                if (!out.find(x => x.name === kw)) {
                                    out.push({ name: kw, full_text: t, href: el.href || '' });
                                }
                                break;
                            }
                        }
                    }
                    return out;
                }
            """)
            return continents
        except Exception as e:
            log.error(f"❌ open_protocol: {e}")
            return []

    async def open_continent(self, cont_name: str) -> list:
        """يفتح القارة، يهبط لتحت 100%، ويجيب الدول"""
        try:
            await self._close_ads()
            
            # 1. نضغطو على القارة
            for sel in [f'a:has-text("{cont_name}")', f'text="{cont_name}"']:
                try:
                    el = self.page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=5000, force=True)
                        await self.page.wait_for_timeout(4000)
                        break
                except Exception: continue

            # 2. نغلقو الإعلانات
            await self._close_ads()
            await self.page.wait_for_timeout(1000)

            # 3. نقبلو الكوكيز
            for sel in ['button:has-text("Accept")', 'button:has-text("Agree")', 'button:has-text("Got it")']:
                try:
                    el = self.page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=2000, force=True)
                        break
                except Exception: continue

            # 4. نهبطو لتحت 100% بـ JS (بلا ما نتأثرو بالماوس)
            scroll_result = await self.page.evaluate(r"""
                async () => {
                    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
                    let lastHeight = 0;
                    let stableCount = 0;
                    
                    for (let i = 0; i < 20; i++) {
                        window.scrollTo(0, document.body.scrollHeight);
                        await sleep(800);
                        
                        const newHeight = document.body.scrollHeight;
                        if (newHeight === lastHeight) {
                            stableCount++;
                            if (stableCount >= 3) break;
                        } else {
                            stableCount = 0;
                            lastHeight = newHeight;
                        }
                    }
                    
                    return {
                        finalHeight: document.body.scrollHeight,
                        currentScroll: window.scrollY,
                        iterations: stableCount,
                    };
                }
            """)
            log.info(f"📜 Scroll result: {scroll_result}")

            # 5. نستناو شوية باش تتحمل العناصر (lazy loading)
            await self.page.wait_for_timeout(3000)
            await self._close_ads()

            # 6. نصوّرو
            await self._screenshot(f"3. Continent: {cont_name}")

            # 7. نستخرجو الدول من الروابط
            countries = await self.page.evaluate(r"""
                () => {
                    const out = [];
                    const exclude = ["Menu", "Home", "About", "Contact", "Blog", "Privacy", "Terms", "SSH Websocket", "V2Ray", "OpenVPN", "TROJAN", "Europe", "Asia", "America", "Africa", "Free VPN", "Premium VPN", "WireGuard"];
                    
                    document.querySelectorAll('a').forEach(a => {
                        const t = (a.innerText || a.textContent || '').trim();
                        if (!t || t.length < 3 || t.length > 40) return;
                        if (exclude.includes(t)) return;
                        
                        const href = (a.href || '').toLowerCase();
                        if (href.includes('ssh') || href.includes('server') || href.includes('config')) {
                            if (!out.find(x => x.name === t)) {
                                out.push({ name: t, href: a.href });
                            }
                        }
                    });
                    
                    if (out.length === 0) {
                        document.querySelectorAll('[class*="card"], article, [class*="country"]').forEach(card => {
                            const h = card.querySelector('h2, h3, h4, strong, a');
                            if (!h) return;
                            const t = (h.innerText || '').trim();
                            if (!t || t.length < 3 || t.length > 40) return;
                            if (exclude.includes(t)) return;
                            
                            const link = card.querySelector('a');
                            if (!out.find(x => x.name === t)) {
                                out.push({ name: t, href: link ? link.href : '' });
                            }
                        });
                    }
                    
                    return out;
                }
            """)
            
            log.info(f"🌍 Countries found: {len(countries)}")
            return countries
        except Exception as e:
            log.error(f"❌ open_continent: {e}")
            return []

    async def open_country(self, country_name: str) -> list:
        """يفتح الدولة ويجيب الخوادم"""
        try:
            await self._close_ads()
            for sel in [f'text="{country_name}"', f'a:has-text("{country_name}")']:
                try:
                    el = self.page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=5000, force=True)
                        await self.page.wait_for_timeout(4000)
                        break
                except Exception: continue
            
            # نضغطو على قائمة الخوادم
            for sel in ['text="قائمة الخوادم"', 'a:has-text("قائمة الخوادم")']:
                try:
                    el = self.page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=3000, force=True)
                        await self.page.wait_for_timeout(2000)
                        break
                except Exception: continue

            await self._screenshot(f"4. Country: {country_name}")

            return await self.page.evaluate(r"""
                () => {
                    const out = [];
                    document.querySelectorAll('[class*="card"], article').forEach(card => {
                        const m = (card.innerText || '').match(/E\d{2,3}/);
                        if (!m) return;
                        const btn = Array.from(card.querySelectorAll('a, button')).find(b => b.innerText.includes('إنشاء') || b.innerText.includes('Create'));
                        if (btn) out.push({ id: m[0], href: btn.href || '' });
                    });
                    return out;
                }
            """)
        except Exception: return []

    async def create_account(self, href: str) -> dict:
        """إنشاء الحساب فـ الخادم"""
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

            for sel in ['button:has-text("إنشاء حساب")', 'button:has-text("Create")']:
                try:
                    el = self.page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=5000, force=True)
                        break
                except Exception: continue

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
