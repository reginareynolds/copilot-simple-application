# Minesweeper

A classic single-player Minesweeper game written in Python, with a browser-based
interface. Choose Beginner, Intermediate, or Expert before the board is
generated. The game includes first-click safety, flags, an elapsed-time display,
a remaining-mine counter, automatic revealing of empty areas, and win/loss
feedback.

## Run in Codespaces

Start the local web server:

```bash
python3 minesweeper.py
```

In VS Code, open the **Ports** tab, forward port **8000** if it is not already
forwarded, and open the forwarded address in a browser. The server listens on
all interfaces so the forwarded port can reach it.

The server uses only Python's standard library; there are no packages to
install. To use a different port, set the `PORT` environment variable before
starting it, then forward that port instead.

Left-click a covered square to reveal it. Right-click to toggle a flag. Use
**Restart** to replay the selected difficulty or **Change difficulty** to go
back to the selection screen.

## Tests

Run the game-rule and web-server tests with Python's standard test runner:

```bash
python3 -m unittest discover -s tests -v
```
