/* One-Shot Solitaire — Web UI */
"use strict";

// --- Constants ---
const CARD_W = 82;
const CARD_H = 122;
const CARD_OVERLAP = 28;

const SUIT_HTML = {
  "\u2660": "&spades;", "\u2665": "&hearts;",
  "\u2666": "&diams;",  "\u2663": "&clubs;"
};
const RED_SUITS = new Set(["\u2665", "\u2666"]);

// --- State ---
let gameId = null;
let gameState = null;
let autoFinishInterval = null;
let statusTimer = null;
// --- Drag state ---
let dragCards = [];
let dragEls = [];
let dragSource = null;
let dragOffsetX = 0;
let dragOffsetY = 0;
let isDragging = false;

// --- DOM refs ---
const stockEl = document.getElementById("stock");
const wasteEl = document.getElementById("waste");
const stockCount = document.getElementById("stock-count");
const wasteCount = document.getElementById("waste-count");
const foundationEls = document.querySelectorAll(".foundation-slot");
const storageEls = document.querySelectorAll(".storage-slot");
const foundationCounter = document.getElementById("foundation-counter");
const statusBar = document.getElementById("status-bar");
const overlay = document.getElementById("overlay");
const overlayTitle = document.getElementById("overlay-title");
const overlayBody = document.getElementById("overlay-body");
const overlayClose = document.getElementById("overlay-close");
const gameOverOverlay = document.getElementById("game-over-overlay");
const gameOverIcon = document.getElementById("game-over-icon");
const gameOverTitle = document.getElementById("game-over-title");
const gameOverText = document.getElementById("game-over-text");
const gameOverBtn = document.getElementById("game-over-btn");
const confettiCanvas = document.getElementById("confetti-canvas");
const confettiCtx = confettiCanvas.getContext("2d");

// --- API helpers ---
async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

// --- Game lifecycle ---
async function newGame(dealId) {
  stopAutoFinish();
  stopConfetti();
  hideGameOver();
  const body = dealId != null ? { game_id: dealId } : {};
  const data = await api("POST", "/api/new-game", body);
  gameId = data.game_id;
  gameState = data.state;
  render();
}

async function resetGame() {
  if (!gameId) return;
  stopAutoFinish();
  stopConfetti();
  hideGameOver();
  const data = await api("POST", `/api/reset/${gameId}`);
  gameState = data.state;
  render();
}

async function makeMove(movePayload) {
  if (!gameId) return;
  try {
    const data = await api("POST", `/api/move/${gameId}`, movePayload);
    gameState = data.state;
    render();
    if (!data.success) {
      showStatus(data.error || "Invalid move");
    } else {
      maybeAutoDraw();
    }
    checkGameEnd();
  } catch (e) {
    showStatus(e.message);
  }
}

function checkGameEnd() {
  if (!gameState) return;
  if (gameState.is_won) {
    showGameOver(true);
    startConfetti();
  } else if (gameState.is_over) {
    showGameOver(false);
  } else if (gameState.is_endgame) {
    startAutoFinish();
  }
}

// --- Card rendering ---
function createCardEl(card, opts = {}) {
  const el = document.createElement("div");
  el.className = "card";
  if (card.face_up) {
    const colorClass = RED_SUITS.has(card.suit) ? "red" : "black";
    el.classList.add("face-up", colorClass);
    const suitHtml = SUIT_HTML[card.suit] || card.suit;
    el.innerHTML =
      `<span class="card-corner top"><span class="card-val">${card.value}</span><span class="card-suit-small">${suitHtml}</span></span>` +
      `<span class="card-center">${suitHtml}</span>` +
      `<span class="card-corner bottom"><span class="card-val">${card.value}</span><span class="card-suit-small">${suitHtml}</span></span>`;
  } else {
    el.classList.add("face-down");
  }
  if (opts.style) Object.assign(el.style, opts.style);
  return el;
}

// --- Full render ---
function render() {
  if (!gameState) return;
  renderStock();
  renderWaste();
  renderFoundations();
  renderTableau();
  renderStorage();
  foundationCounter.textContent = `${gameState.foundation_count} / 52`;
}

function renderStock() {
  stockEl.querySelectorAll(".card").forEach(c => c.remove());
  const label = stockEl.querySelector(".slot-label");
  if (gameState.stock_count > 0) {
    const card = createCardEl({ face_up: false }, {
      style: { position: "absolute", top: "0", left: "0", cursor: "pointer", pointerEvents: "none" }
    });
    stockEl.appendChild(card);
    if (label) label.style.display = "none";
  } else {
    if (label) label.style.display = "";
  }
  setBadge(stockCount, gameState.stock_count);
}

