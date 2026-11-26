"""
بوت تلجرام — حل كورس كيريو JavaScript (ملف واحد)

مهم: Pydroid بيقفل لما تطلع منه.
شغّله من Termux عشان يفضل شغال في الخلفية:

  pkg update -y && pkg install -y python
  pip install python-telegram-bot requests
  termux-wake-lock
  python qureo_bot.py

بعد التشغيل اضغط Home فقط — متسحبهوش من Recent Apps.
في إعدادات البطارية: Termux → بدون تقييد.

(اختياري على الكمبيوتر: curl_cffi)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    from curl_cffi import requests as http
    _USE_CURL_CFFI = True
except ImportError:
    import requests as http
    _USE_CURL_CFFI = False

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# التوكن من Environment Variable (مطلوب على الاستضافة)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
# اختياري: قيّد على يوزرات تلجرام معيّنة، مثال: {"123456789"}
_allowed_raw = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS: set[str] = {
    x.strip() for x in _allowed_raw.split(",") if x.strip()
}

PORTAL = "https://me-portal.qureo.education"
TP = "https://me-tp.qureo.education"
ANSWERS_BASE = (
    "https://raw.githubusercontent.com/vfggf95565/QUREO-Answers/main/JavaScript"
)
SECTION_ID = 5
FIRST_CHAPTER = 90001
LAST_CHAPTER = 90042
IMPERSONATE = "chrome124"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Origin": PORTAL,
    "Referer": f"{PORTAL}/",
}

ASK_ID, ASK_PASSWORD = range(2)
ProgressCb = Callable[[str], None]

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("qureo-bot")

_busy_chats: set[int] = set()
_busy_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=2)
ID_RE = re.compile(r"^\d{6,12}$")


# ---------- Qureo solver ----------
def _norm(s: str | None) -> str:
    s = s or ""
    s = re.sub(r"\[\[[^\]]*\]\]", "", s)
    s = re.sub(r"[\s\u3000\n\r\t]+", "", s)
    s = s.replace("“", '"').replace("”", '"')
    return s.lower()


def _code_from_answer(a: dict | None) -> str | None:
    if not a:
        return None
    t = a.get("type")
    if t in ("code", "text"):
        return a.get("value")
    if t in ("fill", "partial"):
        return a.get("full_code") or a.get("value")
    return a.get("full_code") or a.get("value")


def _match_choice(choices: list[dict], expected: str | None) -> dict | None:
    if not choices:
        return None
    n_exp = _norm(expected)
    for c in choices:
        if _norm(c.get("content")) == n_exp:
            return c
    for c in choices:
        nc = _norm(c.get("content"))
        if n_exp and (n_exp in nc or nc in n_exp):
            return c
    for c in choices:
        nc = re.sub(r"processing|عملية|process", "", _norm(c.get("content")))
        ne = re.sub(r"processing|عملية|process", "", n_exp)
        if nc == ne:
            return c
    return choices[0]


class QureoSolver:
    def __init__(self, student_id: str, password: str, on_progress: ProgressCb | None = None):
        self.student_id = student_id.strip()
        self.password = password
        self.on_progress = on_progress or (lambda _msg: None)
        if _USE_CURL_CFFI:
            self.session = http.Session(impersonate=IMPERSONATE)
        else:
            self.session = http.Session()
            self.session.headers.update(BROWSER_HEADERS)
        self._answers_cache: dict[int, dict | None] = {}

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def _emit(self, msg: str) -> None:
        self.on_progress(msg)

    def login(self) -> dict[str, Any]:
        mode = "curl_cffi" if _USE_CURL_CFFI else "requests"
        self._emit(f"جاري تسجيل الدخول… ({mode})")
        # زيارة الصفحة أولاً لجلب كوكيز الجلسة
        try:
            self.session.get(f"{PORTAL}/", timeout=60)
        except Exception:
            pass

        r = self.session.post(
            f"{PORTAL}/oauth2/password-login",
            json={"student_id": self.student_id, "password": self.password},
            headers={
                "Content-Type": "application/json",
                "Origin": PORTAL,
                "Referer": f"{PORTAL}/",
            },
            allow_redirects=False,
            timeout=60,
        )
        if r.status_code not in (200, 302, 303):
            try:
                data = r.json()
                err = data.get("error") or data.get("error_description") or r.text[:200]
            except Exception:
                err = (r.text or "")[:200] or f"empty body status={r.status_code}"
            if "password_mismatch" in str(err) or "invalid" in str(err).lower():
                raise RuntimeError("رقم الحساب أو كلمة المرور غلط")
            if r.status_code in (403, 429) or "cloudflare" in str(err).lower():
                raise RuntimeError(
                    f"المنصة رفضت الطلب (status {r.status_code}). جرّب تاني بعد دقيقة."
                )
            raise RuntimeError(f"فشل الدخول (status {r.status_code}): {err}")

        info = self.session.get(f"{PORTAL}/oauth2/userinfo", timeout=60)
        if info.status_code != 200:
            raise RuntimeError(
                f"فشل جلب بيانات المستخدم بعد الدخول (status {info.status_code})"
            )

        self.session.get(f"{TP}/course/javascript_ar", timeout=60)
        me = self.session.get(f"{TP}/api/study/students/me", timeout=60)
        if me.status_code != 200:
            self.session.get(
                f"{TP}/oauth2/refresh",
                params={
                    "redirect_url": "/api/study/students/me",
                    "fallback_url": f"{TP}/login",
                },
                allow_redirects=True,
                timeout=60,
            )
            me = self.session.get(f"{TP}/api/study/students/me", timeout=60)

        if me.status_code != 200:
            raise RuntimeError(f"الجلسة لم تصل لمنصة التعلم (status {me.status_code})")
        ctype = (me.headers.get("content-type") or "").lower()
        if "json" not in ctype:
            raise RuntimeError(
                "استجابة غير متوقعة من منصة التعلم "
                f"(content-type={ctype or 'unknown'})"
            )

        self._emit("تم تسجيل الدخول ✅")
        return me.json()

    def _get(self, path: str) -> Any:
        r = self.session.get(f"{TP}{path}", timeout=60)
        r.raise_for_status()
        if not r.content:
            return None
        return r.json()

    def _put(self, path: str, body: Any | None = None) -> Any:
        kwargs: dict[str, Any] = {"timeout": 60}
        if body is not None:
            kwargs["json"] = body
        return self.session.put(f"{TP}{path}", **kwargs)

    def _load_answers(self, level: int) -> dict | None:
        if level in self._answers_cache:
            return self._answers_cache[level]
        r = self.session.get(f"{ANSWERS_BASE}/{level}.json", timeout=60)
        if r.status_code != 200:
            self._answers_cache[level] = None
            return None
        data = r.json()
        self._answers_cache[level] = data
        return data

    def _review_list(self, ans: dict | None) -> list[dict]:
        if not ans or "review" not in ans or "questions" not in ans["review"]:
            return []
        review = ans["review"]
        order = review.get("_order") or list(review["questions"].keys())
        return [review["questions"][k] for k in order if k in review["questions"]]

    def progress(self) -> dict[str, Any]:
        diamond = self.session.get(
            f"{TP}/api/study/students/courses/javascript_ar/diamond",
            timeout=60,
        ).text.strip()
        chapters = self._get(f"/api/study/students/sections/{SECTION_ID}/chapters") or []
        done = [c for c in chapters if c.get("completed_at")]
        pending = [
            cid
            for cid in range(FIRST_CHAPTER, LAST_CHAPTER + 1)
            if not any(c.get("chapter_id") == cid and c.get("completed_at") for c in chapters)
        ]
        return {
            "diamond": diamond,
            "done": len(done),
            "total": LAST_CHAPTER - FIRST_CHAPTER + 1,
            "pending": pending,
        }

    def _complete_lecture(self, lecture_id: int) -> None:
        self._put(f"/api/study/students/lectures/{lecture_id}")
        lec = self._get(f"/api/study/lectures/{lecture_id}") or {}
        for talk in lec.get("talks") or []:
            ttype = talk.get("type")
            tid = talk.get("id")
            body = talk.get("body") or {}
            if ttype == "try":
                codes = body.get("codes") or []
                editable = next((c for c in codes if c.get("editable")), None)
                code = (
                    (editable or {}).get("model_answer")
                    or (editable or {}).get("code")
                    or (codes[0].get("code") if codes else "")
                    or ""
                )
                lang = (editable or {}).get("lang") or "javascript"
                self._put(
                    f"/api/study/students/lecture-talks/{tid}",
                    {"value": {"try": {"lang": lang, "answer": code}}},
                )
            elif ttype in ("choice_question", "choice_survey"):
                choices = body.get("choices") or []
                val = (choices[0].get("value") if choices else "1") or "1"
                self._put(
                    f"/api/study/students/lecture-talks/{tid}",
                    {"value": {ttype: {"value": str(val)}}},
                )
            elif ttype == "puzzle":
                ans = body.get("model_answer") or body.get("answer")
                if ans is not None:
                    self._put(
                        f"/api/study/students/lecture-talks/{tid}",
                        {"value": {"puzzle": {"answer": ans}}},
                    )
        self._put(f"/api/study/students/lectures/{lecture_id}/complete")

    def _complete_test(self, chapter_id: int, test_type: str, level: int) -> dict:
        ans = self._load_answers(level)
        rev = self._review_list(ans)
        self._put(f"/api/study/students/chapters/{chapter_id}/test")
        time.sleep(0.1)
        qs = self._get(f"/api/study/chapters/{chapter_id}/test")
        if not isinstance(qs, list):
            return {"error": "no questions", "wrong": -1, "total": 0}

        base = "review-questions" if test_type == "review" else "test-questions"
        wrong = 0
        for i, q in enumerate(qs):
            expected = rev[i] if i < len(rev) else None
            qmeta = q.get("question") or {}
            qid = qmeta.get("id")
            qtype = qmeta.get("type")
            if qtype == "choice":
                exp_val = _code_from_answer((expected or {}).get("answer"))
                choice = _match_choice(q.get("choices") or [], exp_val)
                r = self._put(
                    f"/api/study/students/{base}/{qid}/answer/choice",
                    {"choice_id": choice["id"]},
                )
                try:
                    data = r.json()
                    if data.get("result", {}).get("correct") is False:
                        wrong += 1
                except Exception:
                    pass
            elif qtype == "description":
                code = _code_from_answer((expected or {}).get("answer"))
                descs = q.get("descriptions") or []
                desc = next((d for d in descs if d.get("editable")), None) or (
                    descs[0] if descs else None
                )
                ans_obj = (expected or {}).get("answer") or {}
                if desc and desc.get("placeholders") and ans_obj.get("blanks"):
                    built = desc.get("code") or ""
                    for idx, ph in enumerate(desc["placeholders"]):
                        blank = (
                            ans_obj["blanks"][idx]
                            if idx < len(ans_obj["blanks"])
                            else ""
                        )
                        built = built.replace(ph.get("name", ""), blank)
                    code = built
                elif ans_obj.get("full_code"):
                    code = ans_obj["full_code"]
                r = self._put(
                    f"/api/study/students/{base}/{qid}/answer/description",
                    {"answer_code": code or ""},
                )
                try:
                    data = r.json()
                    if data.get("result", {}).get("correct") is False:
                        wrong += 1
                except Exception:
                    pass

        chapter = self._get(f"/api/study/students/chapters/{chapter_id}") or {}
        return {"wrong": wrong, "total": len(qs), "chapter": chapter}

    def complete_chapter(self, chapter_id: int) -> dict:
        level = chapter_id - 90000
        meta = self._get(f"/api/study/chapters/{chapter_id}") or {}
        chapter = meta.get("chapter") or {}
        name = chapter.get("name") or str(chapter_id)
        test_type = chapter.get("test_type") or "review"
        for lec in meta.get("lectures") or []:
            self._complete_lecture(lec["id"])
        test = self._complete_test(chapter_id, test_type, level)
        ch = test.get("chapter") or {}
        return {
            "id": chapter_id,
            "name": name,
            "best": ch.get("best_correct_count"),
            "diamond": ch.get("diamond"),
            "done": bool(ch.get("completed_at")),
            "wrong": test.get("wrong"),
            "total": test.get("total"),
            "error": test.get("error"),
        }

    def solve_all(self) -> dict[str, Any]:
        self.login()
        prog = self.progress()
        self._emit(
            f"التقدم الحالي: {prog['done']}/{prog['total']} فصل — "
            f"{prog['diamond']} ألماسة"
        )
        pending = prog["pending"]
        if not pending:
            self._emit("الكورس مكتمل بالفعل ✅")
            return {"already_done": True, **prog}

        results = []
        for cid in pending:
            self._emit(f"جاري حل الفصل {cid - 90000}…")
            try:
                row = self.complete_chapter(cid)
                results.append(row)
                self._emit(
                    f"✓ فصل {cid - 90000} ({row.get('name')}) — "
                    f"ألماس {row.get('diamond')} | "
                    f"أخطاء {row.get('wrong')}/{row.get('total')}"
                )
            except Exception as e:
                results.append({"id": cid, "error": str(e)})
                self._emit(f"✗ فصل {cid - 90000}: {e}")
                break
            time.sleep(0.05)

        final = self.progress()
        self._emit(
            f"انتهى. النتيجة: {final['done']}/{final['total']} فصل — "
            f"{final['diamond']} ألماسة"
        )
        return {"results": results, **final}


def solve(student_id: str, password: str, on_progress: ProgressCb | None = None) -> dict:
    solver = QureoSolver(student_id, password, on_progress)
    try:
        return solver.solve_all()
    finally:
        solver.close()


# ---------- Telegram bot ----------
def _allowed(user_id: int | None) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id is not None and str(user_id) in ALLOWED_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_user or not update.message:
        return ConversationHandler.END
    if not _allowed(update.effective_user.id):
        await update.message.reply_text("غير مصرح لك باستخدام هذا البوت.")
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "مرحباً 👋\n"
        "ابعت رقم حساب كيريو (Login ID) فقط.\n"
        "بعدها هطلب منك كلمة المرور.\n\n"
        "للإلغاء: /cancel"
    )
    return ASK_ID


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await start(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        context.user_data.clear()
        await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    with _busy_lock:
        busy = chat_id in _busy_chats
    await update.message.reply_text("شغال دلوقتي…" if busy else "فاضي وجاهز.")


async def receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return ASK_ID
    text = (update.message.text or "").strip()
    if not ID_RE.match(text):
        await update.message.reply_text(
            "الرقم مش صحيح. ابعت Login ID أرقام فقط (من 6 لـ 12 رقم)."
        )
        return ASK_ID

    context.user_data["student_id"] = text
    try:
        await update.message.delete()
    except Exception:
        pass

    await update.message.chat.send_message(
        "تمام. دلوقتي ابعت كلمة المرور فقط."
    )
    return ASK_PASSWORD


async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.effective_chat or not update.effective_user:
        return ConversationHandler.END

    password = (update.message.text or "").strip()
    student_id = context.user_data.get("student_id")

    try:
        await update.message.delete()
    except Exception:
        pass

    if not student_id:
        await update.message.chat.send_message("ابدأ من جديد بـ /start")
        return ConversationHandler.END

    if not password or len(password) < 4:
        await update.message.chat.send_message(
            "كلمة المرور قصيرة أو فاضية. ابعتها تاني، أو /cancel للإلغاء."
        )
        return ASK_PASSWORD

    chat_id = update.effective_chat.id
    with _busy_lock:
        if chat_id in _busy_chats:
            await update.message.chat.send_message(
                "في عملية شغّالة بالفعل. استنى تخلص."
            )
            context.user_data.clear()
            return ConversationHandler.END
        _busy_chats.add(chat_id)

    context.user_data.clear()

    await update.message.chat.send_message(
        "بدأنا الحل.\nممكن ياخد دقايق — هبعتلك تحديثات."
    )

    async def send_progress(msg: str) -> None:
        try:
            await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
            await context.bot.send_message(chat_id, msg)
        except Exception as e:
            log.warning("progress send failed: %s", e)

    loop = asyncio.get_running_loop()

    def progress_sync(msg: str) -> None:
        fut = asyncio.run_coroutine_threadsafe(send_progress(msg), loop)
        try:
            fut.result(timeout=30)
        except Exception as e:
            log.warning("progress sync failed: %s", e)

    def job() -> dict:
        return solve(student_id, password, on_progress=progress_sync)

    try:
        result = await loop.run_in_executor(_executor, job)
        done = result.get("done")
        total = result.get("total")
        diamond = result.get("diamond")
        if result.get("already_done"):
            text = f"✅ الحساب مكتمل أصلاً\nالفصول: {done}/{total}\nالألماس: {diamond}/210"
        else:
            text = f"✅ خلص\nالفصول: {done}/{total}\nالألماس: {diamond}/210"
        await context.bot.send_message(chat_id, text)
    except Exception as e:
        log.exception("solve failed")
        err = str(e)
        err = re.sub(re.escape(password), "***", err)
        err = re.sub(re.escape(student_id), "***", err)
        await context.bot.send_message(chat_id, f"❌ حصل خطأ:\n{err}")
    finally:
        with _busy_lock:
            _busy_chats.discard(chat_id)

    return ConversationHandler.END


def _start_health_server() -> None:
    """Render (وغيره) يحتاج يسمع على PORT — وإلا الخدمة تعتبر فاشلة."""
    port_s = os.getenv("PORT")
    if not port_s:
        return
    port = int(port_s)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    server = HTTPServer(("0.0.0.0", port), Handler)
    t = threading.Thread(target=server.serve_forever, name="health", daemon=True)
    t.start()
    log.info("Health server on :%s", port)


def _start_keepalive() -> None:
    """يمنع Render Free من النوم: طلب لنفس الخدمة كل 5 دقايق."""
    base = (
        os.getenv("RENDER_EXTERNAL_URL")
        or os.getenv("KEEPALIVE_URL")
        or ""
    ).rstrip("/")
    if not base:
        return

    def loop() -> None:
        url = f"{base}/"
        while True:
            time.sleep(280)
            try:
                http.get(url, timeout=30)
                log.info("keepalive ok")
            except Exception as e:
                log.warning("keepalive failed: %s", e)

    threading.Thread(target=loop, name="keepalive", daemon=True).start()
    log.info("Keepalive → %s", base)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN or "XXXX" in TELEGRAM_BOT_TOKEN:
        raise SystemExit(
            "حط TELEGRAM_BOT_TOKEN في متغير البيئة أو ملف .env"
        )

    _start_health_server()
    _start_keepalive()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("help", help_cmd),
        ],
        states={
            ASK_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id)],
            ASK_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(conv)
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("cancel", cancel))

    log.info("Bot starting… (curl_cffi=%s)", _USE_CURL_CFFI)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
