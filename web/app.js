"use strict";

const chooser = document.querySelector("#chooser");
const gameView = document.querySelector("#game");
const difficultyList = document.querySelector("#difficulty-list");
const chooserStatus = document.querySelector("#chooser-status");
const boardElement = document.querySelector("#board");
const mineCount = document.querySelector("#mine-count");
const timeCount = document.querySelector("#time-count");
const statusElement = document.querySelector("#status");
const difficultyName = document.querySelector("#difficulty-name");

let currentState = null;
let elapsedSeconds = 0;
let timerStartedAt = null;

async function request(path, payload) {
  const response = await fetch(path, {
    method: payload ? "POST" : "GET",
    headers: payload ? { "Content-Type": "application/json" } : {},
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error || `Request failed (${response.status}).`);
  }
  return result;
}

function showError(error) {
  if (!currentState || currentState.phase === "choose") {
    chooser.hidden = false;
    gameView.hidden = true;
    chooserStatus.hidden = false;
    chooserStatus.textContent = error.message;
    return;
  }
  statusElement.textContent = error.message;
  statusElement.dataset.state = "lost";
}

async function loadState() {
  try {
    render(await request("/api/state"));
  } catch (error) {
    showError(error);
  }
}

async function startGame(name) {
  try {
    render(await request("/api/new", { difficulty: name }));
  } catch (error) {
    showError(error);
  }
}

async function showDifficultyMenu() {
  try {
    render(await request("/api/menu", {}));
  } catch (error) {
    showError(error);
  }
}

async function performAction(action, column, row) {
  try {
    render(await request(`/api/${action}`, { column, row }));
  } catch (error) {
    showError(error);
  }
}

function render(state) {
  currentState = state;
  chooser.hidden = state.phase !== "choose";
  gameView.hidden = state.phase === "choose";
  if (state.phase === "choose") {
    chooserStatus.hidden = true;
    renderDifficulties(state.difficulties);
    return;
  }

  difficultyName.textContent = state.difficulty.name.toUpperCase();
  mineCount.textContent = String(state.remaining_mines).padStart(3, "0");
  elapsedSeconds = state.elapsed_seconds;
  timerStartedAt = state.phase === "playing" ? Date.now() : null;
  updateTimer();
  renderBoard(state);
  statusElement.dataset.state = state.phase;
  if (state.phase === "ready") {
    statusElement.textContent = "Click any square to start. Your first click is safe.";
  } else if (state.phase === "won") {
    statusElement.textContent = "Field cleared. Nicely done.";
  } else if (state.phase === "lost") {
    statusElement.textContent = "Mine hit. Try another round.";
  } else {
    statusElement.textContent = "Find the mines. Clear every safe square.";
  }
}

function renderDifficulties(difficulties) {
  difficultyList.replaceChildren();
  for (const difficulty of difficulties) {
    const button = document.createElement("button");
    button.className = "difficulty-card";
    button.type = "button";
    const name = document.createElement("strong");
    name.textContent = difficulty.name;
    const size = document.createElement("span");
    size.className = "difficulty-size";
    size.textContent = `${difficulty.columns} × ${difficulty.rows}`;
    const mines = document.createElement("span");
    mines.className = "difficulty-mines";
    mines.textContent = `${difficulty.mine_count} mines`;
    button.append(name, size, mines);
    button.addEventListener("click", () => startGame(difficulty.name));
    difficultyList.append(button);
  }
}

function renderBoard(state) {
  const { columns, rows } = state.difficulty;
  boardElement.replaceChildren();
  boardElement.style.setProperty("--columns", columns);
  boardElement.setAttribute("aria-rowcount", rows);
  boardElement.setAttribute("aria-colcount", columns);
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const data = state.board[row][column];
      const cell = document.createElement("button");
      cell.className = "cell";
      cell.type = "button";
      cell.setAttribute("role", "gridcell");
      cell.dataset.column = column;
      cell.dataset.row = row;
      cell.setAttribute("aria-label", cellLabel(data, column, row));
      if (data.flagged) {
        cell.classList.add("flagged");
        cell.textContent = "⚑";
      } else if (data.revealed) {
        cell.classList.add("revealed");
        if (data.adjacent > 0) {
          cell.classList.add(`number-${data.adjacent}`);
          cell.textContent = String(data.adjacent);
        }
      } else if (data.mine) {
        cell.classList.add("mine");
        if (data.exploded) cell.classList.add("exploded");
        cell.textContent = "✹";
      }
      if (state.phase === "won" || state.phase === "lost") {
        cell.disabled = true;
      }
      cell.addEventListener("click", () => performAction("reveal", column, row));
      cell.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        performAction("flag", column, row);
      });
      boardElement.append(cell);
    }
  }
}

function cellLabel(data, column, row) {
  if (data.flagged) return `Flagged square, column ${column + 1}, row ${row + 1}`;
  if (data.mine) return `Mine, column ${column + 1}, row ${row + 1}`;
  if (data.revealed && data.adjacent) {
    return `${data.adjacent} neighboring mines, column ${column + 1}, row ${row + 1}`;
  }
  if (data.revealed) return `Empty square, column ${column + 1}, row ${row + 1}`;
  return `Covered square, column ${column + 1}, row ${row + 1}`;
}

function updateTimer() {
  const time = timerStartedAt === null
    ? elapsedSeconds
    : elapsedSeconds + Math.floor((Date.now() - timerStartedAt) / 1000);
  timeCount.textContent = String(Math.min(time, 999)).padStart(3, "0");
}

document.querySelector("#change-difficulty").addEventListener("click", showDifficultyMenu);
document.querySelector("#restart").addEventListener("click", () => {
  if (currentState?.difficulty) startGame(currentState.difficulty.name);
});
window.setInterval(updateTimer, 1000);
loadState();
