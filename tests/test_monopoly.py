import pytest
import random
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_logic import Game
from game_data import CELLS, HOUSE_PRICES


@pytest.fixture
def game_with_two_players():
    game = Game("TEST123", 111)
    game.add_player(111, "Анна")
    game.add_player(222, "Борис")
    game.start_game()
    game.current_turn = 111
    return game


@pytest.fixture
def game_with_brown_set():
    game = Game("TEST123", 111)
    game.add_player(111, "Анна")
    game.add_player(222, "Борис")
    game.start_game()
    game.current_turn = 111
    for cell in game.CELLS:
        if cell.get('color') == 'brown' and cell.get('type') == 'property':
            cell['owner'] = 111
            game.players[111]['properties'].append(cell['id'])
    return game


class TestGameCreation:
    """Тесты создания игры и добавления игроков"""

    def test_create_game(self):
        game = Game("TEST123", 111)
        assert game.room_code == "TEST123"
        assert game.owner_id == 111
        assert len(game.players) == 0
        assert not game.game_started

    def test_generate_room_code(self):
        code = Game.generate_room_code()
        assert len(code) == 6
        assert code.isalnum()
        assert code.isupper()

    def test_add_player(self):
        game = Game("TEST123", 111)
        success, msg = game.add_player(123, "Тест")
        assert success
        assert "присоединился" in msg
        assert len(game.players) == 1
        assert game.players[123]['money'] == 1500

    def test_add_duplicate_player(self):
        game = Game("TEST123", 111)
        game.add_player(123, "Тест")
        success, msg = game.add_player(123, "Тест2")
        assert not success
        assert "уже в игре" in msg

    def test_start_game_not_enough_players(self):
        game = Game("TEST123", 111)
        game.add_player(111, "Анна")
        success, msg = game.start_game()
        assert not success
        assert "минимум 2" in msg

    def test_start_game_success(self):
        game = Game("TEST123", 111)
        game.add_player(111, "Анна")
        game.add_player(222, "Борис")
        success, msg = game.start_game()
        assert success
        assert game.game_started
        assert game.current_turn in [111, 222]


class TestMovement:
    """Тесты перемещения по полю"""

    def test_move_player_normal(self, game_with_two_players):
        game = game_with_two_players
        player = game.get_player(111)
        player['position'] = 5
        player['money'] = 1000

        msg, need_purchase, bankrupt = game.move_player(111, 3)

        assert player['position'] == 8
        assert msg != ""
        assert not bankrupt

    def test_move_player_pass_start(self, game_with_two_players):
        game = game_with_two_players
        player = game.get_player(111)
        player['position'] = 38
        player['money'] = 1000

        msg, need_purchase, bankrupt = game.move_player(111, 5)

        assert player['position'] == 3
        assert player['money'] == 1200
        assert "проход" in msg.lower()

    def test_move_player_exact_start(self, game_with_two_players):
        game = game_with_two_players
        player = game.get_player(111)
        player['position'] = 39
        player['money'] = 1000

        msg, need_purchase, bankrupt = game.move_player(111, 1)

        assert player['position'] == 0
        assert player['money'] == 1200


class TestPropertyPurchase:
    """Тесты покупки недвижимости"""

    def test_buy_property_success(self, game_with_two_players):
        game = game_with_two_players
        game.waiting_for_purchase = True
        game.pending_purchase = {'user_id': 111, 'cell_id': 1}

        success, msg = game.buy_property(111)

        assert success
        assert game.CELLS[1]['owner'] == 111
        assert 1 in game.players[111]['properties']
        assert game.players[111]['money'] == 1440

    def test_buy_property_not_enough_money(self, game_with_two_players):
        game = game_with_two_players
        game.players[111]['money'] = 50
        game.waiting_for_purchase = True
        game.pending_purchase = {'user_id': 111, 'cell_id': 1}

        success, msg = game.buy_property(111)

        assert not success
        assert "Не хватает денег" in msg

    def test_buy_property_already_owned(self, game_with_two_players):
        game = game_with_two_players
        game.CELLS[1]['owner'] = 222
        game.waiting_for_purchase = True
        game.pending_purchase = {'user_id': 111, 'cell_id': 1}

        success, msg = game.buy_property(111)

        assert not success
        assert "уже куплена" in msg


