"""
automation/sso_flow.py
تنسيق العملية — تقرير وحدة + طلب كلمة السر
"""
import re
from urllib.parse import urlparse, parse_qs

from automation.console import CloudConsole
from utils.logger import get_logger

log = get_logger("SSOFlow")


def extract_project_id(url: str) -> str:
    m = re.search(r'(qwiklabs-gcp-[\w-]+)', url or "")
    return m.group(1) if m else None


def extract_domain_from_service_url(service_url: str) -> str:
    s = (service_url or "").strip()
    if s.startswith("http://") or s.startswith("https://"):
        return urlparse(s).netloc.strip()
    return s.replace("http://", "").replace("https://", "").split("/")[0].strip()


def extract_authuser(page_url: str) -> str:
    try:
        qs = parse_qs(urlparse(page_url).query)
        return qs.get('authuser', ['1'])[0]
    except Exception:
        return '1'


def extract_email_from_url(url: str) -> str:
    """يستخرج الإيميل من رابط SSO"""
    try:
        # URL encoded
        m = re.search(r'Email%3D([^%&]+%40qwiklabs\.net)', url or "")
        if m:
            from urllib.parse import unquote
            return unquote(m.group(1))

        m = re.search(r'Email=([^&\s#]+@qwiklabs\.net)', url or "")
        if m:
            return m.group(1)

        # أي إيميل
        m = re.search(r'([a-zA-Z0-9\.\-]+@qwiklabs\.net)', url or "")
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def extract_password_from_url(url: str) -> str:
    """يستخرج كلمة السر من رابط SSO"""
    try:
        m = re.search(r'Password=([^&\s#]+)', url or "")
        if m:
            from urllib.parse import unquote
            return unquote(m.group(1))
    except Exception:
        pass
    return None


async def run_sso_flow(context, sso_url: str, image: str, sender=None, user_tag="@user") -> dict:
    project_id = extract_project_id(sso_url)
    if not project_id:
        raise RuntimeError("❌ Project ID ماكانش في الرابط.")

    log.info(f"🚀 SSO — project={project_id}")

    console = CloudConsole(context, sender=sender, user_tag=user_tag)

    # ✅ رسالة وحدة تتبدل
    status_msg = None
    if sender:
        try:
            status_msg = await sender.reply_text("🚀 جاري التنفيذ... [0/8]")
        except Exception:
            status_msg = None

    async def update_status(step: int, text: str = ""):
        if not status_msg:
            return
        try:
            await status_msg.edit_text(f"🚀 جاري التنفيذ... [{step}/8] {text}")
        except Exception:
            pass

    # ✅ صفحة وحدة
    page = await context.new_page()
    try:
        # 1) SSO
        await update_status(1, "فتح الرابط")
        try:
            await page.goto(sso_url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            await page.goto(sso_url, wait_until="commit", timeout=60000)

        # 2) TOS
        await update_status(2, "TOS")
        try:
            await console.step1_welcome_screen(page)
        except Exception as e:
            log.warning(f"⚠️ step1: {e}")

        # 3) Terms Dialog
        await update_status(3, "Terms Dialog")
        try:
            await console.step2_terms_dialog(page)
        except Exception as e:
            log.warning(f"⚠️ step2: {e}")

        # نستناو Dashboard
        try:
            await page.wait_for_url("**/home/dashboard**", timeout=45000)
        except Exception:
            pass

        await page.wait_for_timeout(500)
        authuser = extract_authuser(page.url)
        log.info(f"🔑 authuser = {authuser}")

        # 4) Enable API
        await update_status(4, "تفعيل API")
        try:
            await console.step3_enable_api(page, project_id, authuser)
        except Exception as e:
            log.warning(f"⚠️ step3: {e}")

        # 5) Create Cloud Run
        await update_status(5, "إنشاء Cloud Run")
        try:
            await console.step4_create_cloud_run(page, project_id, authuser, image)
        except Exception as e:
            await console._shot(page, "❌ step4 فشل")
            raise RuntimeError(f"فشل Cloud Run: {e}")

        # 6
        await update_status(6, "")
        # 7
        await update_status(7, "Create")
        # 8
        await update_status(8, "انتظار الرابط")
        try:
            final_url = await console.step5_get_deployed_url(page)
            domain = extract_domain_from_service_url(final_url)
        except Exception as e:
            await console._shot(page, "❌ step5 فشل")
            raise

        # ✅ نحذفو رسالة الحالة
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

    finally:
        try:
            await page.close()
        except Exception:
            pass

    return {
        "project_id": project_id,
        "authuser": authuser,
        "final_url": final_url,
        "domain": domain,
    }
