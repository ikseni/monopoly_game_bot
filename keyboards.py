"""кнопки"""

from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def create_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("создать игру", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("помощь", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def create_lobby_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("начать игру", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("выйти", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def create_lobby_player_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("помощь", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("выйти", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def create_game_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("бросить кубики", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("позиция", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("собственность", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("построить", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("залог", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("выйти", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()


def create_purchase_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("купить", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("отказаться", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()


def create_house_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("/build brown \U0001F7EB", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("/build lightblue \U00002B1C", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("/build pink \U0001F7EA", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("/build orange \U0001F7E7", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("/build red \U0001F7E5", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("/build yellow \U0001F7E8", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("/build green \U0001F7E9", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("/build darkblue \U0001F7E6", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def create_hotel_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("/hotel brown \U0001F7EB", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("/hotel lightblue \U00002B1C", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("/hotel pink \U0001F7EA", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("/hotel orange \U0001F7E7", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("/hotel red \U0001F7E5", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("/hotel yellow \U0001F7E8", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("/hotel green \U0001F7E9", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("/hotel darkblue \U0001F7E6", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()

def create_auction_keyboard(is_owner=False):
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("ставка", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("пас аукцион", color=VkKeyboardColor.NEGATIVE)
    if is_owner:
        keyboard.add_line()
        keyboard.add_button("завершить аукцион", color=VkKeyboardColor.POSITIVE)
    return keyboard.get_keyboard()


def create_mortgage_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()


def create_build_choice_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("построить дом", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("построить отель", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("назад", color=VkKeyboardColor.SECONDARY)
    return keyboard.get_keyboard()