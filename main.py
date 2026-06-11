import random
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from config import token_name, group_id
from game_logic import Game
from keyboards import (
    create_main_keyboard, create_lobby_keyboard, create_lobby_player_keyboard,
    create_game_keyboard, create_purchase_keyboard, create_house_keyboard,
    create_hotel_keyboard, create_auction_keyboard, create_mortgage_keyboard,
    create_build_choice_keyboard
)
from utils import send_msg

vk_session = vk_api.VkApi(token=token_name)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, group_id)

games = {}



def get_user_name(user_id):
    info = vk.users.get(user_ids=user_id)[0]
    return f"{info['first_name']} {info['last_name']}"


def find_game_of_user(user_id):
    for game in games.values():
        if user_id in game.players:
            return game
    return None


def find_active_game_of_user(user_id):
    for game in games.values():
        if game.game_started and user_id in game.players:
            return game
    return None


def keyboard_for(user_id):
    active_game = find_active_game_of_user(user_id)
    if active_game:
        return create_game_keyboard()

    for game in games.values():
        if not game.game_started and game.owner_id == user_id:
            return create_lobby_keyboard()

    for game in games.values():
        if not game.game_started and user_id in game.players:
            return create_lobby_player_keyboard()

    return create_main_keyboard()


def broadcast(game, text, keyboard=None):
    for pid in list(game.players.keys()):
        send_msg(vk, pid, text, keyboard=keyboard)


def announce_next_turn(game):
    name = game.players[game.current_turn]['name']
    broadcast(game, f"Ход: {name}", keyboard=create_game_keyboard())



"""функции аукциона"""

def start_auction_for_game(game, cell_id, cell_name):
    auction_msg = game.start_auction(cell_id)
    for pid in game.players:
        is_owner = (pid == game.owner_id)
        send_msg(vk, pid, f"Аукцион на {cell_name}!\n{auction_msg}", keyboard=create_auction_keyboard(is_owner))


def handle_purchase_pass(game, user_id, user_name):
    if game.waiting_for_purchase and game.pending_purchase:
        if game.pending_purchase['user_id'] != user_id:
            send_msg(vk, user_id, "Это не твоё предложение!")
            return True
        cell_id = game.pending_purchase['cell_id']
        cell_name = game.CELLS[cell_id]['name']
        start_auction_for_game(game, cell_id, cell_name)
        return True
    return False


def handle_auction_pass(game, user_id, user_name):
    if not game.auction or not game.auction['active']:
        send_msg(vk, user_id, "Нет активного аукциона")
        return

    ok, pass_msg, end_result = game.pass_auction(user_id)

    for pid in game.players:
        is_owner = (pid == game.owner_id)
        send_msg(vk, pid, pass_msg, keyboard=create_auction_keyboard(is_owner))

    if end_result:
        for pid in game.players:
            send_msg(vk, pid, end_result, keyboard=create_game_keyboard())
        game.next_turn()
        announce_next_turn(game)


def handle_auction_bid(game, user_id, bid_amount):
    if not game.auction or not game.auction['active']:
        send_msg(vk, user_id, "Нет активного аукциона")
        return

    success, result = game.make_bid(user_id, bid_amount)

    if success:
        if game.auction is None:
            for pid in game.players:
                send_msg(vk, pid, result, keyboard=create_game_keyboard())
            game.next_turn()
            announce_next_turn(game)
        else:
            for pid in game.players:
                is_owner = (pid == game.owner_id)
                send_msg(vk, pid, result, keyboard=create_auction_keyboard(is_owner))
    else:
        send_msg(vk, user_id, result, keyboard=create_auction_keyboard(user_id == game.owner_id))


def handle_force_end_auction(game, user_id):
    if game.owner_id != user_id:
        send_msg(vk, user_id, "Только создатель игры может завершить аукцион")
        return

    if not game.auction or not game.auction['active']:
        send_msg(vk, user_id, "Нет активного аукциона")
        return

    result = game.force_end_auction()
    for pid in game.players:
        send_msg(vk, pid, result, keyboard=create_game_keyboard())

    game.next_turn()
    announce_next_turn(game)


"""Обработка хода после броска"""

