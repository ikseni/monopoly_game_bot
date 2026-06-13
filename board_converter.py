"""класс для вычисления точных координат для отрисовки объектов на карте"""

class MonopolyConverter:
    BOARD_SIZE = 1000
    INNER_LINE_1 = 140
    INNER_LINE_2 = 860

    PLAYER_SIZE = 50
    PROPERTY_LINE_THICKNESS = 8
    BUILDING_SIZE = 15

    @classmethod
    def get_cell_bounds(cls, cell_index: int):
        """Возвращает (x1, y1, x2, y2, side) границы клетки."""
        side = cell_index // 10
        pos_on_side = cell_index % 10
        step = (cls.INNER_LINE_2 - cls.INNER_LINE_1) / 9

        if side == 0:  #низ
            if pos_on_side == 0:
                x2 = cls.BOARD_SIZE
                x1 = cls.INNER_LINE_2
            else:
                x2 = cls.INNER_LINE_2 - (pos_on_side - 1) * step
                x1 = x2 - step
            y1, y2 = cls.INNER_LINE_2, cls.BOARD_SIZE

        elif side == 1:  # лево
            if pos_on_side == 0:
                y2 = cls.BOARD_SIZE
                y1 = cls.INNER_LINE_2
            else:
                y2 = cls.INNER_LINE_2 - (pos_on_side - 1) * step
                y1 = y2 - step
            x1, x2 = 0, cls.INNER_LINE_1

        elif side == 2:  # верх
            if pos_on_side == 0:
                x1 = 0
                x2 = cls.INNER_LINE_1
            else:
                x1 = cls.INNER_LINE_1 + (pos_on_side - 1) * step
                x2 = x1 + step
            y1, y2 = 0, cls.INNER_LINE_1

        else:  #рпаво
            if pos_on_side == 0:
                y1 = 0
                y2 = cls.INNER_LINE_1
            else:
                y1 = cls.INNER_LINE_1 + (pos_on_side - 1) * step
                y2 = y1 + step
            x1, x2 = cls.INNER_LINE_2, cls.BOARD_SIZE

        return x1, y1, x2, y2, side

    @classmethod
    def get_physical_coords(cls, cell_index: int, category: str, player_id: int = 1):
        """
        Возвращает (x, y) для отрисовки объекта на клетке.
        """
        cell_index = cell_index % 40
        x1, y1, x2, y2, side = cls.get_cell_bounds(cell_index)

        cell_w = x2 - x1
        cell_h = y2 - y1
        half_w = cell_w / 2
        half_h = cell_h / 2

        if category == 'property_strip':
            if side == 0:
                return (x1, y2 - cls.PROPERTY_LINE_THICKNESS)
            elif side == 1:
                return (x1, y1)
            elif side == 2:
                return (x1, y1)
            elif side == 3:
                return (x2 - cls.PROPERTY_LINE_THICKNESS, y1)

        elif category == 'building':

            if cell_index % 10 == 0:
                return (0, 0)

            size = cls.BUILDING_SIZE
            total_size = 4 * size + 3 * 2
            offset = 120

            if side == 0:
                return (x1 + half_w - total_size / 2, y2 - offset - size)
            elif side == 1:
                return (x1 + offset, y1 + half_h - total_size / 2)
            elif side == 2:
                return (x1 + half_w - total_size / 2, y1 + offset)
            elif side == 3:
                return (x2 - offset - size, y1 + half_h - total_size / 2)

        elif category == 'player':
            step_shift = 12
            is_corner = (cell_index % 10 == 0)
            start_offset = 0 if is_corner else (cls.BUILDING_SIZE + 5)

            if side == 0:
                player_x = x1 + half_w - cls.PLAYER_SIZE / 2
                player_y = y2 - start_offset - cls.PLAYER_SIZE - (player_id - 1) * step_shift
                return (player_x, player_y)
            elif side == 1:
                player_x = x1 + start_offset + (player_id - 1) * step_shift
                player_y = y1 + half_h - cls.PLAYER_SIZE / 2
                return (player_x, player_y)
            elif side == 2:
                player_x = x1 + half_w - cls.PLAYER_SIZE / 2
                player_y = y1 + start_offset + (player_id - 1) * step_shift
                return (player_x, player_y)
            elif side == 3:
                player_y = y1 + half_h - cls.PLAYER_SIZE / 2
                player_x = x2 - start_offset - cls.PLAYER_SIZE - (player_id - 1) * step_shift
                return (player_x, player_y)

        raise ValueError(f"Неизвестная категория: {category}")