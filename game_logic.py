import random
import string
from game_data import CELLS, HOUSE_PRICES
from utils import get_random_event


class Game:
    def __init__(self, room_code, owner_id):
        self.room_code = room_code
        self.owner_id = owner_id
        self.players = {}
        self.turn_order = []
        self.current_turn = None
        self.game_started = False
        self.waiting_for_purchase = False
        self.pending_purchase = None
        self.auction = None
        self.double_count = 0
        self.CELLS = [dict(c) for c in CELLS]  # копия, чтобы не мутировать глобал
        self.last_dice_sum = 0

    @staticmethod
    def generate_room_code():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    def add_player(self, user_id, user_name):
        if user_id in self.players:
            return False, "Вы уже в игре"
        if self.game_started:
            return False, "Игра уже началась"
        self.players[user_id] = {
            'name': user_name,
            'position': 0,
            'money': 1500,
            'properties': [],
            'in_jail': False,
            'jail_turns': 0,   # сколько ходов уже отсидел (0, 1, 2)
        }
        self.turn_order.append(user_id)
        return True, f"{user_name} присоединился! Игроков: {len(self.players)}"

    def start_game(self):
        if len(self.players) < 2:
            return False, f"Нужно минимум 2 игрока. Сейчас: {len(self.players)}"
        self.game_started = True
        self.current_turn = random.choice(self.turn_order)
        self.waiting_for_purchase = False
        self.double_count = 0
        players_list = ", ".join([p['name'] for p in self.players.values()])
        first_name = self.players[self.current_turn]['name']
        return True, f"Игра началась!\n{players_list}\nПервый ход: {first_name}"

    def get_player(self, user_id):
        return self.players.get(user_id)

    def is_my_turn(self, user_id):
        return self.current_turn == user_id

    def get_current_player_name(self):
        return self.players[self.current_turn]['name']

    def is_player_in_game(self, user_id):
        return self.game_started and user_id in self.players

    def can_act_in_jail(self, user_id):
        player = self.players.get(user_id)
        if player and player.get('in_jail'):
            return False, "Вы в тюрьме. Hельзя покупать, строить или участвовать в аукционе"
        return True, ""

    """Рента"""

    def owns_full_color(self, owner_id, color):
        all_props = [c for c in self.CELLS if c.get('color') == color and c.get('type') == 'property']
        owned = [c for c in all_props if c.get('owner') == owner_id]
        return len(owned) == len(all_props)

    def get_property_rent(self, cell):
        """
        rent[0] - за улицу
        rent[1] - за всю сеть улицы одного цвета
        rent[2...5] - 1...4 дома на сети улиц
        rent[5] - отель
        """
        if cell.get('mortgaged'):
            return 0

        if cell.get('hotel'):
            return cell['rent'][5]
        houses = cell.get('houses', 0)
        if houses > 0:
            return cell['rent'][min(houses + 1, 5)]
        if self.owns_full_color(cell['owner'], cell.get('color')):
            return cell['rent'][1]
        return cell['rent'][0]

    def get_station_count(self, owner_id):
        return sum(1 for c in self.CELLS if c.get('type') == 'station' and c.get('owner') == owner_id)

    def get_station_rent(self, owner_id):
        """
        rent [1 станция, 2 станции, 3 станции, 4 станции] у одного игрока
        """
        count = self.get_station_count(owner_id)
        rents = [0, 25, 50, 100, 200]
        return rents[min(count, 4)]

    def get_utility_count(self, owner_id):
        return sum(1 for c in self.CELLS if c.get('type') == 'utility' and c.get('owner') == owner_id)

    def get_utility_rent(self, owner_id, dice_sum):
        count = self.get_utility_count(owner_id)
        if count == 1:
            return dice_sum * 4
        elif count >= 2:
            return dice_sum * 10
        return 0

    def get_house_price(self, color):
        return HOUSE_PRICES.get(color, 100)

    """Тюрьма"""

    def move_to_jail(self, user_id):
        player = self.players[user_id]
        player['in_jail'] = True
        player['jail_turns'] = 0
        player['position'] = 10
        return f"{player['name']} отправляется в тюрьму и пропустит 2 хода"

    def process_jail_turn(self, user_id):
        """
        вызывается когда in_jail=True и игрок нажимает "бросить кубики"
        jail_turns - сколько раз уже бросал без дубля (0(первая попытка) или 1(Вторая попытка))
        при ==2 - платит деньги и выходит из тюрьмы
        """
        player = self.players[user_id]
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        dice_sum = dice1 + dice2
        is_double = dice1 == dice2

        if is_double:
            player['in_jail'] = False
            player['jail_turns'] = 0
            msg = (f"{player['name']} бросил {dice1} и {dice2} = {dice_sum}\n"
                   f"Дубль! выходит из тюрьмы и ходит")
            return True, msg, dice_sum, True

        if player['jail_turns'] < 2:
            player['jail_turns'] += 1
            attempts_left = 2 - player['jail_turns']
            msg = (f"{player['name']} бросил {dice1} и {dice2} - не дубль\n"
                   f"Остаётся в тюрьме\n"
                   f"{'Ещё 2 попытки' if attempts_left > 0 else 'Осталась 1 попытка - потом штраф 50$'}")
            return False, msg, dice_sum, False
        else:
            player['money'] -= 50
            player['in_jail'] = False
            player['jail_turns'] = 0
            msg = (f"{player['name']} бросил {dice1} и {dice2} = {dice_sum}\n"
                   f"3-я попытка. Заплатил 50$ штрафа и вышел из тюрьмы")
            return True, msg, dice_sum, False

    """Движение"""

    def _handle_cell(self, user_id, cell_index, msg, dice_sum):

        player = self.players[user_id]
        cell = self.CELLS[cell_index]
        cell_type = cell.get('type', 'property')

        if cell_type == 'property':
            if cell['price'] > 0:
                if cell['owner'] is None:
                    msg += f"\n{cell['name']} стоит {cell['price']}$"
                    msg += f"\nУ тебя {player['money']}$"
                    msg += f"\nкупить или отказаться"
                    self.pending_purchase = {'user_id': user_id, 'cell_id': cell_index}
                    self.waiting_for_purchase = True
                    return msg, True, False
                elif cell['owner'] == user_id:
                    msg += f"\nТвоя собственность"
                else:
                    owner = self.players.get(cell['owner'])
                    rent = self.get_property_rent(cell)
                    player['money'] -= rent
                    if owner:
                        owner['money'] += rent
                    houses_info = ""
                    if cell.get('hotel'):
                        houses_info = " (отель)"
                    elif cell.get('houses', 0) > 0:
                        houses_info = f" ({cell['houses']} домов)"
                    owner_name = owner['name'] if owner else '?'
                    msg += f"\nАренда {rent}$ --> {owner_name}{houses_info}"

        elif cell_type == 'station':
            if cell['owner'] is None:
                msg += f"\n{cell['name']} стоит {cell['price']}$"
                msg += f"\nУ тебя {player['money']}$"
                msg += f"\nкупить или отказаться"
                self.pending_purchase = {'user_id': user_id, 'cell_id': cell_index}
                self.waiting_for_purchase = True
                return msg, True, False
            elif cell['owner'] == user_id:
                msg += f"\nТвоя станция"
            else:
                owner = self.players.get(cell['owner'])
                if cell.get('mortgaged'):
                    rent = 0
                    msg += f"\n{cell['name']} заложена, аренда не взымается"
                else:
                    rent = self.get_station_rent(cell['owner'])
                player['money'] -= rent
                if owner:
                    owner['money'] += rent
                msg += f"\nАренда {rent}$ --> {owner['name']}"

        elif cell_type == 'utility':
            if cell['owner'] is None:
                msg += f"\n{cell['name']} стоит {cell['price']}$"
                msg += f"\nУ тебя {player['money']}$"
                msg += f"\nкупить или отказаться"
                self.pending_purchase = {'user_id': user_id, 'cell_id': cell_index}
                self.waiting_for_purchase = True
                return msg, True, False
            elif cell['owner'] == user_id:
                msg += f"\nТвоя коммунальная услуга"
            else:
                owner = self.players.get(cell['owner'])
                if cell.get('mortgaged'):
                    rent = 0
                    msg += f"\n{cell['name']} заложена, аренда не взымается"
                else:
                    rent = self.get_utility_rent(cell['owner'], dice_sum)
                player['money'] -= rent
                if owner:
                    owner['money'] += rent
                msg += f"\n{rent}$ за {cell['name']} --> {owner['name']}"

        elif cell_type in ('chance', 'chest'):
            event_text, value = get_random_event(cell_type)
            msg += f"\n{event_text}"
            if isinstance(value, int):
                player['money'] += value
                sign = "+" if value >= 0 else ""
                msg += f" ({sign}{value}$)"
            elif isinstance(value, str) and value.startswith("move_"):
                parts = value.split("_")
                if parts[1] == 'rel':
                    steps = int(parts[2])
                    old = player['position']
                    new_pos = (old + steps) % 40
                    if new_pos < old:
                        player['money'] += 200
                        msg += "\n!! +200$ за проход старта !!"
                else:
                    new_pos = int(parts[1])
                    if new_pos < player['position']:
                        player['money'] += 200
                        msg += "\n!! +200$ за проход старта !!"
                player['position'] = new_pos
                target_cell = self.CELLS[new_pos]
                msg += f"\nПеремещение на {target_cell['name']}"
                msg, need_purchase, bankrupt = self._handle_cell(user_id, new_pos, msg, dice_sum)
                return msg, need_purchase, bankrupt
            elif value == "jail":
                jail_msg = self.move_to_jail(user_id)
                msg += f"\n{jail_msg}"

        elif cell_type == 'tax':
            player['money'] -= cell['rent']
            msg += f"\nНалог {cell['rent']}$"

        elif cell_type == 'go_to_jail':
            jail_msg = self.move_to_jail(user_id)
            msg += f"\n{jail_msg}"

        elif cell_type == 'parking':
            msg += f"\nБесплатная стоянка. Отдыхайте))"

        elif cell_type in ('start', 'jail'):
            pass

        if player['money'] < 0:
            return msg, False, True

        return msg, False, False

    def move_player(self, user_id, dice_sum):
        player = self.players[user_id]
        old_pos = player['position']
        new_pos = (old_pos + dice_sum) % 40
        player['position'] = new_pos

        msg = f"{self.CELLS[old_pos]['name']} --> {self.CELLS[new_pos]['name']}"

        passed_start = new_pos < old_pos and self.CELLS[new_pos].get('type') != 'go_to_jail'
        if passed_start:
            player['money'] += 200
            msg += "\n!! +200$ за проход cтарта !!"

        msg, need_purchase, bankrupt = self._handle_cell(user_id, new_pos, msg, dice_sum)

        if bankrupt:
            msg += f"\n\n{player['name']} БАНКРОТ!"
        else:
            msg += f"\n\nБаланс: {player['money']}$"

        return msg, need_purchase, bankrupt

    """Ход"""

    def next_turn(self):
        idx = self.turn_order.index(self.current_turn)
        self.current_turn = self.turn_order[(idx + 1) % len(self.turn_order)]
        self.double_count = 0
        return self.players[self.current_turn]['name']

    """Покупка"""

    def buy_property(self, user_id):
        can_act, jail_msg = self.can_act_in_jail(user_id)
        if not can_act:
            return False, jail_msg

        if not self.pending_purchase or self.pending_purchase['user_id'] != user_id:
            return False, "Нет клетки для покупки"

        cell = self.CELLS[self.pending_purchase['cell_id']]
        player = self.players[user_id]

        if cell['owner'] is not None:
            return False, f"{cell['name']} уже куплена!"
        if player['money'] < cell['price']:
            return False, f"Не хватает денег(( Нужно {cell['price']}$, у тебя {player['money']}$"

        player['money'] -= cell['price']
        cell['owner'] = user_id
        player['properties'].append(self.pending_purchase['cell_id'])
        self.pending_purchase = None
        self.waiting_for_purchase = False

        return True, f"{player['name']} купил(a) {cell['name']} за {cell['price']}$\nОсталось: {player['money']}$"

    """Аукцион"""

    def start_auction(self, cell_id):
        cell = self.CELLS[cell_id]
        self.auction = {
            'active': True,
            'cell_id': cell_id,
            'cell_name': cell['name'],
            'cell_price': cell['price'],
            'current_bid': cell['price'] - 1,
            'current_bidder': None,
            'participants': list(self.players.keys()),
            'passed': []
        }
        self.pending_purchase = None
        self.waiting_for_purchase = False
        return (f"Аукцион!\n{cell['name']}\n"
                f"Начальная ставка: {cell['price']}$\n\n"
                f"/bid сумма - сделать ставку\n"
                f"/pass - отказаться от аукциона\n")

    def make_bid(self, user_id, bid_amount):
        can_act, jail_msg = self.can_act_in_jail(user_id)
        if not can_act:
            return False, jail_msg

        if not self.auction or not self.auction['active']:
            return False, "Нет активного аукциона"

        if user_id in self.auction.get('passed', []):
            return False, "Вы уже отказался от этого аукциона"

        player = self.players[user_id]

        if bid_amount <= self.auction['current_bid']:
            return False, f"Ставка должна быть выше текущей ({self.auction['current_bid']}$)"
        if player['money'] < bid_amount:
            return False, f"Не хватает денег. У тебя {player['money']}$"

        self.auction['current_bid'] = bid_amount
        self.auction['current_bidder'] = user_id

        result = self._check_auction_end()
        if result:
            return True, result

        return True, f"{player['name']} ставит {bid_amount}$ за {self.auction['cell_name']}!"

    def pass_auction(self, user_id):

        if not self.auction or not self.auction['active']:
            return False, "Нет активного аукциона", None

        if user_id in self.auction.get('passed', []):
            return True, f"{self.players[user_id]['name']} уже отказался", None

        self.auction['passed'].append(user_id)
        user_name = self.players[user_id]['name']
        msg = f"{user_name} отказался от аукциона"

        end_result = self._check_auction_end()
        return True, msg, end_result

    def _check_auction_end(self):
        if not self.auction or not self.auction['active']:
            return None

        active = [p for p in self.auction['participants'] if p not in self.auction['passed']]

        if len(active) == 0:
            return self._end_auction_without_winner()

        if self.auction['current_bidder'] is not None:
            others_active = [p for p in active if p != self.auction['current_bidder']]
            if len(others_active) == 0:
                return self._end_auction_with_winner()

        return None

    def _end_auction_with_winner(self):
        winner_id = self.auction['current_bidder']
        winner = self.players[winner_id]
        cell = self.CELLS[self.auction['cell_id']]
        winner['money'] -= self.auction['current_bid']
        cell['owner'] = winner_id
        winner['properties'].append(self.auction['cell_id'])
        result = (f"Аукцион завершён!\n"
                  f"{cell['name']} --> {winner['name']}\n"
                  f"Цена: {self.auction['current_bid']}$\n"
                  f"Осталось: {winner['money']}$")
        self.auction = None
        return result

    def _end_auction_without_winner(self):
        result = "Аукцион: никто не купил, клетка остаётся свободной"
        self.auction = None
        return result

    def force_end_auction(self):
        if not self.auction or not self.auction['active']:
            return "Нет активного аукциона"
        if self.auction['current_bidder'] is not None:
            return self._end_auction_with_winner()
        return self._end_auction_without_winner()

    """Строительство"""

    def can_build_on_color(self, user_id, color):
        all_props = [c for c in self.CELLS if c.get('color') == color and c.get('type') == 'property']
        if not all_props:
            return False, f"Цвет «{color}» не существует"
        owned = [c for c in all_props if c.get('owner') == user_id]
        if len(owned) != len(all_props):
            missing = len(all_props) - len(owned)
            return False, f"Нужно владеть !всеми! улицами цвета {color} (не хватает {missing})"
        return True, owned

    def build_house(self, user_id, color):
        can_act, jail_msg = self.can_act_in_jail(user_id)
        if not can_act:
            return False, jail_msg

        can_build, result = self.can_build_on_color(user_id, color)
        if not can_build:
            return False, result

        player = self.players[user_id]
        props = result

        for prop in props:
            if prop.get('hotel'):
                return False, f"На {prop['name']} уже стоит отель"
            if prop.get('houses', 0) >= 4:
                return False, f"На {prop['name']} уже 4 дома - строй отель: /hotel {color}"

        price_per_house = self.get_house_price(color)
        total_cost = price_per_house * len(props)

        if player['money'] < total_cost:
            return False, f"Не хватает денег. Нужно {total_cost}$ ({price_per_house}$ * {len(props)} улиц), у тебя {player['money']}$"

        player['money'] -= total_cost
        for prop in props:
            prop['houses'] = prop.get('houses', 0) + 1

        houses_now = props[0]['houses']
        return True, (f"{player['name']} построил дома на улицах {color}!\n"
                      f"Домов на каждой: {houses_now}\n"
                      f"Потрачено: {total_cost}$\n"
                      f"Осталось: {player['money']}$")

    def build_hotel(self, user_id, color):
        can_act, jail_msg = self.can_act_in_jail(user_id)
        if not can_act:
            return False, jail_msg

        can_build, result = self.can_build_on_color(user_id, color)
        if not can_build:
            return False, result

        player = self.players[user_id]
        props = result

        for prop in props:
            if prop.get('hotel'):
                return False, f"Отель уже есть на {prop['name']}"
            if prop.get('houses', 0) < 4:
                return False, f"Нужно 4 дома на {prop['name']} перед постройкой отеля. Сейчас: {prop.get('houses', 0)}"

        price_per_hotel = self.get_house_price(color) * 5
        total_cost = price_per_hotel

        if player['money'] < total_cost:
            return False, f"Не хватает денег. Нужно {total_cost}$, у тебя {player['money']}$"

        player['money'] -= total_cost
        for prop in props:
            prop['houses'] = 0
            prop['hotel'] = True

        return True, (f"{player['name']} построил отели на улицах {color}!\n"
                      f"Потрачено: {total_cost}$\n"
                      f"Осталось: {player['money']}$")

    def get_color_groups(self, user_id):
        color_groups = {}
        for prop_id in self.players[user_id]['properties']:
            cell = self.CELLS[prop_id]
            color = cell.get('color')
            if color and cell.get('type') == 'property':
                color_groups.setdefault(color, []).append(cell)

        complete = {}
        for color, props in color_groups.items():
            all_props = [c for c in self.CELLS if c.get('color') == color and c.get('type') == 'property']
            if len(props) == len(all_props):
                complete[color] = props
        return complete

    """Залог"""

    def mortgage_property(self, user_id, cell_id):
        player = self.players[user_id]
        cell = self.CELLS[cell_id]

        if cell.get('owner') != user_id:
            return False, "Это не твоя собственность"
        if cell.get('mortgaged'):
            return False, f"{cell['name']} уже заложена!"
        if cell.get('houses', 0) > 0 or cell.get('hotel'):
            return False, f"Сначала снеси постройки на {cell['name']}"

        mortgage_value = cell['price'] // 2
        cell['mortgaged'] = True
        player['money'] += mortgage_value

        return True, (f"{cell['name']} заложена\n"
                      f"Получено: {mortgage_value}$\n"
                      f"Баланс: {player['money']}$\n"
                      f"Выкуп: {int(mortgage_value * 1.1)}$ (залог + 10%)")

    def unmortgage_property(self, user_id, cell_id):
        player = self.players[user_id]
        cell = self.CELLS[cell_id]

        if cell.get('owner') != user_id:
            return False, "Это не твоя собственность"
        if not cell.get('mortgaged'):
            return False, f"{cell['name']} не заложена"

        mortgage_value = cell['price'] // 2
        redeem_cost = int(mortgage_value * 1.1)

        if player['money'] < redeem_cost:
            return False, f"Не хватает денег. Нужно {redeem_cost}$, у тебя {player['money']}$"

        cell['mortgaged'] = False
        player['money'] -= redeem_cost

        return True, (f"{cell['name']} выкуплена!\n"
                      f"Заплачено: {redeem_cost}$\n"
                      f"Баланс: {player['money']}$")

    def get_mortgageable_properties(self, user_id):
        result = []
        for prop_id in self.players[user_id]['properties']:
            cell = self.CELLS[prop_id]
            if not cell.get('mortgaged') and cell.get('houses', 0) == 0 and not cell.get('hotel'):
                result.append((prop_id, cell))
        return result

    def get_mortgaged_properties(self, user_id):
        result = []
        for prop_id in self.players[user_id]['properties']:
            cell = self.CELLS[prop_id]
            if cell.get('mortgaged'):
                result.append((prop_id, cell))
        return result