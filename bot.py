"""VK-бот: расчёт кредита, графики, PDF-отчёт.

Бот работает в фоновом потоке, а основной процесс — Flask-сервер
(Render Web Service требует, чтобы процесс слушал PORT).
"""
import os
import json
import sqlite3
import threading
import logging
import time

import requests
from flask import Flask
from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from finance import annuity, differentiated
from charts import chart_structure, chart_balance_compare, chart_compare
from pdf_gen import generate_pdf

# ─── конфиг ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("credit-bot")

VK_TOKEN = os.environ.get("VK_TOKEN")
VK_GROUP_ID = os.environ.get("VK_GROUP_ID")
DB_PATH = os.environ.get("DB_PATH", "/tmp/state.db")
PORT = int(os.environ.get("PORT", "10000"))

if not VK_TOKEN or not VK_GROUP_ID:
    log.warning("VK_TOKEN / VK_GROUP_ID не заданы — бот не запустится, "
                "Flask будет отвечать только на health-check.")

# ─── БД состояний пользователей ─────────────────────────────────────────
_db_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.execute("""CREATE TABLE IF NOT EXISTS state(
    user_id INTEGER PRIMARY KEY,
    step    TEXT,
    amount  REAL,
    rate    REAL,
    months  INTEGER
)""")
_conn.commit()


def get_state(uid: int):
    with _db_lock:
        row = _conn.execute(
            "SELECT step, amount, rate, months FROM state WHERE user_id=?",
            (uid,),
        ).fetchone()
    if not row:
        return None
    return dict(zip(["step", "amount", "rate", "months"], row))


def set_state(uid: int, **kw):
    cur = get_state(uid) or {"step": None, "amount": None, "rate": None, "months": None}
    cur.update(kw)
    with _db_lock:
        _conn.execute(
            "INSERT OR REPLACE INTO state VALUES(?,?,?,?,?)",
            (uid, cur["step"], cur["amount"], cur["rate"], cur["months"]),
        )
        _conn.commit()


