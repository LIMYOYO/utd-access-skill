const DOI_PATTERN = /10\.\d{4,9}\/[\-._;()/:<>A-Z0-9]+/i;

function safelyDecode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function trimTrailingPunctuation(value) {
  let result = value.replace(/[.,;:!?"'`]+$/g, "");
  const pairs = [
    ["(", ")"],
    ["[", "]"],
    ["{", "}"],
    ["<", ">"]
  ];

  for (const [open, close] of pairs) {
    const openCount = [...result].filter((character) => character === open).length;
    let closeCount = [...result].filter((character) => character === close).length;
    while (result.endsWith(close) && closeCount > openCount) {
      result = result.slice(0, -1);
      closeCount -= 1;
    }
  }

  return result;
}

export function extractDoi(value) {
  if (typeof value !== "string" || value.trim() === "") {
    return null;
  }

  const decoded = safelyDecode(value.trim());
  const match = decoded.match(DOI_PATTERN);
  if (!match) {
    return null;
  }

  return trimTrailingPunctuation(match[0]).toLowerCase();
}

export function encodeDoiPath(doi) {
  return doi.split("/").map((part) => encodeURIComponent(part)).join("/");
}

export function buildLibKeyUrl(value) {
  const doi = extractDoi(value);
  if (!doi) {
    throw new Error("A valid DOI is required.");
  }
  return `https://libkey.io/${encodeDoiPath(doi)}`;
}

export function buildDoiUrl(value) {
  const doi = extractDoi(value);
  if (!doi) {
    throw new Error("A valid DOI is required.");
  }
  return `https://doi.org/${encodeDoiPath(doi)}`;
}

export function buildUofTSessionUrl() {
  const businessSourcePremier =
    "https://research.ebsco.com/c/gsemyh/search/advanced/filters?autocorrect=y&defaultdb=buh";
  const redirector = "https://go.openathens.net/redirector/utoronto.ca?url=";
  return `${redirector}${encodeURIComponent(businessSourcePremier)}`;
}
