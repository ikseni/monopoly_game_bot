import random
import io
import vk_api
import os
import time
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api import upload
from config import token_name, group_id
from game_logic import Game
from keyboards import (
    create_main_keyboard, create_lobby_keyboard, create_lobby_player_keyboard,
    create_game_keyboard, create_purchase_keyboard, create_house_keyboard,
    create_hotel_keyboard, create_auction_keyboard, create_mortgage_keyboard,
    create_build_choice_keyboard
)
from utils import send_msg
from board_converter import MonopolyConverter
from PIL import Image, ImageDraw, ImageFont

vk_session = vk_api.VkApi(token=token_name)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, group_id)

games = {}
vk_user_data = {}

converter = MonopolyConverter()

"""цвета для фишек"""

player_colors = [
    '#801AC9',
    '#00DA22',
    '#C49227',
    '#000000',
    '#269193',
    '#68365A',
]

color_names = {
    '#801AC9': 'фиолетовый',
    '#00DA22': 'зелёный',
    '#C49227': 'жёлтый',
    '#000000': 'чёрный',
    '#269193': 'голубой',
    '#68365A': 'розовый',
}

_board_cache: Image.Image | None = None


def _get_board_original() -> Image.Image | None:
    global _board_cache
    if _board_cache is None:
        try:
            _board_cache = Image.open("board.png").convert("RGB")
        except FileNotFoundError:
            print("board.png не найден!")
    return _board_cache

try:
    _FONT_TOKEN = ImageFont.truetype("arial.ttf", 20)
    _FONT_SMALL = ImageFont.truetype("arial.ttf", 13)
    _FONT_LEGEND = ImageFont.truetype("arial.ttf", 14)
except Exception:
    _FONT_TOKEN = ImageFont.load_default()
    _FONT_SMALL = ImageFont.load_default()
    _FONT_LEGEND = ImageFont.load_default()


def hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


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


def get_player_color(player_index: int) -> str:
    return player_colors[player_index % len(player_colors)]


def _get_owner_color_map(game) -> dict:
    player_list = list(game.players.keys())
    return {uid: hex_to_rgb(get_player_color(i)) for i, uid in enumerate(player_list)}


"""отрисовка элементов на карте"""

