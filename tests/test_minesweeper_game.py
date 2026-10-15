import random
import unittest

from minesweeper_game import DIFFICULTIES, Difficulty, MinesweeperGame


class MinesweeperGameTests(unittest.TestCase):
    def setUp(self):
        self.difficulty = Difficulty("Test", columns=5, rows=5, mine_count=4)

    def test_classic_difficulties_match_standard_board_sizes(self):
        self.assertEqual(
            [(item.columns, item.rows, item.mine_count) for item in DIFFICULTIES],
            [(9, 9, 10), (16, 16, 40), (30, 16, 99)],
        )

    def test_first_reveal_places_exact_mines_and_is_safe(self):
        game = MinesweeperGame(self.difficulty, rng=random.Random(7))

        game.reveal((2, 2))

        self.assertEqual(len(game.mines), self.difficulty.mine_count)
        self.assertNotIn((2, 2), game.mines)
        self.assertIn((2, 2), game.revealed)
        self.assertEqual(game.state, MinesweeperGame.PLAYING)

    def test_flagging_changes_counter_and_prevents_reveal(self):
        game = MinesweeperGame(self.difficulty, rng=random.Random(7))
        position = (1, 1)

        self.assertTrue(game.toggle_flag(position))
        self.assertEqual(game.remaining_mines, 3)
        self.assertEqual(game.reveal(position), set())
        self.assertEqual(game.state, MinesweeperGame.READY)
        self.assertFalse(game.toggle_flag(position))
        self.assertEqual(game.remaining_mines, 4)

    def test_adjacent_mine_count(self):
        game = MinesweeperGame(self.difficulty)
        game.mines = {(0, 0), (1, 0), (4, 4)}

        self.assertEqual(game.adjacent_mines((1, 1)), 2)
        self.assertEqual(game.adjacent_mines((3, 3)), 1)

    def test_revealing_mine_loses_and_reveals_mines_to_ui(self):
        game = MinesweeperGame(self.difficulty, rng=random.Random(7))
        game.reveal((2, 2))
        mine = next(iter(game.mines))

        game.reveal(mine)

        self.assertEqual(game.state, MinesweeperGame.LOST)
        self.assertEqual(game.exploded, mine)
        self.assertEqual(game.reveal((0, 0)), set())

    def test_revealing_all_safe_cells_wins(self):
        difficulty = Difficulty("Tiny", columns=3, rows=3, mine_count=1)
        game = MinesweeperGame(difficulty, rng=random.Random(2))
        game.reveal((1, 1))

        for row in range(difficulty.rows):
            for column in range(difficulty.columns):
                position = (column, row)
                if position not in game.mines:
                    game.reveal(position)

        self.assertEqual(game.state, MinesweeperGame.WON)
        self.assertEqual(len(game.revealed), 8)
        self.assertEqual(game.toggle_flag((0, 0)), False)

    def test_revealing_empty_area_expands_across_board(self):
        difficulty = Difficulty("Empty", columns=4, rows=4, mine_count=0)
        game = MinesweeperGame(difficulty)

        newly_revealed = game.reveal((0, 0))

        self.assertEqual(len(newly_revealed), 16)
        self.assertEqual(game.state, MinesweeperGame.WON)

    def test_out_of_bounds_input_is_ignored(self):
        game = MinesweeperGame(self.difficulty)

        self.assertEqual(game.reveal((-1, 0)), set())
        self.assertFalse(game.toggle_flag((5, 0)))
        self.assertEqual(game.state, MinesweeperGame.READY)


if __name__ == "__main__":
    unittest.main()
