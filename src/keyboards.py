"""Клавиатуры VK: главное меню + inline callback-кнопки результата."""
from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def main_menu():
    kb = VkKeyboard(one_time=False)
    kb.add_button("📈 Рассчитать кредит", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("💰 Сложный процент", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("📜 Моя история", color=VkKeyboardColor.SECONDARY)
    kb.add_button("ℹ️ О боте", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def back_menu():
    kb = VkKeyboard(one_time=False)
    kb.add_button("⬅️ В меню", color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()


def result_kb():
    """Inline callback-кнопки после расчёта кредита."""
    kb = VkKeyboard(inline=True)
    kb.add_callback_button("📊 Аннуитет: структура",
                           color=VkKeyboardColor.PRIMARY,
                           payload={"cmd": "struct_ann"})
    kb.add_line()
    kb.add_callback_button("📊 Дифф.: структура",
                           color=VkKeyboardColor.PRIMARY,
                           payload={"cmd": "struct_diff"})
    kb.add_line()
    kb.add_callback_button("📈 Остаток долга",
                           color=VkKeyboardColor.SECONDARY,
                           payload={"cmd": "balance"})
    kb.add_callback_button("⚖️ Сравнение",
                           color=VkKeyboardColor.SECONDARY,
                           payload={"cmd": "compare"})
    kb.add_line()
    kb.add_callback_button("📄 PDF-отчёт",
                           color=VkKeyboardColor.POSITIVE,
                           payload={"cmd": "pdf"})
    return kb.get_keyboard()