def generate_board_image(game) -> bytes | None:
    print("debug: функция отрисовки карты вызвана")
    original = _get_board_original()
    if original is None:
        print("debug: нет оригинальной .png картинки")
        return None

    board = original.copy()
    draw = ImageDraw.Draw(board)

    owner_colors = _get_owner_color_map(game)
    player_list = list(game.players.items())

    print(f"debug: player_list = {player_list}")

    for cell in game.CELLS:
        cid = cell['id']
        owner = cell.get('owner')
        if owner is None or owner not in owner_colors:
            continue

        color = owner_colors[owner]
        try:
            x1, y1 = converter.get_physical_coords(cid, 'property_strip')
            _, _, x2, y2, side = converter.get_cell_bounds(cid)
        except Exception as e:
            print(f"debug: ошибка координат для клетки {cid}: {e}")
            continue

        if side in (0, 2):
            w = x2 - x1
            h = converter.PROPERTY_LINE_THICKNESS
        else:
            w = converter.PROPERTY_LINE_THICKNESS
            h = y2 - y1

        draw.rectangle([x1, y1, x1 + w, y1 + h], fill=color)

    for cell in game.CELLS:
        cid = cell['id']
        houses = cell.get('houses', 0)
        hotel = cell.get('hotel', False)
        if (not houses and not hotel) or cid % 10 == 0:
            continue

        try:
            x, y = converter.get_physical_coords(cid, 'building')
            _, _, _, _, side = converter.get_cell_bounds(cid)  # <-- Получаем сторону клетки
        except Exception as e:
            print(f"debug: ошибка координат домов для клетки {cid}: {e}")
            continue

        size = converter.BUILDING_SIZE

        if hotel:
            draw.rectangle([x, y, x + size, y + size], fill=(180, 0, 0), outline='white', width=1)
            draw.text((x + 2, y + 2), "H", fill='white')
        elif houses > 0:
            for h in range(min(houses, 4)):
                if side in (0, 2):  # Горизонтальные клетки (низ, верх) -> рисуем в ряд по X
                    draw.rectangle([x + h * (size + 2), y, x + size + h * (size + 2), y + size],
                                   fill=(34, 139, 34), outline='white', width=1)
                    draw.text((x + 2 + h * (size + 2), y + 2), str(h + 1), fill='white')
                else:  # Вертикальные клетки (лево, право) -> рисуем в столбик по Y
                    draw.rectangle([x, y + h * (size + 2), x + size, y + size + h * (size + 2)],
                                   fill=(34, 139, 34), outline='white', width=1)
                    draw.text((x + 2, y + 2 + h * (size + 2)), str(h + 1), fill='white')

    position_counts = {}
    for _, player in player_list:
        pos = player['position']
        position_counts[pos] = position_counts.get(pos, 0) + 1

    position_offsets = {}

    for idx, (user_id, player) in enumerate(player_list):
        pos = player['position']
        offset_idx = position_offsets.get(pos, 0)
        position_offsets[pos] = offset_idx + 1

        try:
            x, y = converter.get_physical_coords(pos, 'player', player_id=offset_idx + 1)
        except Exception as e:
            print(f"debug: ошибка координат игрока для позиции {pos}: {e}")
            continue

        size = converter.PLAYER_SIZE
        color = hex_to_rgb(get_player_color(idx))

        draw.ellipse([x, y, x + size, y + size], fill=color, outline='white', width=3)

        letter = player['name'][0].upper()
        draw.text((x + size // 2 - 10, y + size // 2 - 10), letter, fill='white', font=_FONT_TOKEN)

    leg_x = 600
    leg_y = 600
    draw.rectangle([leg_x - 5, leg_y - 20, leg_x + 175, leg_y + len(player_list) * 22 + 5], fill=(30, 30, 30))
    draw.text((leg_x, leg_y - 18), "игроки:", fill='white', font=_FONT_LEGEND)
    for idx, (uid, player) in enumerate(player_list):
        color = hex_to_rgb(get_player_color(idx))
        ey = leg_y + idx * 22
        draw.ellipse([leg_x, ey, leg_x + 14, ey + 14], fill=color, outline='white', width=1)
        draw.text((leg_x + 20, ey + 1), player['name'], fill='white', font=_FONT_LEGEND)

    buf = io.BytesIO()
    board.save(buf, format='JPEG', quality=85, optimize=True)
    buf.seek(0)
    print("debug: карта успешно сохранена в буфер")
    return buf.read()


def send_board_to_all(game):
    try:
        jpeg_bytes = generate_board_image(game)
    except Exception as e:
        broadcast(game, "Карта временно недоступна (ошибка генерации)")
        return

    if jpeg_bytes is None or len(jpeg_bytes) < 100:
        print("Ошибка: картинка не сгенерирована или слишком маленькая")
        broadcast(game, "Карта временно недоступна")
        return

    temp_filename = "temp_board.jpg"
    max_retries = 2
    attachment = None

    for attempt in range(max_retries):
        try:
            with open(temp_filename, "wb") as f:
                f.write(jpeg_bytes)

            uploader = upload.VkUpload(vk)
            photos = uploader.photo_messages(temp_filename)

            if not photos:
                print("Ошибка: photo_messages вернул пустой результат")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                broadcast(game, "Карта временно недоступна (ошибка загрузки vk)")
                return

            attachment = f"photo{photos[0]['owner_id']}_{photos[0]['id']}"
            break

        except Exception as e:
            print(f"Ошибка загрузки фото в vk (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1.5)
                continue
            print("Не удалось загрузить фото после повторных попыток.")
            broadcast(game, "Карта временно недоступна")
            return
        finally:
            if os.path.exists(temp_filename):
                try:
                    os.remove(temp_filename)
                except Exception as e:
                    print(f"Не удалось удалить временный файл: {e}")

    if not attachment:
        broadcast(game, "Карта временно недоступна")
        return

    player_list = list(game.players.items())
    legend = "Цвета игроков:\n"
    for idx, (uid, player) in enumerate(player_list):
        color_hex = get_player_color(idx)
        color_name = color_names.get(color_hex, 'неизвестный')
        legend += f"{color_name}: {player['name']}\n"

    current_name = game.players[game.current_turn]['name']
    text = f"\U0001F5FA Карта Монополии\n\nХод: {current_name}\n\n{legend}"

    print(f"debug: Начинаем рассылку карты {len(game.players)} игрокам")
    for pid in game.players:
        try:
            send_msg(vk, pid, text, attachment=attachment, keyboard=create_game_keyboard())
        except Exception as e:
            print(f"ошибка отправки карты игроку {pid}: {e}")

"""для аукциона"""

def start_auction_for_game(game, cell_id, cell_name):
    auction_msg = game.start_auction(cell_id)
    for pid in game.players:
        is_owner = (pid == game.owner_id)
        send_msg(vk, pid, f"Аукцион на {cell_name}!\n{auction_msg}", keyboard=create_auction_keyboard(is_owner))


def handle_purchase_pass(game, user_id, user_name):
    if game.waiting_for_purchase and game.pending_purchase:
        if game.pending_purchase['user_id'] != user_id:
            send_msg(vk, user_id, "Это не твоё предложение")
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
        handle_auction_end(game, end_result)


def handle_auction_bid(game, user_id, bid_amount):
    if not game.auction or not game.auction['active']:
        send_msg(vk, user_id, "Нет активного аукциона")
        return

    success, result = game.make_bid(user_id, bid_amount)

    if success:
        if game.auction is None:
            handle_auction_end(game, result)
        else:
            for pid in game.players:
                is_owner = (pid == game.owner_id)
                send_msg(vk, pid, result, keyboard=create_auction_keyboard(is_owner))
    else:
        send_msg(vk, user_id, result, keyboard=create_auction_keyboard(user_id == game.owner_id))


def handle_auction_end(game, result):
    if game.last_roll_was_double and game.double_roller_id == game.current_turn:
        if game.double_count >= 3:
            jail_msg = game.move_to_jail(game.current_turn)
            full_msg = f"{result}\n\n{jail_msg}\n3 дубля подряд - отправляетесь в тюрьму!"
            game.double_count = 0
            game.last_roll_was_double = False
            game.double_roller_id = None
            game.next_turn()
            broadcast(game, full_msg, keyboard=create_game_keyboard())
            announce_next_turn(game)
        else:
            msg_extra = f"\n\nДубль #{game.double_count}! {game.players[game.current_turn]['name']} получает дополнительный ход"
            broadcast(game, result + msg_extra, keyboard=create_game_keyboard())
            game.double_roller_id = None
    else:
        game.double_count = 0
        game.last_roll_was_double = False
        game.double_roller_id = None
        game.next_turn()
        broadcast(game, result, keyboard=create_game_keyboard())
        announce_next_turn(game)


def handle_force_end_auction(game, user_id):
    if game.owner_id != user_id:
        send_msg(vk, user_id, "Только создатель игры может завершить аукцион")
        return

    if not game.auction or not game.auction['active']:
        send_msg(vk, user_id, "Нет активного аукциона")
        return

    result = game.force_end_auction()
    handle_auction_end(game, result)


"""Обработка хода после броска"""

def finish_roll(game, user_id, user_name, dice1, dice2, is_double):
    dice_sum = dice1 + dice2
    game.last_dice_sum = dice_sum
    game.last_roll_was_double = is_double

    header = f"{user_name}: {dice1} + {dice2} = {dice_sum}"
    if is_double:
        header += " !!дубль!!"
        game.double_count += 1

    move_msg, need_purchase, bankrupt = game.move_player(user_id, dice_sum)
    full_msg = f"{header}\n{move_msg}"

    send_board_to_all(game)

    if need_purchase:
        if is_double:
            game.double_roller_id = user_id
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
        if game.double_count >= 3:
            jail_msg = game.move_to_jail(user_id)
            full_msg += f"\n\n{jail_msg}\n3 дубля подряд - отправляетесь в тюрьму!"
            game.double_count = 0
            game.last_roll_was_double = False
            game.next_turn()
            broadcast(game, full_msg, keyboard=create_game_keyboard())
            announce_next_turn(game)
        else:
            full_msg += f"\n\nДубль #{game.double_count}! {user_name} получает дополнительный ход"
            broadcast(game, full_msg, keyboard=create_game_keyboard())
        return

    game.double_count = 0
    game.last_roll_was_double = False
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
                     f"{winner_name} победил!\n{name} обанкротился",
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
                     "Вы уже в игре или уже создали комнату\n"
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

        if len(game.players) >= 6:
            send_msg(vk, peer_id, "В комнате уже 6 игроков!")
            continue

        success, result = game.add_player(user_id, user_name)

        keyboard = create_lobby_keyboard() if user_id == game.owner_id else create_lobby_player_keyboard()
        send_msg(vk, peer_id, result, keyboard=keyboard)

        if success:
            for pid in game.players:
                if pid != user_id:
                    send_msg(vk, pid, f"{user_name} присоединился!\nИгроков в лобби: {len(game.players)}")
                    if pid == game.owner_id:
                        send_msg(vk, pid, f"Теперь игроков: {len(game.players)}",
                                 keyboard=create_lobby_keyboard())

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

    elif text_lower == '/board':
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре! Сначала создай или присоединись.",
                     keyboard=keyboard_for(user_id))
            continue
        send_board_to_all(active_game)

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
                send_board_to_all(game)
                broadcast(game, full_msg, keyboard=create_game_keyboard())
            else:
                move_msg, need_purchase, bankrupt = game.move_player(user_id, dice_sum)
                full_msg = f"{jail_msg}\n{move_msg}"
                send_board_to_all(game)

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
            if game.last_roll_was_double:
                if game.double_count >= 3:
                    jail_msg = game.move_to_jail(user_id)
                    full_msg = f"{result}\n\n{jail_msg}\n3 дубля подряд - отправляетесь в тюрьму!"
                    game.double_count = 0
                    game.last_roll_was_double = False
                    game.next_turn()
                    broadcast(game, full_msg, keyboard=create_game_keyboard())
                    announce_next_turn(game)
                else:
                    msg_extra = f"\n\nДубль #{game.double_count}! {user_name} получает дополнительный ход"
                    broadcast(game, result + msg_extra, keyboard=create_game_keyboard())
            else:
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

    elif text_lower in ('пас аукцион', '/pass_auction'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        handle_auction_pass(active_game, user_id, user_name)

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
        handle_force_end_auction(active_game, user_id)

    elif text_lower in ('построить', '/build'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        color_groups = game.get_color_groups(user_id)
        if not color_groups:
            send_msg(vk, peer_id,
                     "У Вас нет полных цветовых групп.\nНужно владеть !всеми! улицами одного цвета",
                     keyboard=create_game_keyboard())
            continue

        send_msg(vk, peer_id, "Выберите где строить:", keyboard=create_build_choice_keyboard())

    elif text_lower == 'построить дом':
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        color_groups = game.get_color_groups(user_id)
        if not color_groups:
            send_msg(vk, peer_id, "У Вас нет полных цветовых групп.\nНужно владеть !всеми! улицами одного цвета",
                     keyboard=create_game_keyboard())
            continue

        vk_user_data[f"build_action_{user_id}"] = "house"
        send_msg(vk, peer_id, "Выберите цвет улицы для постройки дома:", keyboard=create_house_keyboard())

    elif text_lower == 'построить отель':
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        color_groups = game.get_color_groups(user_id)
        if not color_groups:
            send_msg(vk, peer_id, "У Вас нет полных цветовых групп для постройки отеля",
                     keyboard=create_game_keyboard())
            continue

        vk_user_data[f"build_action_{user_id}"] = "hotel"
        send_msg(vk, peer_id, "Выберите цвет улицы для постройки отеля (при наличии 4 домов на улице):",
                 keyboard=create_hotel_keyboard())

    elif text_lower.startswith('/build '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        color = text.split()[1].lower()

        if not game.owns_full_color(user_id, color):
            send_msg(vk, peer_id, f"Нужно владеть !всеми! улицами цвета {color}", keyboard=create_game_keyboard())
            continue

        cells = game.get_cells_by_color(user_id, color)
        if not cells:
            send_msg(vk, peer_id, f"У Вас нет улиц цвета {color}!", keyboard=create_game_keyboard())
            continue

        action_type = vk_user_data.get(f"build_action_{user_id}", "house")
        house_price = game.get_house_price(color)

        if action_type == "house":
            msg = f"Выберите улицу для постройки дома (цвет {color}):\n"
            msg += f"Цена одного дома: {house_price}$\n\n"
            for cid, name, houses, hotel in cells:
                if hotel:
                    status = "\U0001F3E8 (отель уже есть)"
                else:
                    status = f"\U0001F3E1 {houses}/4 домов"
                msg += f"  [{cid}] {name} - {status}\n"
            msg += "\nНапишите /build_id id - построить дом\nПример: /build_id 1"
            send_msg(vk, peer_id, msg, keyboard=create_game_keyboard())
        else:
            hotelable = [c for c in cells if c[2] == 4 and not c[3]]
            hotel_price = house_price * 4
            if not hotelable:
                send_msg(vk, peer_id, f"На улицах цвета {color} нет 4 домов для постройки отеля!",
                         keyboard=create_game_keyboard())
            else:
                msg = f"Выберите улицу для постройки отеля (цвет {color}):\n"
                msg += f"Цена отеля: {hotel_price}$\n\n"
                for cid, name, houses, hotel in hotelable:
                    msg += f"  [{cid}] {name} - 4 дома\n"
                msg += "\nНапишите /hotel_id id - построить отель\nПример: /hotel_id 1"
                send_msg(vk, peer_id, msg, keyboard=create_game_keyboard())


    elif text_lower.startswith('/hotel '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        color = text.split()[1].lower()

        if not game.owns_full_color(user_id, color):
            send_msg(vk, peer_id, f"Нужно владеть !всеми! улицами цвета {color}", keyboard=create_game_keyboard())
            continue

        cells = game.get_cells_by_color(user_id, color)
        if not cells:
            send_msg(vk, peer_id, f"У Вас нет улиц цвета {color}!", keyboard=create_game_keyboard())
            continue

        hotelable = [c for c in cells if c[2] == 4 and not c[3]]
        house_price = game.get_house_price(color)
        hotel_price = house_price * 4

        if not hotelable:
            send_msg(vk, peer_id,
                     f"На улицах цвета {color} нет 4 домов для постройки отеля! Сначала постройте 4 дома на каждой улице этого цвета",
                     keyboard=create_game_keyboard())
        else:
            msg = f"Выберите улицу для постройки отеля (цвет {color}):\n"
            msg += f"Цена отеля: {hotel_price}$\n\n"
            for cid, name, houses, hotel in hotelable:
                msg += f"  [{cid}] {name} - 4 дома\n"
            msg += "\nНапишите /hotel_id id - построить отель\nПример: /hotel_id 1"
            send_msg(vk, peer_id, msg, keyboard=create_game_keyboard())

    elif text_lower.startswith('/build_id '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        try:
            cell_id = int(text.split()[1])
        except (IndexError, ValueError):
            send_msg(vk, peer_id, "Формат: /build_id id\nПример: /build_id 1")
            continue

        success, result = game.build_house(user_id, cell_id)
        if success:
            broadcast(game, result)
            send_board_to_all(game)
            if f"build_action_{user_id}" in vk_user_data:
                del vk_user_data[f"build_action_{user_id}"]
        else:
            send_msg(vk, peer_id, result, keyboard=create_game_keyboard())

    elif text_lower.startswith('/hotel_id '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        try:
            cell_id = int(text.split()[1])
        except (IndexError, ValueError):
            send_msg(vk, peer_id, "Формат: /hotel_id id\nПример: /hotel_id 1")
            continue

        success, result = game.build_hotel(user_id, cell_id)
        if success:
            broadcast(game, result)
            send_board_to_all(game)
            if f"build_action_{user_id}" in vk_user_data:
                del vk_user_data[f"build_action_{user_id}"]
        else:
            send_msg(vk, peer_id, result, keyboard=create_game_keyboard())

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
            msg += "Доступно для залога:\n"
            for prop_id, cell in can_mortgage:
                mortgage_value = cell['price'] // 2
                msg += f"  [{prop_id}] {cell['name']} - +{mortgage_value}$\n"
            msg += "\n"

        if mortgaged:
            msg += "Заложены (можно выкупить):\n"
            for prop_id, cell in mortgaged:
                mortgage_value = cell['price'] // 2
                redeem_cost = int(mortgage_value * 1.1)
                msg += f"  [{prop_id}] {cell['name']} - выкуп {redeem_cost}$\n"
            msg += "\n"

        msg += "/mg_yes id - заложить улицу\n"
        msg += "/mg_no id - выкупить улицу\n"
        msg += "пример: /mg_yes 1\n\n"
        msg += "Чтобы заложить улицу с домами или отелем, сначала продай их банку командой /sell"

        send_msg(vk, peer_id, msg, keyboard=create_mortgage_keyboard())

    elif text_lower in ('продать', '/sell'):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        sellable = []
        for prop_id in game.players[user_id]['properties']:
            cell = game.CELLS[prop_id]
            if cell.get('type') == 'property' and (cell.get('houses', 0) > 0 or cell.get('hotel')):
                status = "Отель" if cell.get('hotel') else f"{cell.get('houses', 0)} дом(ов)"
                sellable.append(f"  [{prop_id}] {cell['name']} - {status}")

        if not sellable:
            send_msg(vk, peer_id, "У Вас нет улиц с постройками для продажи", keyboard=create_game_keyboard())
            continue

        msg = "Выберите улицу для продажи постройки банку:\n\n" + "\n".join(sellable)
        msg += "\n\nНапишите /sell_id id - продать одну постройку\nПример: /sell_id 1"
        send_msg(vk, peer_id, msg, keyboard=create_game_keyboard())

    elif text_lower.startswith('/sell_id '):
        if not is_in_game:
            send_msg(vk, peer_id, "Вы не в игре!", keyboard=keyboard_for(user_id))
            continue
        game = active_game

        try:
            cell_id = int(text.split()[1])
        except (IndexError, ValueError):
            send_msg(vk, peer_id, "Формат: /sell_id id\nПример: /sell_id 1")
            continue

        success, result = game.sell_building(user_id, cell_id)
        if success:
            broadcast(game, result)
            send_board_to_all(game)
        else:
            send_msg(vk, peer_id, result, keyboard=create_game_keyboard())

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
                 f"{user_name}\n{jail_status}{turn_marker}"
                 f"Клетка: {cell['name']}\nБаланс: {player['money']}$\n"
                 f"Собственностей: {len(player['properties'])}",
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
                         f"{name} вышел - Вы остались один. Игра завершена, поздравляю с победой!",
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
                 "Список команд для игры в монополию:\n\n"
                 "/create - создать игру\n"
                 "/join код - присоединиться\n"
                 "/start_game - начать (только создатель)\n"
                 "/roll - бросить кубики\n"
                 "/board - показать карту\n"
                 "/buy - купить клетку\n"
                 "/pass - отказаться от покупки --> аукцион\n"
                 "/bid сумма - ставка на аукционе\n"
                 "/pass_auction - пас на аукционе\n"
                 "/next - завершить аукцион (создатель)\n"
                 "/build - показать доступные для строительства улицы\n"
                 "/build_id ID - построить дом\n"
                 "/hotel_id ID - построить отель\n"
                 "/build цвет - выбрать цвет для дома\n"
                 "/hotel цвет - выбрать цвет для отеля\n" 
                 "/pos - моя позиция\n"
                 "/props - моя собственность\n"
                 "/mortgage - залог меню\n"
                 "/mg_yes id - заложить\n"
                 "/mg_no id - выкупить\n"
                 "/sell_id id - продать одну постройку на улице"
                 "/leave - выйти из игры\n\n"
                 "Цвета: brown, lightblue, pink, orange, red, yellow, green, darkblue\n\n"
                 "Или используйте кнопки внизу",
                 keyboard=keyboard_for(user_id))
    else:
        send_msg(vk, peer_id,
                 "Неизвестная команда. Напиши /help",
                 keyboard=keyboard_for(user_id))