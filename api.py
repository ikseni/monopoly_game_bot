from flask import Flask, jsonify, request
from flask_cors import CORS
from state import games
import random

app = Flask(__name__)
CORS(app)  # разрешаем запросы из мини-приложения


@app.route('/api/game_state', methods=['GET'])
def get_game_state():
    """Возвращает состояние игры для отображения карты"""
    room_code = request.args.get('room')

    if not room_code:
        return jsonify({'error': 'Не указан код комнаты'}), 400

    game = games.get(room_code)
    if not game:
        return jsonify({'error': 'Игра не найдена'}), 404

    if not game.game_started:
        return jsonify({'error': 'Игра ещё не началась'}), 400

    # Собираем данные о клетках
    cells_data = []
    for cell in game.CELLS:
        cells_data.append({
            'id': cell['id'],
            'name': cell['name'],
            'owner': cell.get('owner'),
            'color': cell.get('color'),
            'houses': cell.get('houses', 0),
            'hotel': cell.get('hotel', False)
        })

    # Собираем данные об игроках
    players_data = []
    for user_id, player in game.players.items():
        players_data.append({
            'id': user_id,
            'name': player['name'],
            'money': player['money'],
            'position': player['position'],
            'in_jail': player.get('in_jail', False)
        })

    return jsonify({
        'cells': cells_data,
        'players': players_data,
        'current_turn': game.current_turn
    })


@app.route('/api/roll', methods=['POST'])
def roll_dice():
    """Бросок кубиков от имени игрока"""
    data = request.json
    room_code = data.get('room')
    user_id = data.get('user_id')

    if not room_code or not user_id:
        return jsonify({'error': 'Не указан код комнаты или ID игрока'}), 400

    game = games.get(room_code)
    if not game:
        return jsonify({'error': 'Игра не найдена'}), 404

    if not game.game_started:
        return jsonify({'error': 'Игра ещё не началась'}), 400

    if game.current_turn != user_id:
        return jsonify({'error': 'Сейчас не твой ход'}), 403

    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    dice_sum = dice1 + dice2

    # Перемещаем игрока
    msg, need_purchase, bankrupt = game.move_player(user_id, dice_sum)

    # Обновляем ход если не нужно покупать
    if not need_purchase and not bankrupt:
        game.next_turn()

    return jsonify({
        'success': True,
        'dice1': dice1,
        'dice2': dice2,
        'dice_sum': dice_sum,
        'new_position': game.players[user_id]['position'],
        'need_purchase': need_purchase,
        'bankrupt': bankrupt,
        'message': msg
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)