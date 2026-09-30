const API_BASE = "http://127.0.0.1:5000";
const form = document.querySelector("#check-form");
const messageInput = document.querySelector("#message");
const count = document.querySelector("#char-count");
const submitButton = document.querySelector("#submit-button");
const clearButton = document.querySelector("#clear-button");
const sampleButton = document.querySelector("#sample-button");
const status = document.querySelector("#status");
const resultCard = document.querySelector("#result");
const modeButtons = [...document.querySelectorAll(".mode-button")];
const modeKicker = document.querySelector("#mode-kicker");
const modeHelp = document.querySelector("#mode-help");
const messageLabel = document.querySelector("#message-label");
const companySiteField = document.querySelector("#company-site-field");
const companyWebsiteInput = document.querySelector("#company-website");
const buttonLabel = submitButton.querySelector(".button-label");
const sourceResearch = document.querySelector("#source-research");
const sourceStatus = document.querySelector("#source-status");
const sourceList = document.querySelector("#source-list");
const resetStatsButton = document.querySelector("#reset-stats");
const sampleMessage = "URGENT: Your account will be suspended. Verify immediately at https://arnaz0n-login.example";
const sampleInternship = "Congratulations! You are guaranteed job placement after this internship. Pay a refundable registration fee of ₹2,500 within the next 2 hours to secure your position.";
const STATS_KEY = "aegis-check-counts-v1";
const modeCopy = {
  message: {
    endpoint: "/check",
    kicker: "MESSAGE CHECK",
    label: "Suspicious message or URL",
    placeholder: "Paste a suspicious message or link here…",
    help: "Look for suspicious language and URL patterns in a message or link.",
    sample: sampleMessage,
    sampleButton: "Try a message sample",
    submit: "Analyze message",
    pending: "Checking message text locally…",
  },
  internship: {
    endpoint: "/check/internship",
    kicker: "INTERNSHIP OFFER CHECK",
    label: "Internship offer text",
    placeholder: "Paste the internship offer text here…",
    help: "Checks the pasted offer text for selected warning signs. It does not verify the employer or search public sources.",
    sample: sampleInternship,
    sampleButton: "Try an offer sample",
    submit: "Analyze offer",
    pending: "Checking offer text locally…",
  },
};
let activeMode = "message";
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

function setMode(mode) {
  activeMode = mode;
  const copy = modeCopy[mode];
  modeButtons.forEach((button) => {
    const selected = button.dataset.mode === mode;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  modeKicker.textContent = copy.kicker;
  messageLabel.textContent = copy.label;
  messageInput.placeholder = copy.placeholder;
  modeHelp.textContent = copy.help;
  companySiteField.hidden = mode !== "internship";
  sampleButton.innerHTML = `${copy.sampleButton} <span aria-hidden="true">↗</span>`;
  buttonLabel.textContent = copy.submit;
  status.textContent = "";
  resultCard.hidden = true;
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
  renderSourceResearch(data, activeMode);
  resultCard.hidden = false;
  resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderSourceResearch(data, mode) {
  sourceResearch.hidden = mode !== "internship";
  sourceList.replaceChildren();
  if (mode !== "internship") return;

  const sources = Array.isArray(data.sources) ? data.sources : [];
  if (sources.length === 0) {
    sourceStatus.textContent = "Source research is not connected. This check has not searched official pages, reviews, or forums.";
    return;
  }

  sourceStatus.textContent = "Sources are references to review, not proof that an offer is genuine or fraudulent.";
  sources.forEach((source) => {
    if (!source || typeof source !== "object") return;
    const item = document.createElement("li");
    const href = String(source.url || source.link || source.source_url || "");
    const kind = [source.type, source.category, source.source_type, source.kind, href].join(" ").toLowerCase();
    const isUserReport = /reddit|review|forum|user.?report/.test(kind);
    const label = document.createElement("span");
    label.className = "source-kind";
    label.textContent = isUserReport ? "User report · anecdotal" : kind.includes("official") ? "Official source" : "Source";
    item.append(label);

    const title = String(source.title || "Untitled source");
    if (/^https?:\/\//i.test(href)) {
      const link = document.createElement("a");
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = title;
      item.append(link);
    } else {
      const titleText = document.createElement("span");
      titleText.textContent = title;
      item.append(titleText);
    }
    const date = document.createElement("time");
    date.textContent = String(source.date || source.published_date || source.published_at || "Date not provided");
    item.append(date);
    sourceList.append(item);
  });
}

messageInput.addEventListener("input", () => {
  updateInputState();
  status.textContent = "";
});

modeButtons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

sampleButton.addEventListener("click", () => {
  messageInput.value = modeCopy[activeMode].sample;
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

  const companyWebsite = activeMode === "internship" ? companyWebsiteInput.value.trim() : "";
  if (companyWebsite) {
    try {
      const parsedWebsite = new URL(companyWebsite);
      if (!["http:", "https:"].includes(parsedWebsite.protocol)) throw new Error("Use an http or https company website URL.");
    } catch {
      status.textContent = "Enter a valid company website URL beginning with http:// or https://.";
      companyWebsiteInput.focus();
      return;
    }
  }

  submitButton.disabled = true;
  modeButtons.forEach((button) => { button.disabled = true; });
  buttonLabel.textContent = "Checking…";
  status.textContent = modeCopy[activeMode].pending;

  try {
    const response = await fetch(`${API_BASE}${modeCopy[activeMode].endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: activeMode === "internship" && companyWebsiteInput.value.trim()
          ? `${text}\n\nCompany website: ${companyWebsite}`
          : text,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.explanation || `The checker returned an error (${response.status}).`);
    }
    if (typeof data.risk_score !== "number" || typeof data.risk_level !== "string") {
      throw new Error("The checker returned a response Aegis could not understand.");
    }
    status.textContent = "";
    const normalizedLevel = String(data.risk_level).toLowerCase();
    recordCheck(["low", "medium", "high"].includes(normalizedLevel) ? normalizedLevel : "low");
    showResult(data);
  } catch (error) {
    status.textContent = error instanceof TypeError
      ? "Could not reach the checker. Make sure the backend is running at 127.0.0.1:5000."
      : error.message;
  } finally {
    submitButton.disabled = false;
    modeButtons.forEach((button) => { button.disabled = false; });
    buttonLabel.textContent = modeCopy[activeMode].submit;
  }
});

updateInputState();
renderCheckCounts();
