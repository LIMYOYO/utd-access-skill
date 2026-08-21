import test from "node:test";
import assert from "node:assert/strict";

import {
  buildDoiUrl,
  buildLibKeyUrl,
  buildUofTSessionUrl,
  extractDoi
} from "../src/doi.js";

test("extracts a bare DOI", () => {
  assert.equal(extractDoi("10.1287/mnsc.2025.00819"), "10.1287/mnsc.2025.00819");
});

test("extracts a DOI from a publisher URL", () => {
  assert.equal(
    extractDoi("https://pubsonline.informs.org/doi/10.1287/mnsc.2025.00819"),
    "10.1287/mnsc.2025.00819"
  );
});

test("decodes an encoded DOI and trims sentence punctuation", () => {
  assert.equal(
    extractDoi("See https://doi.org/10.1287%2Fmnsc.2025.00819."),
    "10.1287/mnsc.2025.00819"
  );
});

test("preserves balanced parentheses in a DOI", () => {
  assert.equal(
    extractDoi("doi:10.1002/(sici)1099-0844(199912)17:4<290::aid-cbf849>3.0.co;2-p"),
    "10.1002/(sici)1099-0844(199912)17:4<290::aid-cbf849>3.0.co;2-p"
  );
});

test("returns null when no DOI exists", () => {
  assert.equal(extractDoi("Management Science article"), null);
});

test("builds LibKey and DOI resolver URLs", () => {
  assert.equal(
    buildLibKeyUrl("10.1287/mnsc.2025.00819"),
    "https://libkey.io/10.1287/mnsc.2025.00819"
  );
  assert.equal(
    buildDoiUrl("10.1287/mnsc.2025.00819"),
    "https://doi.org/10.1287/mnsc.2025.00819"
  );
});

test("builds a U of T OpenAthens session URL for Business Source Premier", () => {
  const url = new URL(buildUofTSessionUrl());
  assert.equal(url.hostname, "go.openathens.net");
  assert.equal(url.pathname, "/redirector/utoronto.ca");
  assert.match(url.searchParams.get("url"), /research\.ebsco\.com/);
  assert.match(url.searchParams.get("url"), /defaultdb=buh/);
});