function renderWaste() {
  wasteEl.querySelectorAll(".card").forEach(c => c.remove());
  const label = wasteEl.querySelector(".slot-label");
  if (gameState.waste_top) {
    const card = createCardEl(gameState.waste_top, {
      style: { position: "absolute", top: "0", left: "0" }
    });
    card.dataset.source = "waste";
    wasteEl.appendChild(card);
    if (label) label.style.display = "none";
  } else {
    if (label) label.style.display = "";
  }
  setBadge(wasteCount, gameState.waste_count > 1 ? gameState.waste_count : 0);
}

function renderFoundations() {
  foundationEls.forEach((slot, i) => {
    slot.querySelectorAll(".card").forEach(c => c.remove());
    const pile = gameState.foundations[i];
    const suitLabel = slot.querySelector(".suit-label");
    if (pile && pile.length > 0) {
      const top = pile[pile.length - 1];
      const card = createCardEl(top, {
        style: { position: "absolute", top: "0", left: "0" }
      });
      card.dataset.source = "foundation";
      card.dataset.foundationIdx = i;
      slot.appendChild(card);
      if (suitLabel) suitLabel.style.display = "none";
    } else {
      if (suitLabel) suitLabel.style.display = "";
    }
  });
}

function renderTableau() {
  const cols = document.querySelectorAll(".tableau-col");
  cols.forEach((col, colIdx) => {
    col.querySelectorAll(".card").forEach(c => c.remove());
    const pile = gameState.tableau[colIdx];
    col.classList.toggle("empty", !pile || pile.length === 0);
    if (!pile || pile.length === 0) return;
    pile.forEach((card, rowIdx) => {
      const el = createCardEl(card, {
        style: {
          position: "absolute",
          top: (rowIdx * CARD_OVERLAP) + "px",
          left: "0"
        }
      });
      el.style.zIndex = rowIdx;
      if (card.face_up) {
        el.dataset.source = "tableau";
        el.dataset.col = colIdx;
        el.dataset.cardIndex = rowIdx;
      }
      col.appendChild(el);
    });
  });
}

function renderStorage() {
  storageEls.forEach((slot, i) => {
    slot.querySelectorAll(".card").forEach(c => c.remove());
    const card = gameState.storage[i];
    const label = slot.querySelector(".slot-label");
    if (card) {
      const el = createCardEl(card, {
        style: { position: "absolute", top: "0", left: "0" }
      });
      el.dataset.source = "storage";
      el.dataset.slot = i;
      slot.appendChild(el);
      if (label) label.style.display = "none";
    } else {
      if (label) label.style.display = "";
    }
  });
}

function setBadge(el, count) {
  if (count > 0) {
    el.textContent = count;
    el.classList.add("visible");
  } else {
    el.classList.remove("visible");
  }
}

// --- Stock click ---
stockEl.addEventListener("click", () => {
  if (gameState && gameState.stock_count > 0) {
    makeMove({ type: "draw" });
  }
});

// --- Drag and Drop (pointer events) ---
document.addEventListener("pointerdown", onPointerDown);
document.addEventListener("pointermove", onPointerMove);
document.addEventListener("pointerup", onPointerUp);

function onPointerDown(e) {
  if (e.button !== 0) return;
  if (gameState && (gameState.is_won || gameState.is_over)) return;

  const cardEl = e.target.closest(".card.face-up");
  if (!cardEl) return;

  const source = cardEl.dataset.source;
  if (!source) return;

  e.preventDefault();

  if (source === "waste") {
    dragSource = { type: "waste" };
    dragCards = [gameState.waste_top];
    dragEls = [cardEl];
  } else if (source === "foundation") {
    const idx = parseInt(cardEl.dataset.foundationIdx);
    const pile = gameState.foundations[idx];
    const top = pile[pile.length - 1];
    dragSource = { type: "foundation", foundationIdx: idx };
    dragCards = [top];
    dragEls = [cardEl];
  } else if (source === "storage") {
    const slot = parseInt(cardEl.dataset.slot);
    dragSource = { type: "storage", slot };
    dragCards = [gameState.storage[slot]];
    dragEls = [cardEl];
  } else if (source === "tableau") {
    const col = parseInt(cardEl.dataset.col);
    const cardIndex = parseInt(cardEl.dataset.cardIndex);
    const pile = gameState.tableau[col];
    dragSource = { type: "tableau", col, cardIndex };
    dragCards = pile.slice(cardIndex);
    const colEl = cardEl.closest(".tableau-col");
    const allCards = colEl.querySelectorAll(".card");
    dragEls = [];
    allCards.forEach(el => {
      const idx = parseInt(el.dataset.cardIndex);
      if (!isNaN(idx) && idx >= cardIndex) {
        dragEls.push(el);
      }
    });
  }

  if (dragEls.length === 0) return;

  const rect = dragEls[0].getBoundingClientRect();
  dragOffsetX = e.clientX - rect.left;
  dragOffsetY = e.clientY - rect.top;
  isDragging = true;

  dragEls.forEach(el => el.classList.add("dragging"));
}

