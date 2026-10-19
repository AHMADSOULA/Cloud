import aiohttp
import asyncio
from utils.logger import get_logger

log = get_logger("OoredooAPI")

class OoredooAPI:
    def __init__(self):
        self.token_url = "https://apis.ooredoo.dz/api/auth/realms/myooredoo/protocol/openid-connect/token"
        self.balance_url = "https://apis.ooredoo.dz/api/ooredoo-bff/subscriptions/getAccountInfo"
        
        # رؤوس الطلبات (Headers) المطلوبة لتجنب الحظر - مستخرجة من ملف HAR
        self.headers = {
            "User-Agent": "Dart/3.11 (dart:io)",
            "x-platform-origin": "mobile-android",
            "platform": "android",
            "x-version": "1.5.15",
            "x-signature": "f320f896f3da2a5a0284f9af316efb4ab0432b26406413568db116fa9dc60feb",
            "Accept": "*/*"
        }

    async def check_account(self, session, user, password) -> dict:
        """فحص حساب واحد عبر API"""
        res = {"user": user, "pass": password, "balance": "فشل الدخول", "success": False}
        
        # 1. طلب تسجيل الدخول للحصول على التوكين
        payload = {
            "client_id": "myooredoo-app",
            "grant_type": "password",
            "username": user,
            "password": password
        }
        
        try:
            async with session.post(self.token_url, data=payload, headers=self.headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    token = data.get("access_token")
                    
                    if token:
                        # 2. استخدام التوكين لجلب الرصيد
                        balance_headers = self.headers.copy()
                        balance_headers["Authorization"] = f"Bearer {token}"
                        balance_headers["x-msisdn"] = user
                        
                        url = f"{self.balance_url}?msisdn={user}"
                        
                        async with session.get(url, headers=balance_headers, timeout=10) as bal_response:
                            if bal_response.status == 200:
                                bal_data = await bal_response.json()
                                balance = bal_data.get("accountBalance")
                                if balance is not None:
                                    res["balance"] = f"{balance} DA"
                                    res["success"] = True
                                else:
                                    res["balance"] = "رصيد غير متوفر"
                            else:
                                res["balance"] = "خطأ في جلب الرصيد"
                else:
                    if response.status == 401:
                        res["balance"] = "كلمة سر خاطئة"
                    else:
                        res["balance"] = f"خطأ في الاتصال ({response.status})"
                        
        except asyncio.TimeoutError:
            res["balance"] = "انتهى وقت الاتصال (Timeout)"
        except Exception as e:
            log.error(f"❌ API Error for {user}: {e}")
            res["balance"] = "خطأ في الشبكة"
            
        return res
