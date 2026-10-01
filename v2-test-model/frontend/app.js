const API_BASE = "http://127.0.0.1:5000";
const form = document.querySelector("#check-form");
const messageInput = document.querySelector("#message");
const count = document.querySelector("#char-count");
const submitButton = document.querySelector("#submit-button");
const clearButton = document.querySelector("#clear-button");
const sampleButton = document.querySelector("#sample-button");
const status = document.querySelector("#status");
const resultState = document.querySelector("#result-state");
const resultStateMessage = document.querySelector("#result-state-message");
const resultCard = document.querySelector("#result");
const buttonLabel = submitButton.querySelector(".button-label");
const resetStatsButton = document.querySelector("#reset-stats");
const sampleMessage = "URGENT: Your account will be suspended. Verify immediately at https://arnaz0n-login.example";
const STATS_KEY = "aegis-check-counts-v1";
let checkCounts = loadCheckCounts();

function loadCheckCounts() {
  const empty = { total: 0, low: 0, medium: 0, high: 0 };
  try {
    const saved = JSON.parse(localStorage.getItem(STATS_KEY) || "null");
    if (!saved || typeof saved !== "object") return empty;
    return Object.fromEntries(Object.keys(empty).map((key) => {
      const value = Number(saved[key]);
      return [key, Number.isSafeInteger(value) && value >= 0 ? value : 0];
    }));
  } catch {
    return empty;
  }
}

function renderCheckCounts() {
  document.querySelector("#stats-total").textContent = `${checkCounts.total} ${checkCounts.total === 1 ? "check" : "checks"}`;
  for (const level of ["low", "medium", "high"]) {
    document.querySelector(`#stats-${level}`).textContent = checkCounts[level];
  }
}

function recordCheck(level) {
  checkCounts.total += 1;
  checkCounts[level] += 1;
  try {
    localStorage.setItem(STATS_KEY, JSON.stringify(checkCounts));
  } catch {
    // Keep the in-memory count for this visit if browser storage is unavailable.
  }
  renderCheckCounts();
}

resetStatsButton.addEventListener("click", () => {
  if (!window.confirm("Reset the check counts saved in this browser? Pasted text is not stored.")) return;
  checkCounts = { total: 0, low: 0, medium: 0, high: 0 };
  try {
    localStorage.removeItem(STATS_KEY);
  } catch {
    // The visible counts are still reset for this visit.
  }
  renderCheckCounts();
});

function updateInputState() {
  count.textContent = `${messageInput.value.length} / 5000`;
  clearButton.disabled = messageInput.value.length === 0;
}

