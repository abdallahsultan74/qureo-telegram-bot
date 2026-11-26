# تشغيل البوت من الموبايل بدون ما يتقفل

Pydroid **مش مناسب** للخلفية — أندرويد بيوقفّه لما تطلع من التطبيق.

استخدم **Termux** (من F-Droid، مش Play Store).

## مرة واحدة — التثبيت

```bash
pkg update -y
pkg install -y python
pip install python-telegram-bot requests
```

انسخ `qureo_bot.py` لمجلد Termux، مثلاً:

```bash
mkdir -p ~/qureo
# انقل الملف لـ ~/qureo/qureo_bot.py (من Download عبر cp)
cp /sdcard/Download/qureo_bot.py ~/qureo/
cd ~/qureo
```

## كل مرة — التشغيل (يفضل شغال)

```bash
cd ~/qureo
termux-wake-lock
python qureo_bot.py
```

أو:

```bash
bash start_bot.sh
```

بعد ما يشتغل: اضغط **Home** بس.  
**متعملش** swipe لإغلاق Termux من التطبيقات الأخيرة.

## عشان البطارية متوقفوش

إعدادات أندرويد → التطبيقات → Termux → البطارية → **بدون تقييد / Unrestricted**

## اختياري: tmux (تقدر تقفل الجلسة وترجع)

```bash
pkg install -y tmux
tmux new -s qureo
termux-wake-lock
python qureo_bot.py
# اخرج من الجلسة من غير إيقاف: Ctrl+b ثم d
# الرجوع: tmux attach -t qureo
```

## الاستخدام

افتح البوت على تلجرام → `/start` → رقم الحساب → كلمة المرور.
