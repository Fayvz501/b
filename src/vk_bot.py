"""VK-бот: расчёт кредита, графики, PDF, история, сложный процент.

ВАЖНО: используется VkBotLongPoll (для сообществ), а не VkLongPoll.
Только VkBotLongPoll умеет принимать события message_event,
без которых callback-кнопки не работают.
"""
import json
import logging
import threading
import time

import requests
from vk_api import VkApi
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

from src.config import VK_TOKEN, VK_GROUP_ID
from src.db_manager import (init_db, save_calc, get_history,
                             get_state, set_state, clear_state)
from src.finance import annuity, differentiated, compound_interest
from src.charts import chart_structure, chart_balance_compare, chart_compare
from src.pdf_engine import build_report
from src.keyboards import main_menu, back_menu, result_kb

log = logging.getLogger("credit-bot")

# ── ленивая инициализация vk_api ────────────────────────────────────────
_vk_session = None
_vk = None
_longpoll = None


def _vk_init():
    global _vk_session, _vk, _longpoll
    if _vk is None:
        _vk_session = VkApi(token=VK_TOKEN)
        _vk = _vk_session.get_api()
        _longpoll = VkBotLongPoll(_vk_session, int(VK_GROUP_ID))


# ── helpers для отправки ────────────────────────────────────────────────
def send(uid: int, text: str, **kw):
    _vk.messages.send(user_id=uid, message=text,
                      random_id=get_random_id(), **kw)


def send_photo(uid: int, img_bytes: bytes, caption: str = ""):
    upload_url = _vk.photos.getMessagesUploadServer(peer_id=uid)["upload_url"]
    r = requests.post(upload_url,
                      files={"photo": ("c.png", img_bytes, "image/png")}).json()
    saved = _vk.photos.saveMessagesPhoto(
        photo=r["photo"], server=r["server"], hash=r["hash"]
    )[0]
    send(uid, caption, attachment=f'photo{saved["owner_id"]}_{saved["id"]}')


def send_doc(uid: int, file_bytes: bytes, fname: str, caption: str = ""):
    upload_url = _vk.docs.getMessagesUploadServer(
        peer_id=uid, type="doc")["upload_url"]
    r = requests.post(
        upload_url,
        files={"file": (fname, file_bytes, "application/pdf")},
    ).json()
    saved = _vk.docs.save(file=r["file"], title=fname)["doc"]
    send(uid, caption, attachment=f'doc{saved["owner_id"]}_{saved["id"]}')


# ── тексты ──────────────────────────────────────────────────────────────
WELCOME = (
    "💼 Finance Pro — кредитный калькулятор\n\n"
    "Что я умею:\n"
    "📈 Рассчитать кредит — аннуитет vs дифф., графики, PDF\n"
    "💰 Сложный процент — капитализация для вкладов\n"
    "📜 История — последние расчёты\n\n"
    "Выбери действие на клавиатуре."
)

INFO = (
    "🤖 Я считаю кредиты по двум схемам:\n\n"
    "▫️ Аннуитет — равные платежи весь срок\n"
    "▫️ Дифференцированный — убывающие платежи\n\n"
    "Покажу графики структуры платежа, сравню переплаты "
    "и выдам PDF-отчёт с полным графиком на весь срок."
)


# ── обработка команд ────────────────────────────────────────────────────
def _to_menu(uid: int):
    clear_state(uid)
    send(uid, WELCOME, keyboard=main_menu())


def _show_history(uid: int):
    rows = get_history(uid)
    if not rows:
        send(uid, "📭 История пуста.\nСделай первый расчёт.",
             keyboard=main_menu())
        return
    out = ["📜 Последние расчёты:\n"]
    for c_type, amount, rate, months, over, dt in rows:
        out.append(
            f"• {c_type}: {amount:,.0f} ₽ × {rate}% × {months} мес.\n"
            f"  Переплата/доход: {over:,.2f} ₽  ({dt[:16]})"
        )
    send(uid, "\n".join(out), keyboard=main_menu())


