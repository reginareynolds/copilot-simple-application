"""Game rules and state for classic Minesweeper."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import random
from typing import Iterable

Position = tuple[int, int]


@dataclass(frozen=True)
class Difficulty:
    name: str
    columns: int
    rows: int
    mine_count: int


DIFFICULTIES = (
    Difficulty("Beginner", columns=9, rows=9, mine_count=10),
    Difficulty("Intermediate", columns=16, rows=16, mine_count=40),
    Difficulty("Expert", columns=30, rows=16, mine_count=99),
)


class MinesweeperGame:
    """A Minesweeper board whose mines are placed on the first reveal."""

    READY = "ready"
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"

    def __init__(self, difficulty: Difficulty, rng: random.Random | None = None):
        if (
            difficulty.columns < 1
            or difficulty.rows < 1
            or difficulty.mine_count < 0
            or difficulty.mine_count >= difficulty.columns * difficulty.rows
        ):
            raise ValueError("Board dimensions and mine count must define a safe cell.")

        self.difficulty = difficulty
        self._rng = rng or random.Random()
        self.mines: set[Position] = set()
        self.revealed: set[Position] = set()
        self.flags: set[Position] = set()
        self.state = self.READY
        self.exploded: Position | None = None

    def neighbors(self, position: Position) -> Iterable[Position]:
        column, row = position
        for neighbor_row in range(max(0, row - 1), min(self.difficulty.rows, row + 2)):
            for neighbor_column in range(
                max(0, column - 1), min(self.difficulty.columns, column + 2)
            ):
                neighbor = (neighbor_column, neighbor_row)
                if neighbor != position:
                    yield neighbor

    def adjacent_mines(self, position: Position) -> int:
        return sum(neighbor in self.mines for neighbor in self.neighbors(position))

    def reveal(self, position: Position) -> set[Position]:
        """Reveal a cell and any connected empty area; return newly revealed cells."""
        if self.state in (self.WON, self.LOST):
            return set()
        if (
            not self._is_in_bounds(position)
            or position in self.flags
            or position in self.revealed
        ):
            return set()

        if self.state == self.READY:
            self._place_mines(position)
            self.state = self.PLAYING

        if position in self.mines:
            self.exploded = position
            self.state = self.LOST
            return set()

        newly_revealed: set[Position] = set()
        pending = deque([position])
        while pending:
            current = pending.popleft()
            if (
                current in self.revealed
                or current in self.flags
                or current in self.mines
            ):
                continue
            self.revealed.add(current)
            newly_revealed.add(current)
            if self.adjacent_mines(current) == 0:
                pending.extend(
                    neighbor
                    for neighbor in self.neighbors(current)
                    if neighbor not in self.revealed and neighbor not in self.flags
                )

        if len(self.revealed) == self.difficulty.columns * self.difficulty.rows - len(
            self.mines
        ):
            self.state = self.WON
        return newly_revealed

    def toggle_flag(self, position: Position) -> bool:
        """Toggle a flag on a covered cell; return whether it is now flagged."""
        if self.state in (self.WON, self.LOST) or not self._is_in_bounds(position):
            return False
        if position in self.revealed:
            return False
        if position in self.flags:
            self.flags.remove(position)
            return False
        self.flags.add(position)
        return True

    @property
    def remaining_mines(self) -> int:
        return self.difficulty.mine_count - len(self.flags)

    def _place_mines(self, safe_position: Position) -> None:
        available = [
            (column, row)
            for row in range(self.difficulty.rows)
            for column in range(self.difficulty.columns)
            if (column, row) != safe_position
        ]
        self.mines = set(self._rng.sample(available, self.difficulty.mine_count))

    def _is_in_bounds(self, position: Position) -> bool:
        column, row = position
        return 0 <= column < self.difficulty.columns and 0 <= row < self.difficulty.rows