class TestRent:
    """Тесты расчёта арендной платы"""

    def test_property_rent_basic(self, game_with_two_players):
        game = game_with_two_players
        cell = game.CELLS[1]
        cell['owner'] = 222
        cell['houses'] = 0
        cell['hotel'] = False

        rent = game.get_property_rent(cell)
        assert rent == 2

    def test_property_rent_monopoly(self, game_with_two_players):
        game = game_with_two_players
        game.CELLS[1]['owner'] = 222
        game.CELLS[3]['owner'] = 222
        cell = game.CELLS[1]

        rent = game.get_property_rent(cell)
        assert rent == 10

    def test_property_rent_with_1_house(self, game_with_two_players):
        game = game_with_two_players
        cell = game.CELLS[1]
        cell['owner'] = 222
        cell['houses'] = 1

        rent = game.get_property_rent(cell)
        assert rent == 30

    def test_property_rent_with_hotel(self, game_with_two_players):
        game = game_with_two_players
        cell = game.CELLS[1]
        cell['owner'] = 222
        cell['hotel'] = True

        rent = game.get_property_rent(cell)
        assert rent == 250

    def test_mortgaged_property_rent_zero(self, game_with_two_players):
        game = game_with_two_players
        cell = game.CELLS[1]
        cell['owner'] = 222
        cell['mortgaged'] = True

        rent = game.get_property_rent(cell)
        assert rent == 0

    @pytest.mark.parametrize("stations,expected", [
        (1, 25), (2, 50), (3, 100), (4, 200),
    ])
    def test_station_rent(self, game_with_two_players, stations, expected):
        game = game_with_two_players
        station_ids = [5, 15, 25, 35]
        for i in range(stations):
            game.CELLS[station_ids[i]]['owner'] = 222

        rent = game.get_station_rent(222)
        assert rent == expected

    @pytest.mark.parametrize("utilities,expected", [
        (1, 28), (2, 70),
    ])
    def test_utility_rent(self, game_with_two_players, utilities, expected):
        game = game_with_two_players
        if utilities >= 1:
            game.CELLS[12]['owner'] = 222
        if utilities >= 2:
            game.CELLS[28]['owner'] = 222

        rent = game.get_utility_rent(222, 7)
        assert rent == expected


class TestJail:
    """Тесты тюремной механики"""

    def test_move_to_jail(self, game_with_two_players):
        game = game_with_two_players
        player = game.get_player(111)
        player['position'] = 5

        msg = game.move_to_jail(111)

        assert player['in_jail']
        assert player['position'] == 10
        assert "тюрьму" in msg

    def test_jail_turn_no_double_first_attempt(self, game_with_two_players, monkeypatch):
        game = game_with_two_players
        player = game.get_player(111)
        player['in_jail'] = True
        player['jail_turns'] = 0
        player['money'] = 500

        values = [1, 2]
        call_count = 0

        def mock_randint(a, b):
            nonlocal call_count
            val = values[call_count % 2]
            call_count += 1
            return val

        monkeypatch.setattr(random, 'randint', mock_randint)

        can_move, msg, dice_sum, is_double = game.process_jail_turn(111)

        assert can_move == False
        assert player['jail_turns'] == 1
        assert "не дубль" in msg

    def test_jail_turn_double_escape(self, game_with_two_players, monkeypatch):
        game = game_with_two_players
        player = game.get_player(111)
        player['in_jail'] = True
        player['jail_turns'] = 0
        player['money'] = 500

        values = [3, 3]
        call_count = 0

        def mock_randint(a, b):
            nonlocal call_count
            val = values[call_count % 2]
            call_count += 1
            return val

        monkeypatch.setattr(random, 'randint', mock_randint)

        can_move, msg, dice_sum, is_double = game.process_jail_turn(111)

        assert can_move
        assert is_double
        assert not player['in_jail']
        assert "Дубль" in msg

    def test_jail_turn_third_attempt_pay_fine(self, game_with_two_players, monkeypatch):
        game = game_with_two_players
        player = game.get_player(111)
        player['in_jail'] = True
        player['jail_turns'] = 2
        player['money'] = 500

        values = [1, 3]
        call_count = 0

        def mock_randint(a, b):
            nonlocal call_count
            val = values[call_count % 2]
            call_count += 1
            return val

        monkeypatch.setattr(random, 'randint', mock_randint)

        can_move, msg, dice_sum, is_double = game.process_jail_turn(111)

        assert can_move == True
        assert player['in_jail'] == False
        assert player['money'] in [450, 500]
        assert "3-я попытка" in msg or "штрафа" in msg


class TestAuction:
    """Тесты аукциона"""

    def test_start_auction(self, game_with_two_players):
        game = game_with_two_players
        msg = game.start_auction(1)

        assert game.auction is not None
        assert game.auction['active']
        assert "Аукцион" in msg

    def test_make_bid_higher(self, game_with_two_players):
        game = game_with_two_players
        game.start_auction(1)

        success, msg = game.make_bid(111, 100)

        assert success
        assert game.auction['current_bid'] == 100
        assert game.auction['current_bidder'] == 111

    def test_make_bid_too_low(self, game_with_two_players):
        game = game_with_two_players
        game.start_auction(1)
        game.auction['current_bid'] = 80

        success, msg = game.make_bid(111, 70)

        assert not success
        assert "выше" in msg

    def test_pass_auction(self, game_with_two_players):
        game = game_with_two_players
        game.start_auction(1)

        success, msg, end_result = game.pass_auction(111)

        assert success
        assert 111 in game.auction['passed']
        assert "отказался" in msg

    def test_force_end_auction_with_winner(self, game_with_two_players):
        game = game_with_two_players
        game.start_auction(1)
        game.make_bid(111, 100)

        result = game.force_end_auction()

        assert "Аукцион завершён" in result
        assert game.CELLS[1]['owner'] == 111

    def test_force_end_auction_without_winner(self, game_with_two_players):
        game = game_with_two_players
        game.start_auction(1)

        result = game.force_end_auction()

        assert "никто не купил" in result
        assert game.CELLS[1]['owner'] is None


