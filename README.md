# بوت تلجرام — حل كورس كيريو JavaScript

## الاستخدام

1. `/start`
2. ابعت **رقم الحساب** فقط
3. ابعت **كلمة المرور** فقط  
   (البوت بيمسح رسالة الباسورد قدر الإمكان ومش بيعرض بيانات الدخول)

## تشغيل على الكمبيوتر

```powershell
cd D:\Downloads\qureo-telegram-bot
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```

## تشغيل على الموبايل (Termux)

شوف الملف `TERMUX.md` — ينفع لأن مفيش متصفح، بس بايثون.

## ملاحظات

- التوكن في `.env`
- اختياري: `ALLOWED_USER_IDS=123,456` لتقييد الاستخدام