function setResultState(state, message) {
  resultState.dataset.state = state;
  resultStateMessage.textContent = message;
  resultState.hidden = false;
  resultState.setAttribute("role", state === "error" ? "alert" : "status");
  resultState.setAttribute("aria-live", state === "error" ? "assertive" : "polite");
  resultState.setAttribute("aria-busy", String(state === "loading"));
  if (state !== "empty") resultState.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showEmptyState() {
  setResultState("empty", "Your result will appear here after you run a check.");
}

function showResult(data) {
  const parsedScore = Number(data.risk_score);
  const score = Number.isFinite(parsedScore) ? Math.min(100, Math.max(0, parsedScore)) : 0;
  const level = String(data.risk_level || "low").toLowerCase();
  const allowedLevels = ["low", "medium", "high"];
  const safeLevel = allowedLevels.includes(level) ? level : "low";

  document.querySelector("#score-value").textContent = Number.isFinite(score) ? score : 0;
  const scoreColor = { low: "#7de0c0", medium: "#ffc46f", high: "#ff8991" }[safeLevel];
  document.querySelector("#score-ring").style.background =
    `conic-gradient(${scoreColor} ${score * 3.6}deg, rgba(125,224,192,.12) ${score * 3.6}deg)`;

  const levelBadge = document.querySelector("#result-level");
  levelBadge.textContent = `${safeLevel.toUpperCase()} RISK`;
  levelBadge.className = `risk-pill ${safeLevel === "low" ? "" : safeLevel}`;

  const signalsList = document.querySelector("#signals-list");
  signalsList.replaceChildren();
  const signals = Array.isArray(data.signals) ? data.signals : [];
  if (signals.length) {
    signals.forEach((signal) => {
      const item = document.createElement("li");
      item.textContent = String(signal);
      signalsList.append(item);
    });
  } else {
    const item = document.createElement("li");
    item.className = "no-signals";
    item.textContent = "No obvious warning signs were detected.";
    signalsList.append(item);
  }
  document.querySelector("#explanation").textContent = String(data.explanation || "No explanation was returned.");
  renderComponentScore("rule_warnings", data.component_scores?.rule_warnings, "#rule-score-value", "#rule-score-scope");
  renderComponentScore("url_phishing", data.component_scores?.url_phishing, "#url-score-value", "#url-score-scope");
  renderComponentScore("message_spam", data.component_scores?.message_spam, "#message-score-value", "#message-score-scope");
  const scoreNote = String(data.score_note || "Scores are separate experimental estimates, not calibrated probabilities. A low score does not prove a message is safe.");
  document.querySelector("#score-note").textContent = scoreNote;
  if (!/does not prove|not prove/i.test(scoreNote)) {
    document.querySelector("#score-note").append(document.createTextNode(" A low score does not prove a message is safe."));
  }
  resultCard.hidden = false;
  resultCard.setAttribute("aria-busy", "false");
  resultState.hidden = true;
  resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderComponentScore(key, component, valueSelector, scopeSelector) {
  const value = document.querySelector(valueSelector);
  const scope = document.querySelector(scopeSelector);
  if (key === "url_phishing" && (!component || component.score == null)) {
    value.textContent = "No URL detected · not applicable";
  } else if (component && typeof component.score === "number" && Number.isFinite(component.score)) {
    value.textContent = `${Math.min(100, Math.max(0, component.score))} / 100`;
  } else {
    value.textContent = "Not returned";
  }
  if (component && typeof component.scope === "string" && component.scope.trim()) {
    scope.textContent = component.scope;
  }
}

messageInput.addEventListener("input", () => {
  updateInputState();
  status.textContent = "";
  resultCard.hidden = true;
  showEmptyState();
});

sampleButton.addEventListener("click", () => {
  messageInput.value = sampleMessage;
  updateInputState();
  status.textContent = "";
  resultCard.hidden = true;
  showEmptyState();
  messageInput.focus();
});

clearButton.addEventListener("click", () => {
  messageInput.value = "";
  updateInputState();
  status.textContent = "";
  resultCard.hidden = true;
  showEmptyState();
  messageInput.focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = messageInput.value.trim();
  if (!text) {
    status.textContent = "Paste a message or link before starting the check.";
    messageInput.focus();
    return;
  }

  submitButton.disabled = true;
  messageInput.disabled = true;
  clearButton.disabled = true;
  sampleButton.disabled = true;
  buttonLabel.textContent = "Checking…";
  status.textContent = "";
  resultCard.hidden = true;
  resultCard.setAttribute("aria-busy", "true");
  setResultState("loading", "Checking message text locally…");

  try {
    const response = await fetch(`${API_BASE}/check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    let data;
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    if (!response.ok) {
      const details = [...new Set([data?.explanation, data?.error]
        .filter((value) => typeof value === "string" && value.trim())
        .map((value) => value.trim()))].join(" ");
      throw new Error(details || `The checker could not complete this request (error ${response.status}). Please try again.`);
    }
    if (!data || typeof data !== "object" || typeof data.risk_score !== "number" || typeof data.risk_level !== "string") {
      throw new Error("The checker returned an incomplete response. Please try again.");
    }
    status.textContent = "";
    const normalizedLevel = String(data.risk_level).toLowerCase();
    recordCheck(["low", "medium", "high"].includes(normalizedLevel) ? normalizedLevel : "low");
    showResult(data);
  } catch (error) {
    const message = error instanceof TypeError
      ? "Could not reach the checker. Make sure the backend is running at 127.0.0.1:5000."
      : error.message;
    setResultState("error", `${message} You can edit the text and try again.`);
  } finally {
    submitButton.disabled = false;
    messageInput.disabled = false;
    sampleButton.disabled = false;
    buttonLabel.textContent = "Analyze message";
    updateInputState();
    resultCard.setAttribute("aria-busy", "false");
  }
});

updateInputState();
renderCheckCounts();
