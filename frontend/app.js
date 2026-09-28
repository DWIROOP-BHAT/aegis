const API_URL = "http://127.0.0.1:5000/check";
const form = document.querySelector("#check-form");
const messageInput = document.querySelector("#message");
const count = document.querySelector("#char-count");
const submitButton = document.querySelector("#submit-button");
const clearButton = document.querySelector("#clear-button");
const sampleButton = document.querySelector("#sample-button");
const status = document.querySelector("#status");
const resultCard = document.querySelector("#result");
const sampleMessage = "URGENT: Your account will be suspended. Verify immediately at https://arnaz0n-login.example";

function updateInputState() {
  count.textContent = `${messageInput.value.length} / 5000`;
  clearButton.disabled = messageInput.value.length === 0;
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
  resultCard.hidden = false;
  resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

messageInput.addEventListener("input", () => {
  updateInputState();
  status.textContent = "";
});

sampleButton.addEventListener("click", () => {
  messageInput.value = sampleMessage;
  updateInputState();
  status.textContent = "";
  messageInput.focus();
});

clearButton.addEventListener("click", () => {
  messageInput.value = "";
  updateInputState();
  status.textContent = "";
  resultCard.hidden = true;
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
  submitButton.querySelector(".button-label").textContent = "Checking…";
  status.textContent = "Sending your message for analysis…";

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.explanation || `The checker returned an error (${response.status}).`);
    }
    if (typeof data.risk_score !== "number" || typeof data.risk_level !== "string") {
      throw new Error("The checker returned a response Aegis could not understand.");
    }
    status.textContent = "";
    showResult(data);
  } catch (error) {
    status.textContent = error instanceof TypeError
      ? "Could not reach the checker. Make sure the backend is running at 127.0.0.1:5000."
      : error.message;
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector(".button-label").textContent = "Analyze message";
  }
});

updateInputState();
