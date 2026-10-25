"use strict";

// Everything that comes from the server is put on the page as text (textContent), never as
// HTML: the quotes are law text from a wiki that anyone can edit.

const form = document.getElementById("ask-form");
const input = document.getElementById("question");
const submit = document.getElementById("submit");
const statusLine = document.getElementById("status");
const result = document.getElementById("result");

const STATUS_LABELS = {
  answered: "נענתה",
  refused_low_score: "נדחתה: לא נמצא סעיף קרוב מספיק",
  refused_by_model: "נדחתה: המקורות שנמצאו לא עונים על השאלה",
  rejected_invalid_citations: "נפסלה: ציטוט לא תקין",
  rejected_no_citations: "נפסלה: תשובה בלי מקור",
};

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  }
  node.append(...children);
  return node;
}

// A link is made only for an https address.
function link(url, label) {
  if (typeof url !== "string" || !url.startsWith("https://")) return null;
  return el("a", { href: url, target: "_blank", rel: "noopener noreferrer", text: label });
}

// The answer with its [1] markers turned into links to the cards.
const CITATION = /\[(\d+(?:\s*[,،]\s*\d+)*)\]/g;
function answerNodes(text) {
  const nodes = [];
  let last = 0;
  for (const match of text.matchAll(CITATION)) {
    nodes.push(text.slice(last, match.index));
    for (const number of match[1].split(/[,،]/).map((part) => part.trim())) {
      nodes.push(el("a", { class: "cite", href: "#card-" + number, text: "[" + number + "]" }));
    }
    last = match.index + match[0].length;
  }
  nodes.push(text.slice(last));
  return nodes;
}

function card(citation) {
  const c = citation.card;
  const root = el("article", { class: "card", id: "card-" + citation.number });
  root.append(el("h3", { text: "[" + citation.number + "] " + c.law + " | סעיף " + c.section }));
  root.append(el("blockquote", { text: c.quote }));
  if (c.text_as_of) root.append(el("p", { class: "meta", text: "נוסח נכון לתאריך " + c.text_as_of }));
  if (c.currency_warning) root.append(el("p", { class: "warn", text: c.currency_warning }));
  const links = el("div", { class: "links" });
  for (const item of [
    link(c.knesset_url, "עמוד החוק באתר הכנסת"),
    link(c.wikisource_url, "הנוסח בספר החוקים הפתוח"),
    c.last_amendment_url ? link(c.last_amendment_url, "התיקון האחרון ברשומות") : null,
  ]) {
    if (item) links.append(item);
  }
  root.append(links);
  root.append(el("p", { class: "meta", text: c.search_hint }));
  return root;
}

function technical(data) {
  const details = el("details", { class: "tech" });
  details.append(el("summary", { text: "פרטים טכניים" }));
  const lines = [
    "מצב: " + (STATUS_LABELS[data.status] || data.status),
    "מודל: " + (data.model || "לא נקרא מודל"),
    "זמן: " + data.seconds.toFixed(1) + " שניות",
    "טוקנים: " + data.input_tokens + " קלט, " + data.output_tokens + " פלט",
  ];
  for (const line of lines) details.append(el("p", { text: line }));
  return details;
}

function show(data) {
  result.replaceChildren();
  if (data.status === "answered") {
    result.append(el("div", { class: "answer" }, ...answerNodes(data.answer)));
    result.append(el("h2", { text: "המקורות, לבדיקה שלכם" }));
    for (const citation of data.citations) result.append(card(citation));
  } else {
    result.append(el("div", { class: "refusal", text: data.answer }));
  }
  result.append(el("p", { class: "disclaimer", text: data.disclaimer }));
  result.append(technical(data));
}

function showError(message) {
  result.replaceChildren(el("div", { class: "error", role: "alert", text: message }));
}

async function ask(question) {
  submit.disabled = true;
  statusLine.textContent = "מחפשים בחוקים וכותבים תשובה…";
  result.replaceChildren();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });
    if (response.status === 422) {
      showError("השאלה ריקה או ארוכה מדי. אפשר עד אלף תווים.");
    } else if (!response.ok) {
      showError("השירות עמוס או לא זמין כרגע. נסו שוב בעוד רגע.");
    } else {
      show(await response.json());
    }
  } catch (error) {
    showError(
      error.name === "AbortError"
        ? "התשובה מתעכבת יותר מדי. נסו שוב."
        : "אין חיבור לשרת. בדקו את החיבור ונסו שוב."
    );
  } finally {
    clearTimeout(timer);
    submit.disabled = false;
    statusLine.textContent = "";
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (question) ask(question);
});

for (const chip of document.querySelectorAll(".chip")) {
  chip.addEventListener("click", () => {
    input.value = chip.textContent;
    ask(chip.textContent);
  });
}

// The list of laws, with how current each text is.
async function loadLaws() {
  const list = document.getElementById("laws");
  try {
    const response = await fetch("/laws");
    if (!response.ok) return;
    for (const law of await response.json()) {
      const current = law.currency_status === "ok";
      const item = el("li");
      const title = el("div", { text: law.name });
      title.append(
        el("span", {
          class: "badge " + (current ? "ok" : "attention"),
          text: current ? "הנוסח מעודכן" : "כדאי לוודא את הנוסח",
        })
      );
      item.append(title);
      const parts = [];
      if (law.last_amendment) parts.push("התיקון האחרון בנוסח: " + law.last_amendment);
      if (law.text_as_of) parts.push("נוסח נכון לתאריך " + law.text_as_of);
      if (parts.length) item.append(el("p", { class: "meta", text: parts.join(" | ") }));
      if (law.currency_warning) item.append(el("p", { class: "meta", text: law.currency_warning }));
      const links = el("div", { class: "links" });
      for (const anchor of [link(law.knesset_url, "באתר הכנסת"), link(law.wikisource_url, "בספר החוקים הפתוח")]) {
        if (anchor) links.append(anchor);
      }
      item.append(links);
      list.append(item);
    }
  } catch (error) {
    // The list is a convenience: the page works without it.
  }
}

loadLaws();

// A link such as /?q=... fills in the question and asks it. The text only goes into the box
// and to /ask: it is never put on the page as HTML.
const prefilled = new URLSearchParams(window.location.search).get("q");
if (prefilled && prefilled.trim()) {
  input.value = prefilled.trim().slice(0, 1000);
  ask(input.value);
}