function onPointerMove(e) {
  if (!isDragging) return;
  e.preventDefault();

  const x = e.clientX - dragOffsetX;
  const y = e.clientY - dragOffsetY;

  dragEls.forEach((el, i) => {
    el.style.position = "fixed";
    el.style.left = x + "px";
    el.style.top = (y + i * CARD_OVERLAP) + "px";
    el.style.zIndex = 1000 + i;
  });
}

function onPointerUp(e) {
  if (!isDragging) return;
  isDragging = false;

  dragEls.forEach(el => el.classList.remove("dragging"));

  const dropTarget = findDropTarget(e.clientX, e.clientY);
  if (dropTarget) {
    executeDrop(dropTarget);
  } else {
    render();
  }

  dragCards = [];
  dragEls = [];
  dragSource = null;
}

function findDropTarget(x, y) {
  for (let i = 0; i < foundationEls.length; i++) {
    const rect = foundationEls[i].getBoundingClientRect();
    if (hitTest(x, y, rect)) return { type: "foundation", index: i };
  }

  const cols = document.querySelectorAll(".tableau-col");
  for (let i = 0; i < cols.length; i++) {
    const rect = cols[i].getBoundingClientRect();
    const pile = gameState.tableau[i];
    const colHeight = pile.length > 0 ? CARD_H + (pile.length - 1) * CARD_OVERLAP : CARD_H;
    const expanded = {
      left: rect.left, right: rect.left + CARD_W,
      top: rect.top, bottom: rect.top + colHeight + 20
    };
    if (x >= expanded.left && x <= expanded.right && y >= expanded.top && y <= expanded.bottom) {
      return { type: "tableau", col: i };
    }
  }

  for (let i = 0; i < storageEls.length; i++) {
    const rect = storageEls[i].getBoundingClientRect();
    if (hitTest(x, y, rect)) return { type: "storage", slot: i };
  }

  return null;
}

