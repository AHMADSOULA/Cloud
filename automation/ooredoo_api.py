import asyncio
import html
from curl_cffi import requests as curl_requests
from utils.logger import get_logger

log = get_logger("OoredooAPI")

class OoredooAPI:
    def __init__(self):
        # روابط الـ API الخاصة بتطبيق My Ooredoo
        self.token_url = "https://apis.ooredoo.dz/api/auth/realms/myooredoo/protocol/openid-connect/token"
        self.balance_url = "https://apis.ooredoo.dz/api/ooredoo-bff/subscriptions/getAccountInfo"
        
        # الرؤوس (Headers) المستخرجة من تطبيق الهاتف الحقيقي لتجنب الحظر
        self.headers = {
            "User-Agent": "Dart/3.11 (dart:io)",
            "x-device-fingerprint": "512ad0a35aedf14ec3774ac8a4a5171f3a75232c4f799e5080ff98e7e6333e2f",
            "x-platform-origin": "mobile-android",
            "platform": "android",
            "x-version": "1.5.15",
            "x-signature": "f320f896f3da2a5a0284f9af316efb4ab0432b26406413568db116fa9dc60feb",
            "x-platform-data-signature": "eyJwbGF0Zm9ybSI6ImFuZHJvaWQiLCJpcy1waHlzaWNhbC1kZXZpY2UiOnRydWUsImRldmljZS1pZCI6IjE5OTJhODcwLWI5NzUtMTFmMS05ZmE0LWMxMjBhM2Q2ZDNlYzE3OTA0MDQ4MDE2NTUifQ==",
            "Accept": "*/*",
        }

    def check_account(self, user, password) -> dict:
        """
        فحص الحساب باستخدام curl_cffi لتخطي الحظر.
        هذه الدالة تعمل بشكل متزامن (Synchronous) ويفضل استدعاؤها باستخدام asyncio.to_thread
        """
        res = {"user": user, "pass": password, "balance": "فشل الدخول", "success": False, "error_detail": ""}
        
        payload = {
            "client_id": "myooredoo-app",
            "grant_type": "password",
            "username": user,
            "password": password
        }
        
        try:
            # ✅ استخدام curl_cffi مع انتحال شخصية متصفح Chrome
            # هذا هو السر الذي يمنع سيرفر Ooredoo من حظر السكربت
            session = curl_requests.Session(impersonate="chrome")
            
            # 1. طلب تسجيل الدخول للحصول على التوكين
            response = session.post(self.token_url, data=payload, headers=self.headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception:
                    # إذا أرجع السيرفر صفحة HTML بدلاً من JSON، فهذا يعني أن هناك حظر
                    text = response.text
                    clean_text = html.escape(text[:80].replace('\n', ' '))
                    res["balance"] = "محظور من السيرفر (WAF)"
                    res["error_detail"] = f"رد السيرفر بصفحة HTML. النص: {clean_text}"
                    return res
                    
                token = data.get("access_token")
                
                if token:
                    # 2. استخدام التوكين لجلب الرصيد
                    balance_headers = self.headers.copy()
                    balance_headers["Authorization"] = f"Bearer {token}"
                    balance_headers["x-msisdn"] = user
                    
                    url = f"{self.balance_url}?msisdn={user}"
                    
                    bal_response = session.get(url, headers=balance_headers, timeout=15)
                    
                    if bal_response.status_code == 200:
                        try:
                            bal_data = bal_response.json()
                            balance = bal_data.get("accountBalance")
                            if balance is not None:
                                res["balance"] = f"{balance} DA"
                                res["success"] = True
                            else:
                                res["balance"] = "رصيد غير متوفر"
                        except Exception:
                            res["balance"] = "خطأ في صيغة رد الرصيد"
                    else:
                        res["balance"] = f"خطأ في جلب الرصيد (HTTP {bal_response.status_code})"
            else:
                if response.status_code == 401:
                    res["balance"] = "كلمة سر خاطئة"
                else:
                    res["balance"] = f"خطأ في الاتصال (HTTP {response.status_code})"
                    
        except Exception as e:
            res["balance"] = "خطأ غير متوقع"
            res["error_detail"] = f"تفاصيل: {html.escape(str(e)[:100])}"
            
        return res