# ─── клавиатуры ─────────────────────────────────────────────────────────
def main_kb():
    kb = VkKeyboard(inline=False)
    kb.add_button("💰 Новый расчёт", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("ℹ️ О боте", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def result_kb():
    kb = VkKeyboard(inline=True)
    kb.add_callback_button(
        "📊 Аннуитет: структура",
        color=VkKeyboardColor.PRIMARY,
        payload={"cmd": "struct_ann"},
    )
    kb.add_line()
    kb.add_callback_button(
        "📊 Дифф.: структура",
        color=VkKeyboardColor.PRIMARY,
        payload={"cmd": "struct_diff"},
    )
    kb.add_line()
    kb.add_callback_button(
        "📈 Остаток долга",
        color=VkKeyboardColor.SECONDARY,
        payload={"cmd": "balance"},
    )
    kb.add_callback_button(
        "⚖️ Сравнение",
        color=VkKeyboardColor.SECONDARY,
        payload={"cmd": "compare"},
    )
    kb.add_line()
    kb.add_callback_button(
        "📄 PDF-отчёт",
        color=VkKeyboardColor.POSITIVE,
        payload={"cmd": "pdf"},
    )
    return kb.get_keyboard()


# ─── ленивая инициализация vk_api ───────────────────────────────────────
_vk_session = None
_vk = None
_longpoll = None


def _vk_init():
    global _vk_session, _vk, _longpoll
    if _vk is None:
        _vk_session = VkApi(token=VK_TOKEN)
        _vk = _vk_session.get_api()
        _longpoll = VkBotLongPoll(_vk_session, int(VK_GROUP_ID))


# ─── helpers для отправки ───────────────────────────────────────────────
def send(uid: int, text: str, **kw):
    _vk.messages.send(
        user_id=uid,
        message=text,
        random_id=get_random_id(),
        **kw,
    )


def send_photo(uid: int, img_bytes: bytes, caption: str = ""):
    upload_url = _vk.photos.getMessagesUploadServer(peer_id=uid)["upload_url"]
    r = requests.post(
        upload_url,
        files={"photo": ("chart.png", img_bytes, "image/png")},
    ).json()
    saved = _vk.photos.saveMessagesPhoto(
        photo=r["photo"], server=r["server"], hash=r["hash"]
    )[0]
    send(uid, caption,
         attachment=f'photo{saved["owner_id"]}_{saved["id"]}')


def send_doc(uid: int, file_bytes: bytes, fname: str, caption: str = ""):
    upload_url = _vk.docs.getMessagesUploadServer(peer_id=uid, type="doc")["upload_url"]
    r = requests.post(
        upload_url,
        files={"file": (fname, file_bytes, "application/pdf")},
    ).json()
    saved = _vk.docs.save(file=r["file"], title=fname)["doc"]
    send(uid, caption,
         attachment=f'doc{saved["owner_id"]}_{saved["id"]}')


# ─── тексты ─────────────────────────────────────────────────────────────
INFO = (
    "🤖 Я считаю кредиты по двум схемам:\n\n"
    "▫️ Аннуитет — равные платежи\n"
    "▫️ Дифференцированный — убывающие платежи\n\n"
    "Покажу графики структуры платежа, сравню переплаты и выдам "
    "PDF-отчёт с полным графиком на весь срок.\n\n"
    "Жми «Новый расчёт»."
)


# ─── обработка сообщений ────────────────────────────────────────────────
def handle_text(uid: int, text: str):
    text = (text or "").strip()
    low = text.lower()

    if low in ("/start", "начать", "start", "привет"):
        send(uid, INFO, keyboard=main_kb())
        return
    if "о боте" in low:
        send(uid, INFO, keyboard=main_kb())
        return
    if "новый расчёт" in low or "новый расчет" in low:
        set_state(uid, step="amount", amount=None, rate=None, months=None)
        send(uid, "💰 Введи сумму кредита в рублях (например, 1000000):")
        return

    s = get_state(uid)
    if not s or not s["step"] or s["step"] == "done":
        send(uid, "Нажми «Новый расчёт».", keyboard=main_kb())
        return

    try:
        v = float(text.replace(",", ".").replace(" ", ""))
    except ValueError:
        send(uid, "❌ Это не число. Попробуй ещё раз.")
        return

    if s["step"] == "amount":
        if not (0 < v <= 1e10):
            send(uid, "❌ Сумма от 1 до 10 млрд ₽.")
            return
        set_state(uid, amount=v, step="rate")
        send(uid, f"✅ {v:,.0f} ₽\n\n📈 Введи ставку (% годовых, например 15.5):")
    elif s["step"] == "rate":
        if not (0 < v <= 200):
            send(uid, "❌ Ставка от 0 до 200%.")
            return
        set_state(uid, rate=v, step="months")
        send(uid, f"✅ {v}%\n\n📅 Срок в месяцах (например, 60):")
    elif s["step"] == "months":
        m = int(v)
        if not (0 < m <= 600):
            send(uid, "❌ Срок от 1 до 600 мес.")
            return
        set_state(uid, months=m, step="done")
        show_result(uid)


def show_result(uid: int):
    s = get_state(uid)
    a = annuity(s["amount"], s["rate"], s["months"])
    d = differentiated(s["amount"], s["rate"], s["months"])
    diff_save = a.total_interest - d.total_interest

    txt = (
        f"📊 Расчёт готов\n\n"
        f"Сумма: {s['amount']:,.0f} ₽\n"
        f"Ставка: {s['rate']}% • Срок: {s['months']} мес.\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔵 АННУИТЕТ\n"
        f"  Платёж: {a.first_payment:,.2f} ₽/мес\n"
        f"  Всего: {a.total_paid:,.2f} ₽\n"
        f"  Переплата: {a.total_interest:,.2f} ₽\n\n"
        f"🔴 ДИФФЕРЕНЦИРОВАННЫЙ\n"
        f"  Первый: {d.first_payment:,.2f} ₽\n"
        f"  Последний: {d.last_payment:,.2f} ₽\n"
        f"  Всего: {d.total_paid:,.2f} ₽\n"
        f"  Переплата: {d.total_interest:,.2f} ₽\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💡 Экономия дифф.: {diff_save:,.2f} ₽"
    )
    send(uid, txt, keyboard=result_kb())


def handle_callback(obj: dict):
    uid = obj["user_id"]
    peer_id = obj["peer_id"]
    eid = obj["event_id"]
    payload = obj.get("payload") or {}
    cmd = payload.get("cmd")

    s = get_state(uid)
    if not s or s.get("step") != "done":
        _vk.messages.sendMessageEventAnswer(
            event_id=eid, user_id=uid, peer_id=peer_id,
            event_data=json.dumps({
                "type": "show_snackbar",
                "text": "Сначала сделай расчёт",
            }),
        )
        return

    # пустой ответ — чтобы убрать индикатор загрузки на кнопке
    _vk.messages.sendMessageEventAnswer(
        event_id=eid, user_id=uid, peer_id=peer_id,
    )

    a = annuity(s["amount"], s["rate"], s["months"])
    d = differentiated(s["amount"], s["rate"], s["months"])

    if cmd == "struct_ann":
        send_photo(uid, chart_structure(a, "Аннуитет: структура платежа"),
                   "📊 Видно, как доля основного долга растёт со временем.")
    elif cmd == "struct_diff":
        send_photo(uid, chart_structure(d, "Дифференцированный: структура"),
                   "📊 Проценты убывают линейно.")
    elif cmd == "balance":
        send_photo(uid, chart_balance_compare(a, d),
                   "📈 Дифф. погашает основной долг быстрее.")
    elif cmd == "compare":
        send_photo(uid, chart_compare(a, d),
                   "⚖️ Сравнение размеров ежемесячного платежа.")
    elif cmd == "pdf":
        pdf = generate_pdf(s["amount"], s["rate"], s["months"], a, d)
        send_doc(uid, pdf, "credit_report.pdf",
                 "📄 Полный график платежей на весь срок.")


# ─── главный цикл бота ──────────────────────────────────────────────────
def bot_loop():
    if not VK_TOKEN or not VK_GROUP_ID:
        log.error("Бот не запущен: нет VK_TOKEN или VK_GROUP_ID.")
        return

    while True:
        try:
            _vk_init()
            log.info("VK Long Poll started.")
            for ev in _longpoll.listen():
                try:
                    if ev.type == VkBotEventType.MESSAGE_NEW:
                        msg = ev.obj.message
                        handle_text(msg["from_id"], msg.get("text", ""))
                    elif ev.type == VkBotEventType.MESSAGE_EVENT:
                        handle_callback(ev.obj)
                except Exception as e:
                    log.exception("Ошибка обработки события: %s", e)
        except Exception as e:
            log.exception("Long Poll упал, перезапуск через 5с: %s", e)
            time.sleep(5)


# ─── Flask: health-check (нужен Render Web Service) ─────────────────────
app = Flask(__name__)


@app.route("/")
def root():
    return "Credit calculator VK bot is running.", 200


@app.route("/health")
def health():
    return {"status": "ok"}, 200


# поток с ботом стартует при импорте — gunicorn делает один импорт
_bot_thread = threading.Thread(target=bot_loop, daemon=True, name="vk-bot")
_bot_thread.start()


if __name__ == "__main__":
    # локальный запуск без gunicorn
    app.run(host="0.0.0.0", port=PORT)