def handle_text(uid: int, text: str):
    text = (text or "").strip()
    low = text.lower()

    if low in ("/start", "start", "начать", "привет"):
        _to_menu(uid); return
    if "в меню" in low:
        _to_menu(uid); return
    if "о боте" in low:
        send(uid, INFO, keyboard=main_menu()); return
    if "история" in low:
        _show_history(uid); return
    if "рассчитать кредит" in low:
        set_state(uid, mode="loan", step="amount",
                  amount=None, rate=None, months=None)
        send(uid, "💰 Введи сумму кредита в рублях (например, 1000000):",
             keyboard=back_menu())
        return
    if "сложный процент" in low:
        set_state(uid, mode="deposit", step="amount",
                  amount=None, rate=None, months=None)
        send(uid, "💰 Сумма вклада в рублях:", keyboard=back_menu())
        return

    s = get_state(uid)
    if not s or not s.get("step") or s["step"] == "done":
        send(uid, "Выбери действие на клавиатуре.", keyboard=main_menu())
        return

    # парсим число
    try:
        v = float(text.replace(",", ".").replace(" ", ""))
    except ValueError:
        send(uid, "❌ Это не число. Попробуй ещё раз.")
        return

    step = s["step"]
    mode = s["mode"]

    if step == "amount":
        if not (0 < v <= 1e10):
            send(uid, "❌ Сумма от 1 до 10 млрд ₽."); return
        set_state(uid, amount=v, step="rate")
        send(uid, f"✅ {v:,.0f} ₽\n\n📈 Введи ставку (% годовых, например 15.5):")
    elif step == "rate":
        if not (0 < v <= 200):
            send(uid, "❌ Ставка от 0 до 200%."); return
        set_state(uid, rate=v, step="months")
        send(uid, f"✅ {v}%\n\n📅 Срок в месяцах (например, 60):")
    elif step == "months":
        m = int(v)
        if not (0 < m <= 600):
            send(uid, "❌ Срок от 1 до 600 мес."); return
        set_state(uid, months=m, step="done")
        if mode == "loan":
            _show_loan_result(uid)
        else:
            _show_deposit_result(uid)


def _show_loan_result(uid: int):
    s = get_state(uid)
    a = annuity(s["amount"], s["rate"], s["months"])
    d = differentiated(s["amount"], s["rate"], s["months"])
    saving = a.total_interest - d.total_interest

    save_calc(uid, "Кредит", s["amount"], s["rate"], s["months"],
              a.total_interest)

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
        f"💡 Экономия дифф.: {saving:,.2f} ₽"
    )
    send(uid, txt, keyboard=result_kb())


def _show_deposit_result(uid: int):
    s = get_state(uid)
    res = compound_interest(s["amount"], s["rate"], s["months"])
    save_calc(uid, "Вклад", s["amount"], s["rate"], s["months"], res["profit"])

    txt = (
        f"💰 Сложный процент (капитализация ежемесячная)\n\n"
        f"Вклад: {res['principal']:,.2f} ₽\n"
        f"Ставка: {res['rate']}% годовых\n"
        f"Срок: {res['months']} мес.\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Итоговая сумма: {res['final']:,.2f} ₽\n"
        f"Доход: {res['profit']:,.2f} ₽"
    )
    send(uid, txt, keyboard=main_menu())
    clear_state(uid)


def handle_callback(obj: dict):
    uid = obj["user_id"]
    peer_id = obj["peer_id"]
    eid = obj["event_id"]
    payload = obj.get("payload") or {}
    cmd = payload.get("cmd")

    s = get_state(uid)
    if not s or s.get("step") != "done" or s.get("mode") != "loan":
        _vk.messages.sendMessageEventAnswer(
            event_id=eid, user_id=uid, peer_id=peer_id,
            event_data=json.dumps({
                "type": "show_snackbar",
                "text": "Сначала сделай расчёт кредита",
            }),
        )
        return

    # снимаем индикатор загрузки на кнопке
    _vk.messages.sendMessageEventAnswer(
        event_id=eid, user_id=uid, peer_id=peer_id)

    a = annuity(s["amount"], s["rate"], s["months"])
    d = differentiated(s["amount"], s["rate"], s["months"])

    if cmd == "struct_ann":
        send_photo(uid, chart_structure(a, "Аннуитет: структура платежа"),
                   "📊 Видно, как доля основного долга растёт со временем.")
    elif cmd == "struct_diff":
        send_photo(uid, chart_structure(d, "Дифф.: структура платежа"),
                   "📊 Проценты убывают линейно.")
    elif cmd == "balance":
        send_photo(uid, chart_balance_compare(a, d),
                   "📈 Дифф. погашает основной долг быстрее.")
    elif cmd == "compare":
        send_photo(uid, chart_compare(a, d),
                   "⚖️ Сравнение размеров ежемесячного платежа.")
    elif cmd == "pdf":
        pdf = build_report(s["amount"], s["rate"], s["months"], a, d)
        send_doc(uid, pdf, "credit_report.pdf",
                 "📄 Полный график платежей на весь срок.")


# ── главный цикл ────────────────────────────────────────────────────────
def bot_loop():
    if not VK_TOKEN or not VK_GROUP_ID:
        log.error("Бот не запущен: нет VK_TOKEN или VK_GROUP_ID в окружении.")
        return

    init_db()

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


def start_bot_in_background():
    """Стартует бот в демоническом потоке. Вызывается из main.py."""
    t = threading.Thread(target=bot_loop, daemon=True, name="vk-bot")
    t.start()
    return t
