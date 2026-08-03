// MediMama frontend client.

const API_BASE = (window.MEDIMAMA_CONFIG?.apiBase ?? "").replace(/\/+$/, "");
const REQUEST_TIMEOUT_MS = 120000;

// Lower numbers mean higher urgency, so the colour scale runs from red to green.
const URGENCY_STYLES = {
  1: { className: "urgency-l1", label: "L1 — Immediate emergency" },
  2: { className: "urgency-l2", label: "L2 — Very urgent" },
  3: { className: "urgency-l3", label: "L3 — Urgent, same-day review" },
  4: { className: "urgency-l4", label: "L4 — Less urgent" },
  5: { className: "urgency-l5", label: "L5 — Self-care guidance" },
};

const els = {
  form: document.getElementById("askForm"),
  language: document.getElementById("language"),
  age: document.getElementById("age"),
  symptoms: document.getElementById("symptoms"),
  submitBtn: document.getElementById("submitBtn"),
  loading: document.getElementById("loading"),
  error: document.getElementById("error"),
  results: document.getElementById("results"),
  urgencyBox: document.getElementById("urgencyBox"),
  urgencyAdvice: document.getElementById("urgencyAdvice"),
  answerText: document.getElementById("answerText"),
  citationsBlock: document.getElementById("citationsBlock"),
  citationsList: document.getElementById("citationsList"),
};

const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

function applyDirection(language) {
  const rtl = language === "fa" || language === "ar";
  document.documentElement.dir = rtl ? "rtl" : "ltr";
  document.documentElement.lang = language;
}

els.language.addEventListener("change", () => applyDirection(els.language.value));

async function postQuestion(payload) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Skips the ngrok browser interstitial during Colab demos.
        "ngrok-skip-browser-warning": "true",
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await response.text().catch(() => "");
      throw new Error(`Request failed (${response.status}). ${detail}`.trim());
    }

    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

function renderUrgency(level) {
  const style = URGENCY_STYLES[level];
  els.urgencyBox.className = "urgency-box";

  if (!style) {
    els.urgencyBox.textContent = "Not clinically triaged";
    return;
  }

  els.urgencyBox.classList.add(style.className);
  els.urgencyBox.textContent = style.label;
}

function renderCitations(citations) {
  els.citationsList.replaceChildren();

  if (!Array.isArray(citations) || citations.length === 0) {
    hide(els.citationsBlock);
    return;
  }

  for (const citation of citations) {
    const item = document.createElement("li");

    const sourceLine = document.createElement("strong");
    sourceLine.textContent = citation.source || "Source";
    item.appendChild(sourceLine);

    if (citation.chunk) {
      const snippet = document.createElement("p");
      snippet.className = "citation-snippet";
      snippet.textContent = citation.chunk;
      item.appendChild(snippet);
    }

    els.citationsList.appendChild(item);
  }

  show(els.citationsBlock);
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const language = els.language.value;
  const age = Number.parseInt(els.age.value, 10);
  const symptoms = els.symptoms.value.trim();

  applyDirection(language);

  if (!Number.isInteger(age) || age < 0 || age > 216) {
    els.error.textContent = "Enter an age in months between 0 and 216.";
    show(els.error);
    return;
  }

  if (symptoms.length < 3) {
    els.error.textContent = "Describe the symptoms in a little more detail.";
    show(els.error);
    return;
  }

  els.submitBtn.disabled = true;
  hide(els.error);
  hide(els.results);
  show(els.loading);

  try {
    const data = await postQuestion({
      symptoms: symptoms,
      child_age_months: age,
      language: language,
    });

    renderUrgency(data.emergency_level);
    els.urgencyAdvice.textContent = data.see_doctor_urgency ?? "";
    els.answerText.textContent = data.answer ?? "No guidance was returned.";
    renderCitations(data.citations);
    show(els.results);
  } catch (err) {
    const aborted = err.name === "AbortError";
    els.error.textContent = aborted
      ? "The request timed out. The model may still be loading — try again shortly."
      : `Could not reach the MediMama API. ${err.message}`;
    show(els.error);
  } finally {
    els.submitBtn.disabled = false;
    hide(els.loading);
  }
});

applyDirection(els.language.value);