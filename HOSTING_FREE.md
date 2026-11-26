# استضافة مجانية بدون بطاقة

الريبو جاهز:
https://github.com/abdallahsultan74/qureo-telegram-bot

Start command: `python qureo_bot.py`  
Env: `TELEGRAM_BOT_TOKEN=...`

## 1) دلوقتي (شغّال)
البوت شغال على جهازك ويتفتح مع ويندوز تلقائي.
شرط: الكمبيوتر فاتح + نت.

## 2) FadeHost — بوت مجاني 24/7 بدون بطاقة
https://fadehost.com/telegram-bot-hosting/

1. اعمل حساب بإيميل فقط
2. Apps → Host something → Telegram bot
3. اختار الريبو من GitHub
4. حط `TELEGRAM_BOT_TOKEN`
5. Deploy

ملاحظة: لو اللوحة طالعة Error 522، استنى شوية وحاول تاني.

## 3) Serv00 — مجاني + SSH بدون بطاقة
https://www.serv00.com/ → Register account

بعد ما يوصلك اللوجين SSH، ابعتلي بيانات الدخول (من غير الباسورد في الشات لو مش مرتاح — أو شغّل الأوامر دي بنفسك):

```bash
cd ~
git clone https://github.com/abdallahsultan74/qureo-telegram-bot.git
cd qureo-telegram-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='توكن_البوت'
nohup python qureo_bot.py > bot.log 2>&1 &
```

سجّل دخول كل 90 يوم عشان الحساب يفضل موجود.
