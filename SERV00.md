# تشغيل البوت مجانًا بدون بطاقة

## الخيار الأسهل دلوقتي (شغّال)

البوت شغال على جهازك ويتفتح مع ويندوز تلقائي.
شرط واحد: الكمبيوتر يكون فاتح ومتصل بالنت.

## FadeHost (بوت مجاني 24/7 بدون بطاقة)

1. ادخل: https://fadehost.com
2. اعمل حساب (من غير بطاقة)
3. أنشئ **Telegram Bot / App** مجاني
4. اربطه بريبو GitHub:
   `https://github.com/abdallahsultan74/qureo-telegram-bot`
5. Start command:
   ```
   python qureo_bot.py
   ```
6. Environment variable:
   ```
   TELEGRAM_BOT_TOKEN=توكن_البوت
   ```

## Serv00 (مجاني + SSH، من غير بطاقة)

1. سجّل من: https://www.serv00.com/ → Register account
2. من اللوحة فعّل **Run your own applications**
3. ادخل SSH بعد ما يوصلك اللوجين
4. نفّذ:

```bash
cd ~
git clone https://github.com/abdallahsultan74/qureo-telegram-bot.git
cd qureo-telegram-bot
python3 -m venv .venv
source .venv/bin/activate
pip install python-telegram-bot python-dotenv requests
# curl_cffi ممكن مينفعش على FreeBSD — requests يكفي
export TELEGRAM_BOT_TOKEN='توكن_البوت'
nohup python qureo_bot.py > bot.log 2>&1 &
```

سجّل دخول على اللوحة أو SSH مرة كل 90 يوم عشان الحساب متتحذفش.