def finish_roll(game, user_id, user_name, dice1, dice2, is_double):
    dice_sum = dice1 + dice2
    game.last_dice_sum = dice_sum

    header = f"{user_name}: {dice1} + {dice2} = {dice_sum}"
    if is_double:
        header += " Дубль!"

    move_msg, need_purchase, bankrupt = game.move_player(user_id, dice_sum)
    full_msg = f"{header}\n{move_msg}"

    if need_purchase:
        for pid in game.players:
            if pid == user_id:
                send_msg(vk, pid, full_msg, keyboard=create_purchase_keyboard())
            else:
                send_msg(vk, pid, full_msg, keyboard=create_game_keyboard())
        return

    if bankrupt:
        broadcast(game, full_msg)
        _remove_bankrupt(game, user_id)
        return

    if is_double:
        game.double_count += 1
        if game.double_count >= 3:
            jail_msg = game.move_to_jail(user_id)
            full_msg += f"\n\n{jail_msg}\n3 дубля подряд - отправляетесь тюрьму!"
            game.double_count = 0
            game.next_turn()
            broadcast(game, full_msg, keyboard=create_game_keyboard())
            announce_next_turn(game)
        else:
            full_msg += f"\n\nДубль #{game.double_count}! {user_name} получает дополнительный ход"
            broadcast(game, full_msg, keyboard=create_game_keyboard())
        return

    game.double_count = 0
    game.next_turn()
    broadcast(game, full_msg, keyboard=create_game_keyboard())
    announce_next_turn(game)


def _remove_bankrupt(game, user_id):
    name = game.players[user_id]['name']
    for prop_id in game.players[user_id]['properties']:
        cell = game.CELLS[prop_id]
        cell['owner'] = None
        cell['mortgaged'] = False
        cell['houses'] = 0
        cell['hotel'] = False
    del game.players[user_id]
    if user_id in game.turn_order:
        game.turn_order.remove(user_id)

    if len(game.players) < 2:
        if game.players:
            winner_id = list(game.players.keys())[0]
            winner_name = game.players[winner_id]['name']
            send_msg(vk, winner_id,
                     f"{winner_name} ПОБЕДИЛ!\n{name} обанкротился((",
                     keyboard=create_main_keyboard())
        game.game_started = False
        for code, g in list(games.items()):
            if g is game:
                del games[code]
                break
    else:
        if game.current_turn == user_id:
            game.current_turn = game.turn_order[0]
        broadcast(game, f"{name} обанкротился и выбыл из игры")
        announce_next_turn(game)


"главный цикл"

print("бот запущен")