function hitTest(x, y, rect) {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

function executeDrop(target) {
  if (!dragSource || dragCards.length === 0) { render(); return; }
  const src = dragSource;

  if (target.type === "foundation") {
    if (dragCards.length > 1) { showStatus("Cannot move a stack to foundation"); render(); return; }
    if (src.type === "waste") makeMove({ type: "foundation" });
    else if (src.type === "storage") makeMove({ type: "move", src: ["storage", src.slot], dest: ["foundation", target.index] });
    else if (src.type === "tableau") makeMove({ type: "move", src: ["tableau", src.col], dest: ["foundation", target.index] });
  } else if (target.type === "tableau") {
    if (src.type === "waste") makeMove({ type: "tableau", col: target.col });
    else if (src.type === "foundation") makeMove({ type: "foundation_to_tableau", foundation_idx: src.foundationIdx, col: target.col });
    else if (src.type === "storage") makeMove({ type: "move", src: ["storage", src.slot], dest: ["tableau", target.col] });
    else if (src.type === "tableau") {
      if (src.col === target.col) { render(); return; }
      if (dragCards.length > 1) makeMove({ type: "stack_move", src_col: src.col, dest_col: target.col, count: dragCards.length });
      else makeMove({ type: "move", src: ["tableau", src.col], dest: ["tableau", target.col] });
    }
  } else if (target.type === "storage") {
    if (dragCards.length > 1) { showStatus("Cannot move a stack to storage"); render(); return; }
    if (src.type === "waste") makeMove({ type: "storage", slot: target.slot });
    else if (src.type === "tableau") makeMove({ type: "move", src: ["tableau", src.col], dest: ["storage", target.slot] });
    else if (src.type === "storage") makeMove({ type: "move", src: ["storage", src.slot], dest: ["storage", target.slot] });
  } else {
    render();
  }
}

// --- Auto-draw ---
function maybeAutoDraw() {
  if (!gameState) return;
  if (gameState.waste_count === 0 && gameState.stock_count > 0) {
    makeMove({ type: "draw" });
  }
}

// --- Auto-finish ---
function startAutoFinish() {
  if (autoFinishInterval) return;
  showStatus("Auto-finishing...");
  autoFinishInterval = setInterval(async () => {
    if (!gameId || !gameState) { stopAutoFinish(); return; }
    try {
      const data = await api("GET", `/api/hints/${gameId}`);
      const foundationHint = data.hints.find(h =>
        h.type === "foundation" ||
        (h.type === "move" && h.dest && h.dest[0] === "foundation")
      );
      if (foundationHint) {
        if (foundationHint.type === "foundation") await makeMove({ type: "foundation" });
        else await makeMove({ type: "move", src: foundationHint.src, dest: foundationHint.dest });
      } else {
        stopAutoFinish();
      }
    } catch {
      stopAutoFinish();
    }
  }, 200);
}

function stopAutoFinish() {
  if (autoFinishInterval) { clearInterval(autoFinishInterval); autoFinishInterval = null; }
}

// --- Status messages ---
function showStatus(msg) {
  statusBar.textContent = msg;
  statusBar.classList.add("visible");
  if (statusTimer) clearTimeout(statusTimer);
  statusTimer = setTimeout(() => statusBar.classList.remove("visible"), 2500);
}

// --- Game over ---
function showGameOver(won) {
  stopAutoFinish();
  gameOverOverlay.classList.remove("hidden");
  if (won) {
    gameOverIcon.textContent = "\u2728";
    gameOverTitle.textContent = "Victory";
    gameOverTitle.className = "won";
    gameOverText.textContent = "All 52 cards placed on foundations.";
  } else if (gameState.is_repetition_draw) {
    gameOverIcon.textContent = "\u2014";
    gameOverTitle.textContent = "Draw \u2014 Repetition";
    gameOverTitle.className = "lost";
    gameOverText.textContent = `The same position occurred three times. ${gameState.foundation_count} of 52 cards reached the foundations.`;
  } else {
    gameOverIcon.textContent = "\u2014";
    gameOverTitle.textContent = "No Moves Left";
    gameOverTitle.className = "lost";
    gameOverText.textContent = `${gameState.foundation_count} of 52 cards reached the foundations.`;
  }
}

function hideGameOver() { gameOverOverlay.classList.add("hidden"); }

gameOverBtn.addEventListener("click", () => newGame());

// --- Overlay (hints / rules) ---
overlayClose.addEventListener("click", () => overlay.classList.add("hidden"));
overlay.addEventListener("click", (e) => {
  if (e.target === overlay) overlay.classList.add("hidden");
});

document.getElementById("btn-hint").addEventListener("click", async () => {
  if (!gameId) return;
  const data = await api("GET", `/api/hints/${gameId}`);
  overlayTitle.textContent = "Possible Moves";
  if (data.hints.length === 0) {
    overlayBody.innerHTML = "<p>No legal moves available.</p>";
  } else {
    overlayBody.innerHTML = data.hints.map((h, i) =>
      `<div class="hint-item" data-hint-index="${i}">${h.description}</div>`
    ).join("");
    overlayBody.querySelectorAll(".hint-item").forEach((el, idx) => {
      el.addEventListener("click", () => {
        overlay.classList.add("hidden");
        executeHint(data.hints[idx]);
      });
    });
  }
  overlay.classList.remove("hidden");
});

function executeHint(hint) {
  if (hint.type === "draw") makeMove({ type: "draw" });
  else if (hint.type === "foundation") makeMove({ type: "foundation" });
  else if (hint.type === "tableau") makeMove({ type: "tableau", col: hint.col });
  else if (hint.type === "storage") makeMove({ type: "storage", slot: hint.slot });
  else if (hint.type === "move") makeMove({ type: "move", src: hint.src, dest: hint.dest });
}

document.getElementById("btn-rules").addEventListener("click", async () => {
  try {
    const res = await fetch("/rules");
    const text = await res.text();
    overlayTitle.textContent = "Rules";
    overlayBody.innerHTML = markdownToHtml(text);
    overlay.classList.remove("hidden");
  } catch {
    showStatus("Could not load rules");
  }
});

document.getElementById("btn-new").addEventListener("click", () => newGame());

// --- Simple markdown to HTML ---
function markdownToHtml(md) {
  const lines = md.split("\n");
  let html = "";
  let inList = false;
  let listType = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("#### ")) {
      if (inList) { html += listType === "ul" ? "</ul>" : "</ol>"; inList = false; }
      html += `<h3>${fmtInline(escHtml(trimmed.slice(5)))}</h3>`;
    } else if (trimmed.startsWith("### ")) {
      if (inList) { html += listType === "ul" ? "</ul>" : "</ol>"; inList = false; }
      html += `<h3>${fmtInline(escHtml(trimmed.slice(4)))}</h3>`;
    } else if (trimmed.startsWith("## ")) {
      if (inList) { html += listType === "ul" ? "</ul>" : "</ol>"; inList = false; }
      html += `<h2>${escHtml(trimmed.slice(3))}</h2>`;
    } else if (trimmed.startsWith("# ")) {
      if (inList) { html += listType === "ul" ? "</ul>" : "</ol>"; inList = false; }
      html += `<h1>${escHtml(trimmed.slice(2))}</h1>`;
    } else if (trimmed.startsWith("- ")) {
      if (!inList || listType !== "ul") {
        if (inList) html += listType === "ul" ? "</ul>" : "</ol>";
        html += "<ul>"; inList = true; listType = "ul";
      }
      html += `<li>${fmtInline(escHtml(trimmed.slice(2)))}</li>`;
    } else if (/^\d+\.\s/.test(trimmed)) {
      if (!inList || listType !== "ol") {
        if (inList) html += listType === "ul" ? "</ul>" : "</ol>";
        html += "<ol>"; inList = true; listType = "ol";
      }
      html += `<li>${fmtInline(escHtml(trimmed.replace(/^\d+\.\s/, "")))}</li>`;
    } else if (trimmed === "---") {
      if (inList) { html += listType === "ul" ? "</ul>" : "</ol>"; inList = false; }
      html += "<hr>";
    } else if (trimmed === "") {
      if (inList) { html += listType === "ul" ? "</ul>" : "</ol>"; inList = false; }
    } else {
      if (inList) { html += listType === "ul" ? "</ul>" : "</ol>"; inList = false; }
      html += `<p>${fmtInline(escHtml(trimmed))}</p>`;
    }
  }
  if (inList) html += listType === "ul" ? "</ul>" : "</ol>";
  return html;
}

