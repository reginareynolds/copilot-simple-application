"""HTTP server for the browser-based Minesweeper game."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Any
from urllib.parse import urlsplit

from minesweeper_game import DIFFICULTIES, Difficulty, MinesweeperGame, Position

WEB_DIRECTORY = Path(__file__).parent / "web"
SESSION_COOKIE = "minesweeper_session"
MAX_REQUEST_BYTES = 4096
DIFFICULTIES_BY_NAME = {difficulty.name.lower(): difficulty for difficulty in DIFFICULTIES}


@dataclass
class GameSession:
    game: MinesweeperGame | None = None
    started_at: float | None = None


class MinesweeperServer(ThreadingHTTPServer):
    """Threaded local web server with independent game state per browser session."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int]):
        self.sessions: dict[str, GameSession] = {}
        self.sessions_lock = threading.Lock()
        super().__init__(address, MinesweeperRequestHandler)


class MinesweeperRequestHandler(BaseHTTPRequestHandler):
    server: MinesweeperServer

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._send_file("index.html", "text/html; charset=utf-8", establish_session=True)
        elif path == "/app.css":
            self._send_file("app.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._send_file("app.js", "text/javascript; charset=utf-8")
        elif path == "/api/state":
            session, token, created = self._get_session()
            with self.server.sessions_lock:
                payload = self._serialize_session(session)
            self._send_json(HTTPStatus.OK, payload, token if created else None)
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        session, token, created = self._get_session()
        cookie = token if created else None
        try:
            body = self._read_json()
            with self.server.sessions_lock:
                if path == "/api/new":
                    self._start_game(session, body)
                elif path == "/api/menu":
                    self._show_difficulty_menu(session)
                elif path == "/api/reveal":
                    self._reveal(session, body)
                elif path == "/api/flag":
                    self._toggle_flag(session, body)
                else:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."}, cookie)
                    return
                payload = self._serialize_session(session)
            self._send_json(HTTPStatus.OK, payload, cookie)
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)}, cookie)

    def _read_json(self) -> dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid Content-Length header.") from error
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            raise ValueError("Request body must be between 1 and 4096 bytes.")
        try:
            data = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("Request body must contain valid JSON.") from error
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _start_game(self, session: GameSession, body: dict[str, Any]) -> None:
        name = body.get("difficulty")
        if not isinstance(name, str) or name.lower() not in DIFFICULTIES_BY_NAME:
            raise ValueError("Choose Beginner, Intermediate, or Expert.")
        session.game = MinesweeperGame(DIFFICULTIES_BY_NAME[name.lower()])
        session.started_at = None

    @staticmethod
    def _show_difficulty_menu(session: GameSession) -> None:
        session.game = None
        session.started_at = None

    def _reveal(self, session: GameSession, body: dict[str, Any]) -> None:
        game = self._require_game(session)
        position = self._position(body, game.difficulty)
        was_ready = game.state == MinesweeperGame.READY
        game.reveal(position)
        if was_ready and game.state != MinesweeperGame.READY:
            session.started_at = time.monotonic()

    def _toggle_flag(self, session: GameSession, body: dict[str, Any]) -> None:
        game = self._require_game(session)
        game.toggle_flag(self._position(body, game.difficulty))

    @staticmethod
    def _require_game(session: GameSession) -> MinesweeperGame:
        if session.game is None:
            raise ValueError("Choose a difficulty before playing.")
        return session.game

    @staticmethod
    def _position(body: dict[str, Any], difficulty: Difficulty) -> Position:
        column, row = body.get("column"), body.get("row")
        if (
            isinstance(column, bool)
            or not isinstance(column, int)
            or isinstance(row, bool)
            or not isinstance(row, int)
        ):
            raise ValueError("Cell coordinates must be integers.")
        if not (0 <= column < difficulty.columns and 0 <= row < difficulty.rows):
            raise ValueError("Cell coordinates are outside the board.")
        return column, row

    @staticmethod
    def _serialize_session(session: GameSession) -> dict[str, Any]:
        game = session.game
        if game is None:
            return {
                "phase": "choose",
                "difficulties": [
                    {
                        "name": difficulty.name,
                        "columns": difficulty.columns,
                        "rows": difficulty.rows,
                        "mine_count": difficulty.mine_count,
                    }
                    for difficulty in DIFFICULTIES
                ],
            }

        lost = game.state == MinesweeperGame.LOST
        won = game.state == MinesweeperGame.WON
        board = []
        for row in range(game.difficulty.rows):
            board_row = []
            for column in range(game.difficulty.columns):
                position = (column, row)
                is_mine = position in game.mines
                is_flagged = (position in game.flags and not (lost and is_mine)) or (
                    won and is_mine
                )
                is_revealed = position in game.revealed
                cell: dict[str, Any] = {
                    "revealed": is_revealed,
                    "flagged": is_flagged,
                }
                if is_revealed:
                    cell["adjacent"] = game.adjacent_mines(position)
                if lost and is_mine:
                    cell["mine"] = True
                    cell["exploded"] = position == game.exploded
                board_row.append(cell)
            board.append(board_row)

        elapsed = 0
        if session.started_at is not None:
            elapsed = int(time.monotonic() - session.started_at)
        return {
            "phase": game.state,
            "difficulty": {
                "name": game.difficulty.name,
                "columns": game.difficulty.columns,
                "rows": game.difficulty.rows,
                "mine_count": game.difficulty.mine_count,
            },
            "remaining_mines": 0 if won else game.remaining_mines,
            "elapsed_seconds": elapsed,
            "board": board,
        }

    def _get_session(self) -> tuple[GameSession, str, bool]:
        cookies = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        cookie = cookies.get(SESSION_COOKIE)
        token = cookie.value if cookie is not None else ""
        with self.server.sessions_lock:
            session = self.server.sessions.get(token)
            if session is not None:
                return session, token, False
            token = secrets.token_urlsafe(32)
            session = GameSession()
            self.server.sessions[token] = session
        return session, token, True

    def _send_file(
        self, filename: str, content_type: str, establish_session: bool = False
    ) -> None:
        try:
            content = (WEB_DIRECTORY / filename).read_bytes()
        except OSError:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Web asset unavailable."})
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if establish_session:
            _, token, _ = self._get_session()
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax",
            )
        self.end_headers()
        self.wfile.write(content)

    def _send_json(
        self,
        status: HTTPStatus,
        payload: dict[str, Any],
        cookie: str | None = None,
    ) -> None:
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie is not None:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={cookie}; Path=/; HttpOnly; SameSite=Lax",
            )
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        super().log_message(format, *args)


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    with MinesweeperServer((host, port)) as server:
        print(f"Minesweeper is running on http://{host}:{server.server_port}")
        print("Open this port in Codespaces to play in your browser.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Minesweeper.")


if __name__ == "__main__":
    main()