for event in longpoll.listen():
    if event.type != VkBotEventType.MESSAGE_NEW:
        continue

    msg_obj = event.obj.message
    user_id = msg_obj['from_id']
    text = msg_obj['text'].strip()
    text_lower = text.lower()
    peer_id = msg_obj['peer_id']

    try:
        user_name = get_user_name(user_id)
    except Exception:
        user_name = f"Игрок{user_id}"

    active_game = find_active_game_of_user(user_id)
    is_in_game = active_game is not None


    if text_lower in ('создать игру', '/create'):
        existing = find_game_of_user(user_id)
        if existing:
            send_msg(vk, peer_id,
                     "Вы уже в игре или уже создал комнату\n"
                     "напиши команду /leave чтобы выйти",
                     keyboard=keyboard_for(user_id))
            continue

        room_code = Game.generate_room_code()
        new_game = Game(room_code, user_id)
        new_game.add_player(user_id, user_name)
        games[room_code] = new_game

        send_msg(vk, peer_id,
                 f"Игра создана. Вы уже в лобби!\n"
                 f"Код комнаты: {room_code}\n\n"
                 f"Чтобы играть вместе попроси друзей написать: /join {room_code}\n"
                 f"Когда все готовы - нажми кнопку «начать игру»",
                 keyboard=create_lobby_keyboard())

    elif text_lower.startswith('/join '):
        parts = text.split()
        if len(parts) < 2:
            send_msg(vk, peer_id, "Используй: /join код_комнаты")
            continue

        room_code = parts[1].upper()
        game = games.get(room_code)

        if not game:
            send_msg(vk, peer_id, f"Комната «{room_code}» не найдена!")
            continue
        if game.game_started:
            send_msg(vk, peer_id, "Игра уже началась")
            continue
        if user_id in game.players:
            send_msg(vk, peer_id, "Вы уже в этой комнате!")
            continue

        success, result = game.add_player(user_id, user_name)

        if user_id == game.owner_id:
            keyboard = create_lobby_keyboard()
        else:
            keyboard = create_lobby_player_keyboard()

        send_msg(vk, peer_id, result, keyboard=keyboard)

        if success:
            for pid in game.players:
                if pid != user_id:
                    send_msg(vk, pid, f"{user_name} присоединился!\nИгроков в лобби: {len(game.players)}")
                    if pid == game.owner_id:
                        send_msg(vk, pid, f"Теперь игроков: {len(game.players)}", keyboard=create_lobby_keyboard())

    elif text_lower in ('начать игру', '/start_game'):
        owner_game = None
        for g in games.values():
            if g.owner_id == user_id and not g.game_started:
                owner_game = g
                break

        if not owner_game:
            send_msg(vk, peer_id,
                     "У Вас нет незапущенной комнаты\n"
                     "Только создатель может начать игру")
            continue

        success, result = owner_game.start_game()
        if success:
            for pid in owner_game.players:
                send_msg(vk, pid, result + "\n\nНажми «бросить кубики» чтобы ходить", keyboard=create_game_keyboard())
        else:
            send_msg(vk, peer_id, result)

    elif text_lower in ('бросить кубики', '/roll'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в активной игре", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if game.waiting_for_purchase:
            send_msg(vk, peer_id, "попробуй позже", keyboard=create_purchase_keyboard())
            continue
        if game.auction and game.auction['active']:
            send_msg(vk, peer_id, "Сначала завершите аукцион",
                     keyboard=create_auction_keyboard(user_id == game.owner_id))
            continue
        if not game.is_my_turn(user_id):
            send_msg(vk, peer_id, f"Сейчас ходит {game.get_current_player_name()}. Дождитесь своей очереди")
            continue

        player = game.get_player(user_id)

        if player.get('in_jail'):
            can_move, jail_msg, dice_sum, is_double = game.process_jail_turn(user_id)

            if not can_move:
                game.next_turn()
                next_name = game.players[game.current_turn]['name']
                full_msg = f"{jail_msg}\n\nХод: {next_name}"
                broadcast(game, full_msg, keyboard=create_game_keyboard())
            else:
                move_msg, need_purchase, bankrupt = game.move_player(user_id, dice_sum)
                full_msg = f"{jail_msg}\n{move_msg}"

                if need_purchase:
                    for pid in game.players:
                        if pid == user_id:
                            send_msg(vk, pid, full_msg, keyboard=create_purchase_keyboard())
                        else:
                            send_msg(vk, pid, full_msg, keyboard=create_game_keyboard())
                elif bankrupt:
                    broadcast(game, full_msg)
                    _remove_bankrupt(game, user_id)
                else:
                    game.double_count = 0
                    game.next_turn()
                    next_name = game.players[game.current_turn]['name']
                    full_msg += f"\n\nХод: {next_name}"
                    broadcast(game, full_msg, keyboard=create_game_keyboard())
            continue

        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        finish_roll(game, user_id, user_name, dice1, dice2, dice1 == dice2)

    elif text_lower in ('купить', '/buy'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if not game.waiting_for_purchase:
            send_msg(vk, peer_id, "Нет активного предложения о покупке")
            continue
        if game.pending_purchase['user_id'] != user_id:
            send_msg(vk, peer_id, "Не Ваша очередь покупать")
            continue

        success, result = game.buy_property(user_id)
        if success:
            broadcast(game, result)
            game.next_turn()
            announce_next_turn(game)
        else:
            send_msg(vk, peer_id, result)
            if game.pending_purchase:
                cell_id = game.pending_purchase['cell_id']
                cell_name = game.CELLS[cell_id]['name']
                start_auction_for_game(game, cell_id, cell_name)

    elif text_lower in ('отказаться', '/pass'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if not handle_purchase_pass(game, user_id, user_name):
            send_msg(vk, peer_id, "Нет активного предложения о покупке")

    elif text_lower in ('отказаться', 'пас аукцион', '/pass_auction'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game
        handle_auction_pass(game, user_id, user_name)

    elif text_lower == 'ставка':
        send_msg(vk, peer_id, "Напиши /bid сумма  (пример: /bid 250)")

    elif text_lower.startswith('/bid '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if not game.auction or not game.auction['active']:
            send_msg(vk, peer_id, "Нет активного аукциона!")
            continue

        try:
            bid_amount = int(text.split()[1])
        except (IndexError, ValueError):
            send_msg(vk, peer_id, "Формат: /bid сумма  (пример: /bid 250)")
            continue

        handle_auction_bid(game, user_id, bid_amount)

    elif text_lower in ('завершить аукцион', '/next'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game
        handle_force_end_auction(game, user_id)

    elif text_lower in ('построить', '/build'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if not game.is_my_turn(user_id):
            send_msg(vk, peer_id, f"Строить можно только в свой ход.\nСейчас ходит {game.get_current_player_name()}")
            continue

        color_groups = game.get_color_groups(user_id)
        if not color_groups:
            send_msg(vk, peer_id, "У Вас нет полных цветовых групп.\nНужно владеть !всеми! улицами одного цвета",
                     keyboard=create_game_keyboard())
            continue

        send_msg(vk, peer_id, "Выбери действие:", keyboard=create_build_choice_keyboard())

    elif text_lower.startswith('/build '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if not game.is_my_turn(user_id):
            send_msg(vk, peer_id, "Строить можно только в свой ход")
            continue

        color = text.split()[1].lower()
        success, result = game.build_house(user_id, color)
        if success:
            broadcast(game, result)
            send_msg(vk, peer_id, "Хочешь построить ещё или продолжаешь ход?", keyboard=create_game_keyboard())
        else:
            send_msg(vk, peer_id, result, keyboard=create_game_keyboard())

    elif text_lower.startswith('/hotel '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if not game.is_my_turn(user_id):
            send_msg(vk, peer_id, "Строить можно только в свой ход")
            continue

        color = text.split()[1].lower()
        success, result = game.build_hotel(user_id, color)
        if success:
            broadcast(game, result)
            send_msg(vk, peer_id, "Хочешь построить ещё или продолжаешь ход?", keyboard=create_game_keyboard())
        else:
            send_msg(vk, peer_id, result, keyboard=create_game_keyboard())

    elif text_lower == 'построить дом':
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if not game.is_my_turn(user_id):
            send_msg(vk, peer_id, "Строить можно только в свой ход")
            continue

        color_groups = game.get_color_groups(user_id)
        if not color_groups:
            send_msg(vk, peer_id, "У Вас нет полных цветовых групп для строительства домов",
                     keyboard=create_game_keyboard())
            continue

        send_msg(vk, peer_id, "Выбери цвет для постройки дома:", keyboard=create_house_keyboard())

    elif text_lower == 'построить отель':
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        if not game.is_my_turn(user_id):
            send_msg(vk, peer_id, "Строить можно только в свой ход")
            continue

        color_groups = game.get_color_groups(user_id)
        if not color_groups:
            send_msg(vk, peer_id, "У Вас нет полных цветовых групп для постройки отеля",
                     keyboard=create_game_keyboard())
            continue

        send_msg(vk, peer_id, "Выбери цвет для постройки отеля (нужно 4 дома на сети улиц одного цвета):",
                 keyboard=create_hotel_keyboard())

    elif text_lower in ('залог', '/mortgage'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game
        player = game.get_player(user_id)

        can_mortgage = game.get_mortgageable_properties(user_id)
        mortgaged = game.get_mortgaged_properties(user_id)

        if not can_mortgage and not mortgaged:
            send_msg(vk, peer_id, "Нет собственностей для залога или выкупа.", keyboard=create_game_keyboard())
            continue

        msg = f"Баланс: {player['money']}$\n\n"

        if can_mortgage:
            msg += "Добступно для залога:\n"
            for prop_id, cell in can_mortgage:
                mortgage_value = cell['price'] // 2
                msg += f"  [{prop_id}] {cell['name']} — +{mortgage_value}$\n"
            msg += "\n"

        if mortgaged:
            msg += "Заложены (можно выкупить):\n"
            for prop_id, cell in mortgaged:
                mortgage_value = cell['price'] // 2
                redeem_cost = int(mortgage_value * 1.1)
                msg += f"  [{prop_id}] {cell['name']} — выкуп {redeem_cost}$\n"
            msg += "\n"

        msg += "/mg_yes id - заложить улицу\n"
        msg += "/mg_no id - выкупить улицу\n"
        msg += "пример: /mg_yes 1"

        send_msg(vk, peer_id, msg, keyboard=create_mortgage_keyboard())

    elif text_lower.startswith('/mg_yes '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game
        try:
            cell_id = int(text.split()[1])
        except (IndexError, ValueError):
            send_msg(vk, peer_id, "Формат: /mg_yes id")
            continue
        success, result = game.mortgage_property(user_id, cell_id)
        send_msg(vk, peer_id, result, keyboard=create_mortgage_keyboard())

    elif text_lower.startswith('/mg_no '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game
        try:
            cell_id = int(text.split()[1])
        except (IndexError, ValueError):
            send_msg(vk, peer_id, "Формат: /mg_no id")
            continue
        success, result = game.unmortgage_property(user_id, cell_id)
        send_msg(vk, peer_id, result, keyboard=create_mortgage_keyboard())

    elif text_lower in ('позиция', '/pos'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game
        player = game.get_player(user_id)
        cell = game.CELLS[player['position']]
        jail_status = "В тюрьме\n" if player.get('in_jail') else ""
        turn_marker = "Ваш ход\n" if game.is_my_turn(user_id) else ""
        send_msg(vk, peer_id,
                 f"{user_name}\n{jail_status}{turn_marker}Клетка: {cell['name']}\nБаланс: {player['money']}$\nСобственностей: {len(player['properties'])}",
                 keyboard=create_game_keyboard())

    elif text_lower in ('собственность', '/props'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game
        player = game.get_player(user_id)

        if not player['properties']:
            send_msg(vk, peer_id, "У Вас пока нет собственности.", keyboard=create_game_keyboard())
            continue

        lines = [f"{user_name} - собственность:"]
        total = 0
        for pos in player['properties']:
            cell = game.CELLS[pos]
            if cell.get('mortgaged'):
                status = " [ЗАЛОГ]"
            elif cell.get('hotel'):
                status = " [ОТЕЛЬ]"
            elif cell.get('houses', 0) > 0:
                status = f" [{cell['houses']} домов]"
            else:
                status = ""
            lines.append(f"  [{pos}] {cell['name']} (${cell['price']}){status}")
            total += cell['price']
        lines.append(f"\nИтого по цене: ${total}")
        send_msg(vk, peer_id, "\n".join(lines), keyboard=create_game_keyboard())

    elif text_lower in ('выйти', '/leave'):
        game_to_leave = find_game_of_user(user_id)
        if not game_to_leave:
            send_msg(vk, peer_id, "Вы не в игре.", keyboard=keyboard_for(user_id))
            continue

        name = game_to_leave.players[user_id]['name']

        for prop_id in game_to_leave.players[user_id]['properties']:
            cell = game_to_leave.CELLS[prop_id]
            cell['owner'] = None
            cell['mortgaged'] = False
            cell['houses'] = 0
            cell['hotel'] = False

        del game_to_leave.players[user_id]
        if user_id in game_to_leave.turn_order:
            game_to_leave.turn_order.remove(user_id)

        send_msg(vk, peer_id, "Вы вышли из игры.", keyboard=keyboard_for(user_id))

        if len(game_to_leave.players) < 2:
            if game_to_leave.players:
                remaining_id = list(game_to_leave.players.keys())[0]
                send_msg(vk, remaining_id,
                         f"{name} вышел - ты остался один. Игра завершена, поздравляю с победой!",
                         keyboard=create_main_keyboard())
            for code, g in list(games.items()):
                if g is game_to_leave:
                    del games[code]
                    break
        else:
            broadcast(game_to_leave, f"{name} вышел из игры.")
            if game_to_leave.game_started and game_to_leave.current_turn == user_id:
                game_to_leave.current_turn = game_to_leave.turn_order[0]
                announce_next_turn(game_to_leave)

    elif text_lower == 'назад':
        if is_in_game:
            send_msg(vk, peer_id, "Главное меню игры", keyboard=create_game_keyboard())
        else:
            send_msg(vk, peer_id, "Главное меню", keyboard=create_main_keyboard())

    elif text_lower in ('/help', 'помощь', '/'):
        send_msg(vk, peer_id,
                 "Спосок команд для игры в монополию:\n\n"
                 "/create - создать игру\n"
                 "/join код - присоединиться\n"
                 "/start_game - начать (только создатель)\n"
                 "/roll - бросить кубики\n"
                 "/buy - купить клетку\n"
                 "/pass - отказаться от покупки --> аукцион\n"
                 "/bid сумма - ставка на аукционе\n"
                 "/pass_auction - пас на аукционе\n"
                 "/next - завершить аукцион (создатель)\n"
                 "/build цвет - построить дом\n"
                 "/hotel цвет - построить отель\n"
                 "/pos - моя позиция\n"
                 "/props - моя собственность\n"
                 "/mortgage - залог меню\n"
                 "/mg_yes id - заложить\n"
                 "/mg_no id - выкупить\n"
                 "/leave - выйти из игры\n\n"
                 "Цвета: brown, lightblue, pink, orange, red, yellow, green, darkblue\n\n"
                 "Или используйте кнопки внузу",
                 keyboard=keyboard_for(user_id))
    else:
        send_msg(vk, peer_id,
                 "Неизвестная команда. Напиши /help",
                 keyboard=keyboard_for(user_id))