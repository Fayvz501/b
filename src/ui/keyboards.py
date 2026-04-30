from vk_api.keyboard import VkKeyboard, VkKeyboardColor

def main_menu():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('📈 Рассчитать кредит', color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button('💰 Сложный процент', color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('📜 Моя история', color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def back_menu():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('⬅️ В меню', color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()