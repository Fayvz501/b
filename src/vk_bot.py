import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.upload import VkUpload
from src.config import VK_TOKEN
from src.database.db_manager import save_calc, get_history, init_db
from src.ui.keyboards import main_menu, back_menu
from src.modules.calculator import FinanceCore
from src.modules.pdf_engine import build_report
import os

init_db()
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
upload = VkUpload(vk_session)

user_states = {} # Простейшая машина состояний: {user_id: {'step': 'amount', 'data': {}}}

def send(user_id, text, kbd=None):
    vk.messages.send(user_id=user_id, message=text, keyboard=kbd, random_id=0)

def main():
    print("PRO Система запущена...")
    for event in VkLongPoll(vk_session).listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            uid = event.user_id
            txt = event.text
            
            if txt == '⬅️ В меню' or txt.lower() == 'старт':
                user_states[uid] = None
                send(uid, "Добро пожаловать в Finance Pro! Выберите действие:", main_menu())
                
            elif txt == '📜 Моя история':
                hist = get_history(uid)
                if not hist:
                    send(uid, "История пуста.")
                else:
                    res = "Последние расчеты:\n"
                    for h in hist:
                        res += f"• {h[0]}: {h[1]} руб (Переплата: {h[2]})\n"
                    send(uid, res)
            
            elif txt == '📈 Рассчитать кредит':
                user_states[uid] = {'mode': 'loan', 'step': 1, 'data': []}
                send(uid, "Введите сумму кредита (число):", back_menu())
                
            # Обработка шагов ввода
            elif uid in user_states and user_states[uid]:
                state = user_states[uid]
                try:
                    val = float(txt)
                    state['data'].append(val)
                    
                    if state['mode'] == 'loan':
                        if state['step'] == 1:
                            state['step'] = 2
                            send(uid, "Введите годовую ставку (%):")
                        elif state['step'] == 2:
                            state['step'] = 3
                            send(uid, "Введите срок в месяцах:")
                        elif state['step'] == 3:
                            send(uid, "⌛ Формирую профессиональный отчет...")
                            df, pay, over = FinanceCore.annuity_total(state['data'][0], state['data'][1], int(state['data'][2]))
                            pdf = build_report(df, uid, "Кредитный отчет")
                            
                            doc = upload.document_message(pdf, title="Отчет.pdf", peer_id=uid)['doc']
                            save_calc(uid, "Кредит", state['data'][0], over)
                            
                            msg = f"✅ Расчет окончен!\nЕжемесячный платеж: {pay} руб.\nПереплата: {over} руб."
                            vk.messages.send(user_id=uid, message=msg, attachment=f"doc{doc['owner_id']}_{doc['id']}", random_id=0)
                            os.remove(pdf)
                            user_states[uid] = None
                except:
                    send(uid, "Пожалуйста, введите корректное число.")

if __name__ == "__main__":
    main()