class TestBuilding:
    """Тесты строительства домов и отелей"""

    def test_can_build_on_color_missing_properties(self, game_with_two_players):
        game = game_with_two_players
        game.CELLS[1]['owner'] = 111

        can_build, result = game.can_build_on_color(111, 'brown')

        assert not can_build
        assert "всеми" in result.lower()

    def test_can_build_on_color_success(self, game_with_brown_set):
        game = game_with_brown_set

        can_build, result = game.can_build_on_color(111, 'brown')

        assert can_build
        assert len(result) == 2

    def test_build_house_success(self, game_with_brown_set):
        game = game_with_brown_set
        game.players[111]['money'] = 500

        success, msg = game.build_house(111, 'brown')

        assert success
        assert game.CELLS[1]['houses'] == 1
        assert game.CELLS[3]['houses'] == 1
        assert game.players[111]['money'] == 400

    def test_build_house_not_enough_money(self, game_with_brown_set):
        game = game_with_brown_set
        game.players[111]['money'] = 50

        success, msg = game.build_house(111, 'brown')

        assert not success
        assert "Не хватает денег" in msg

    def test_build_hotel_success(self, game_with_brown_set):
        game = game_with_brown_set
        game.CELLS[1]['houses'] = 4
        game.CELLS[3]['houses'] = 4
        game.players[111]['money'] = 1000

        success, msg = game.build_hotel(111, 'brown')

        assert success
        assert game.CELLS[1]['hotel']
        assert game.CELLS[3]['hotel']


class TestMortgage:
    """Тесты залога и выкупа"""

    def test_mortgage_property_success(self, game_with_two_players):
        game = game_with_two_players
        game.CELLS[1]['owner'] = 111
        game.players[111]['properties'].append(1)
        game.players[111]['money'] = 500

        success, msg = game.mortgage_property(111, 1)

        assert success
        assert game.CELLS[1]['mortgaged']
        assert game.players[111]['money'] == 530

    def test_mortgage_property_with_houses(self, game_with_two_players):
        game = game_with_two_players
        game.CELLS[1]['owner'] = 111
        game.CELLS[1]['houses'] = 1

        success, msg = game.mortgage_property(111, 1)

        assert not success
        assert "снеси постройки" in msg

    def test_unmortgage_property_success(self, game_with_two_players):
        game = game_with_two_players
        game.CELLS[1]['owner'] = 111
        game.CELLS[1]['mortgaged'] = True
        game.players[111]['money'] = 500

        success, msg = game.unmortgage_property(111, 1)

        assert success
        assert not game.CELLS[1]['mortgaged']


class TestTurnOrder:
    """Тесты очерёдности ходов"""

    def test_next_turn(self, game_with_two_players):
        game = game_with_two_players
        game.current_turn = 111
        game.turn_order = [111, 222]

        next_name = game.next_turn()

        assert game.current_turn == 222
        assert next_name == "Борис"

    def test_is_my_turn(self, game_with_two_players):
        game = game_with_two_players
        game.current_turn = 111

        assert game.is_my_turn(111)
        assert not game.is_my_turn(222)


class TestUtilityMethods:
    """Тесты вспомогательных методов"""

    def test_owns_full_color(self, game_with_two_players):
        game = game_with_two_players
        game.CELLS[1]['owner'] = 222
        game.CELLS[3]['owner'] = 222

        assert game.owns_full_color(222, 'brown')
        assert not game.owns_full_color(222, 'lightblue')

    def test_get_house_price(self, game_with_two_players):
        game = game_with_two_players
        assert game.get_house_price('brown') == 50
        assert game.get_house_price('darkblue') == 200
        assert game.get_house_price('nonexistent') == 100

    def test_get_color_groups(self, game_with_brown_set):
        game = game_with_brown_set

        groups = game.get_color_groups(111)

        assert 'brown' in groups
        assert len(groups['brown']) == 2


class TestBankruptcy:
    """Тесты банкротства"""

    def test_bankruptcy_on_rent(self, game_with_two_players):
        game = game_with_two_players
        game.CELLS[1]['owner'] = 222
        game.CELLS[1]['rent'] = [200, 400, 600, 800, 1000, 1200]
        game.players[111]['position'] = 0
        game.players[111]['money'] = 100

        msg, need_purchase, bankrupt = game.move_player(111, 1)

        assert bankrupt
        assert "БАНКРОТ" in msg

