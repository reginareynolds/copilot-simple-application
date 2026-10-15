import http.cookiejar
import json
import threading
import unittest
import urllib.error
import urllib.request

from minesweeper import MinesweeperServer


class MinesweeperWebTests(unittest.TestCase):
    def setUp(self):
        self.server = MinesweeperServer(("127.0.0.1", 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = self._new_opener()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    @staticmethod
    def _new_opener():
        cookies = http.cookiejar.CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

    def _request(self, path, payload=None, opener=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        return (opener or self.opener).open(request)

    def _state(self):
        with self._request("/api/state") as response:
            return json.loads(response.read())

    def test_serves_browser_app_and_initial_difficulty_selection(self):
        with self._request("/") as response:
            self.assertIn("text/html", response.headers["Content-Type"])
            self.assertIn("HttpOnly", response.headers["Set-Cookie"])
            self.assertIn(b"Minesweeper", response.read())

        state = self._state()

        self.assertEqual(state["phase"], "choose")
        self.assertEqual(
            [difficulty["name"] for difficulty in state["difficulties"]],
            ["Beginner", "Intermediate", "Expert"],
        )

    def test_new_game_and_first_reveal(self):
        with self._request("/api/new", {"difficulty": "Beginner"}) as response:
            state = json.loads(response.read())

        self.assertEqual(state["phase"], "ready")
        self.assertEqual(len(state["board"]), 9)
        self.assertEqual(len(state["board"][0]), 9)

        with self._request("/api/reveal", {"column": 0, "row": 0}) as response:
            state = json.loads(response.read())

        self.assertEqual(state["phase"], "playing")
        self.assertTrue(state["board"][0][0]["revealed"])
        self.assertFalse(state["board"][0][0].get("mine", False))
        self.assertEqual(state["remaining_mines"], 10)

    def test_flags_update_remaining_mine_count(self):
        self._request("/api/new", {"difficulty": "Beginner"}).close()

        with self._request("/api/flag", {"column": 2, "row": 3}) as response:
            state = json.loads(response.read())
        self.assertEqual(state["remaining_mines"], 9)
        self.assertTrue(state["board"][3][2]["flagged"])

        with self._request("/api/flag", {"column": 2, "row": 3}) as response:
            state = json.loads(response.read())
        self.assertEqual(state["remaining_mines"], 10)
        self.assertFalse(state["board"][3][2]["flagged"])

    def test_change_difficulty_returns_to_picker(self):
        self._request("/api/new", {"difficulty": "Expert"}).close()

        with self._request("/api/menu", {}) as response:
            state = json.loads(response.read())

        self.assertEqual(state["phase"], "choose")
        self.assertEqual(len(state["difficulties"]), 3)

    def test_difficulty_and_coordinate_errors_are_reported(self):
        with self.assertRaises(urllib.error.HTTPError) as invalid_difficulty:
            self._request("/api/new", {"difficulty": "custom"})
        self.assertEqual(invalid_difficulty.exception.code, 400)
        try:
            self.assertIn(
                "Choose Beginner",
                json.loads(invalid_difficulty.exception.read())["error"],
            )
        finally:
            invalid_difficulty.exception.close()

        self._request("/api/new", {"difficulty": "Beginner"}).close()
        with self.assertRaises(urllib.error.HTTPError) as invalid_cell:
            self._request("/api/reveal", {"column": 9, "row": 0})
        self.assertEqual(invalid_cell.exception.code, 400)
        try:
            self.assertIn(
                "outside the board",
                json.loads(invalid_cell.exception.read())["error"],
            )
        finally:
            invalid_cell.exception.close()

    def test_browser_assets_are_served(self):
        for path, expected_type in (
            ("/app.css", "text/css"),
            ("/app.js", "text/javascript"),
        ):
            with self.subTest(path=path):
                with self._request(path) as response:
                    self.assertIn(expected_type, response.headers["Content-Type"])
                    self.assertGreater(len(response.read()), 0)

    def test_each_browser_session_has_its_own_game(self):
        other_browser = self._new_opener()
        self._request("/api/new", {"difficulty": "Expert"}).close()

        with self._request("/api/state") as response:
            first_state = json.loads(response.read())
        request = urllib.request.Request(self.base_url + "/api/state")
        with other_browser.open(request) as response:
            second_state = json.loads(response.read())

        self.assertEqual(first_state["phase"], "ready")
        self.assertEqual(first_state["difficulty"]["name"], "Expert")
        self.assertEqual(second_state["phase"], "choose")


if __name__ == "__main__":
    unittest.main()
