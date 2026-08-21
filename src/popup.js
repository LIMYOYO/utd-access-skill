import { buildLibKeyUrl, buildUofTSessionUrl, extractDoi } from "./doi.js";

const form = document.querySelector("#doi-form");
const input = document.querySelector("#doi-input");
const status = document.querySelector("#status");
const startSession = document.querySelector("#start-session");

function setStatus(message, isError = false) {
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function collectPageCandidates() {
  const selectors = [
    'meta[name="citation_doi"]',
    'meta[name="dc.identifier"]',
    'meta[name="dc.identifier.doi"]',
    'meta[name="prism.doi"]',
    'meta[property="og:url"]'
  ];
  const metaValues = selectors
    .map((selector) => document.querySelector(selector)?.content)
    .filter(Boolean);
  const doiLinks = [...document.querySelectorAll('a[href*="doi.org/10."]')]
    .slice(0, 10)
    .map((anchor) => anchor.href);

  return [window.location.href, ...metaValues, ...doiLinks];
}

async function detectDoi() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      setStatus("Paste a DOI to continue.");
      return;
    }

    const [{ result: candidates = [] }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: collectPageCandidates
    });
    const doi = candidates.map(extractDoi).find(Boolean);
    if (doi) {
      input.value = doi;
      setStatus("DOI detected from the current page.");
    } else {
      setStatus("No DOI detected. Paste one below.");
    }
  } catch {
    setStatus("This page cannot be inspected. Paste a DOI below.");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const doi = extractDoi(input.value);
  if (!doi) {
    setStatus("Enter a valid DOI, such as 10.1287/mnsc.2025.00819.", true);
    input.focus();
    return;
  }

  chrome.tabs.create({ url: buildLibKeyUrl(doi) });
  window.close();
});

startSession.addEventListener("click", () => {
  chrome.tabs.create({ url: buildUofTSessionUrl() });
  window.close();
});

input.addEventListener("input", () => {
  if (status.classList.contains("error")) {
    setStatus("Paste a DOI or keep typing.");
  }
});

detectDoi();