function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtInline(s) {
  s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/\*(.+?)\*/g, "<em>$1</em>");
  return s;
}

// --- Keyboard shortcuts ---
document.addEventListener("keydown", (e) => {
  if (!overlay.classList.contains("hidden")) {
    if (e.key === "Escape") overlay.classList.add("hidden");
    return;
  }
  if (!gameOverOverlay.classList.contains("hidden")) {
    if (e.key === "r" || e.key === "R") newGame();
    return;
  }
  if (e.key === "d" || e.key === "D") {
    if (gameState && gameState.stock_count > 0) makeMove({ type: "draw" });
  } else if (e.key === "r" || e.key === "R") {
    resetGame();
  }
});

// --- Confetti ---
let confettiParticles = [];
let confettiAnimId = null;

function startConfetti() {
  confettiCanvas.width = window.innerWidth;
  confettiCanvas.height = window.innerHeight;
  confettiParticles = [];
  const colors = ["#c4a35a", "#dbb96e", "#faf6ef", "#a3231a", "#2a5f3a", "#e8d5a3"];
  for (let i = 0; i < 180; i++) {
    confettiParticles.push({
      x: Math.random() * confettiCanvas.width,
      y: Math.random() * -confettiCanvas.height,
      vx: (Math.random() - 0.5) * 2.5,
      vy: 1.5 + Math.random() * 3.5,
      size: 3 + Math.random() * 5,
      color: colors[Math.floor(Math.random() * colors.length)],
      rotation: Math.random() * 360,
      rotSpeed: (Math.random() - 0.5) * 8,
      life: 180 + Math.random() * 120
    });
  }
  if (!confettiAnimId) animateConfetti();
}

function stopConfetti() {
  confettiParticles = [];
  if (confettiAnimId) { cancelAnimationFrame(confettiAnimId); confettiAnimId = null; }
  confettiCtx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
}

function animateConfetti() {
  confettiCtx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
  confettiParticles = confettiParticles.filter(p => p.life > 0);
  if (confettiParticles.length === 0) { confettiAnimId = null; return; }
  for (const p of confettiParticles) {
    p.x += p.vx;
    p.y += p.vy;
    p.rotation += p.rotSpeed;
    p.life--;
    confettiCtx.save();
    confettiCtx.translate(p.x, p.y);
    confettiCtx.rotate(p.rotation * Math.PI / 180);
    confettiCtx.fillStyle = p.color;
    confettiCtx.globalAlpha = Math.min(1, p.life / 40);
    confettiCtx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.55);
    confettiCtx.restore();
  }
  confettiAnimId = requestAnimationFrame(animateConfetti);
}

// --- Init ---
newGame();
