#!/data/data/com.termux/files/usr/bin/bash
# شغّال على Termux — يفضل البوت فاتح حتى لو قفلت الشاشة أو طلعت من Termux

cd "$(dirname "$0")"

termux-wake-lock 2>/dev/null || true

if ! python -c "import telegram" 2>/dev/null; then
  pip install -q python-telegram-bot requests
fi

echo "البوت شغال… متقفلش Termux من Recent Apps"
echo "عشان تطلعه في الخلفية: اضغط Home بس (متعملش Swipe لإغلاق)"
echo "للإيقاف: Ctrl+C"
python qureo_bot.py
