# Access feasibility audit

Checked September 25–26, 2026, America/Toronto. This is a planning audit, not an institution-authenticated coverage benchmark. No credentials, institutional cookies, or subscription full texts were collected. One publicly served repository PDF was downloaded to a temporary local file for a bounded access check; the PDF is not part of this repository.

## Journal scope and catalogue evidence

`journal-scope.csv` contains 155 candidate titles: 31 OM/supply-chain/transport, 29 OR/optimization/probability, 26 management/IS/marketing, 55 economics, and 14 finance/statistics/ML. Historical titles are retained explicitly. Each row records observed ISSNs, an identity source, the source's title and publisher/host label, and a per-product coverage classification. These are research scope choices, not a journal ranking or an exhaustive definition of OM.

`ebsco-coverage.csv` retains 408 matching rows from three official product lists, including separate historical coverage intervals where present. Joining used observed ISSNs after title disambiguation. In particular, the POMS journal is ISSN 1059-1478, not the distinct 2251-6409 title; Journal of Management uses 0149-2063, not the unrelated 0255-9838 title. Optimization was resolved separately to avoid matching Optimization: Journal of Research in Management. Blank full-text fields were not filled from indexing dates.

An ISSN checksum check caught an extra invalid value (`0340-4384`) in Crossref's Queueing Systems record. The [publisher journal page](https://link.springer.com/journal/11134) confirmed `0257-0130` and `1572-9443`; only those are retained in the catalogue. The rejected observation is recorded in `journal-identities.json`. All retained ISSNs pass checksum validation. This correction did not alter the EBSCO matched rows.

| Journal | Premier | Complete | Ultimate |
| --- | --- | --- | --- |
| Management Science | Full text from 1998; delay blank | Same | Full text from 1954; delay blank |
| M&SOM | Full text from 1999; delay blank | Same | Same |
| Operations Research | Full text from 1998; delay blank | Same | Full text from 1956; delay blank |
| POM | Indexed; no full text listed | Same | Full text from 2006-04-08; 12 months |
| Journal of Operations Management | Indexed; no full text listed | Same | Full text from 2001; 12 months |
| American Economic Review | Full text from 1911; 24 months | Same | Same |
| Quarterly Journal of Economics | Indexed; no full text listed | Same | Full text from 1996; 12 months |
| Journal of Political Economy | Indexed; no full text listed | Same | Full text from 1965; 12 months |
| Econometrica | Indexed; no full text listed | Same | Same |
| European Journal of Operational Research | Indexed; no full text listed | Same | Same |

Sources: official [Premier](https://about.ebsco.com/m/ee/Marketing/titleLists/buh-journals.htm), [Complete](https://about.ebsco.com/m/ee/Marketing/titleLists/bth-journals.htm), and [Ultimate](https://about.ebsco.com/m/ee/Marketing/titleLists/bsu-journals.htm) journal lists. All three returned HTTP 200. `catalogue-provenance.json` records document hashes, sizes, retrieval context and row counts. The source files themselves are not redistributed here.

Interpretation: `full_text_no_delay_listed` means a full-text start exists and no stop/delay is listed; it does not promise immediate publication availability. `full_text_embargo` preserves the listed delay, not a computed article eligibility date. `indexed_no_full_text_listed` is not proof that the institution lacks a separately licensed publisher copy. `not_found_by_observed_issn` means no matching row in these three products, not absence from all EBSCO products. Coverage can differ by contract, region, date and article. The source cautions that coverage dates are intended and may differ from the product; its publication/update date was not exposed.

## Live probes

Small, anonymous HTTP requests used the User-Agent `PaperAccessRouter-Feasibility/0.1`; no authentication bypass or repeated challenge-solving was attempted. JSON files preserve the selected metadata responses and access outcomes. Timing is a one-request observation, not a throughput benchmark.

| Probe | Observation | What it establishes |
| --- | --- | --- |
| Crossref + OpenAlex for `10.1287/mnsc.2025.00819` | Both 200; OpenAlex reports closed, no cached PDF/XML | Identity resolved; no OA route found by this lookup |
| Crossref + OpenAlex for `10.1287/mnsc.2023.00320` | Both 200; OpenAlex reports closed, no cached content; publisher PDF request 403 | Previous “OA example” claim is unverified; neither metadata nor a 403 establishes definitive paywall status |
| SSRN `10.2139/ssrn.4189586` | Metadata 200; OpenAlex reports green, no direct PDF/cached content; SSRN landing request 403 | An OA label is insufficient for unattended download; no conclusion about authenticated browser access |
| LibKey for `10.1287/mnsc.2025.00819` | 200, `text/html`, 5,580 bytes | Router page reachable; no full text acquired |
| OpenAlex M&SOM query, `has_content.pdf:true` | 200; query reported 162 matches and returned 3 sample records | A discovery sample, not a journal coverage rate; query did not measure total journal output or all versions |
| Repository copy of `10.1287/msom.5.2.79.16071` | 200, PDF, 2,230,333 bytes, 12.00 seconds | Actual publicly served manuscript obtained |
| OpenAlex content for the same work, without key | 401 | Keyless content download not available in this probe; keyed mode not tested |
| Econ `10.1257/jep.33.3.3` | OpenAlex 200, published OA location, no cached content; AEA page offers complimentary PDF; web tool PDF fetch returned 403 | Official reading route identified, programmatic PDF acquisition unproven |

The repository PDF is *Telephone Call Centers: Tutorial, Review, and Research Prospects*, by Noah Gans, Ger Koole and Avishai Mandelbaum. OpenAlex labels the location `submittedVersion`; the first page is dated March 17, 2003. `pdfinfo` parsed 84 unencrypted pages; first-page `pdftotext` output matched the title and authors. PDF header and EOF markers were present. SHA-256: `f072da286c0dae17d46d1e01b8f08ee01495753289d5817e6adc12e6fee9eec8`. This checks one manuscript's identity/container, not completeness of every formula or page. Metadata supplied no explicit reuse licence, so the probe does not establish redistribution or AI-processing rights.

The economics example is Susanto Basu's *Are Price-Cost Markups Rising in the United States? A Discussion of the Evidence*, JEP 33(3), pp. 3–22. Its [official article page](https://www.aeaweb.org/articles?id=10.1257/jep.33.3.3) identifies the complimentary PDF. The 403 was from the web retrieval tool, distinct from the local Python probes.

The local raw observations are in `metadata-probes.json`, `access-probes.json`, `oa-discovery-sample.json` and `econ-discovery-sample.json`. Journal identity discovery also encountered five Crossref 429 responses during a short two-worker lookup; those responses were not journal absence. Remaining identities were checked through OpenAlex or a later exact Crossref journal request. This motivates host-level backoff even for metadata discovery. These ad hoc probes are not a reusable downloader or load test.

## Source capability register

All entries below are based on official provider/publisher documentation, except where explicitly marked unverified. Documentation-level support is not a successful live integration.

| Source | Evidence / consequence |
| --- | --- |
| INFORMS | [2026 subscription FAQ](https://www.informs.org/Publications/Journal-Subscriptions/FAQs) describes the institutional move to Business Source and separate historical archive arrangements. The [journal catalogue](https://www.informs.org/Publications/INFORMS-Journals) lists 17 journals, including open-access titles. Do not interpret the institutional migration as eliminating all OA or individual access. |
| EBSCO EDS | [Working with full text](https://developer.ebsco.com/eds-api/docs/working-with-full-text): search supplies availability indicators; retrieve supplies HTML or expiring PDF URLs. [Application credentials](https://developer.ebsco.com/home/docs/request-application-credentials) describes EDS credentials, which are not an individual university SSO password. No institutional credentials tested. |
| EBSCO usage | [Standard agreement I.3](https://legal.ebsco.com/license-agreement) limits systematic collection and contains an AI/ML restriction. Institution-specific terms may differ. Link resolving, permitted reading downloads, corpus building and AI processing must remain distinct capabilities. No claim about the user's actual institutional contract is made. |
| LibKey | [Integration](https://thirdiron.com/libkey-integration/) and [API documentation overview](https://thirdiron.atlassian.net/wiki/spaces/BrowZineAPIDocs/overview?homepageId=66322460) support a DOI-to-institution-access integration; developer API keys are requested from Third Iron. Public link routing remains a fallback. API access does not grant publisher downloading rights. |
| OpenAlex | [Fulltext](https://help.openalex.org/access/fulltext/) documents cached PDF/TEI, a content API requiring a key, an official CLI with retry/resume, and archive access. [Pricing](https://help.openalex.org/access/pricing/) and [products](https://help.openalex.org/access/overview/) list daily free usage and per-file costs. Content licence and version remain article-specific; metadata CC0 does not license every PDF. |
| Unpaywall | [API](https://unpaywall.org/products/api) and [maintainer code](https://github.com/ourresearch/oadoi/blob/master/views.py) describe DOI lookups with a real email parameter and a 100,000/day cap. Rate and contact requirements should be refreshed at implementation. No fake contact email or test request used. It discovers OA locations rather than guaranteeing every PDF. |
| CORE | [API](https://core.ac.uk/services/api) supports metadata and full-text access, registration and batch requests. Published rate guidance includes one batch or five single requests per ten seconds; configuration must follow the actual account's current limits. Not live-tested here. |
| arXiv | [Bulk access](https://info.arxiv.org/help/bulk_data.html) distinguishes metadata API/OAI-PMH from bulk full-text mechanisms. Use documented channels, keep version IDs and per-item licences. No full-corpus transfer attempted. |
| SSRN | [Free/paid papers](https://www.elsevier.support/ssrn/answer/are-all-papers-on-ssrn-free), [charging collections](https://www.elsevier.support/ssrn/answer/why-am-i-being-charged-for-a-paper-download), and [reuse](https://www.elsevier.support/ssrn/answer/can-i-repurpose-content-available-on-ssrn) show access and reuse vary. The [terms link](https://www.elsevier.support/ssrn/answer/what-are-ssrn-terms-and-conditions) was found but its destination could not be retrieved. No general public SSRN bulk full-text API was verified. |
| RePEc / NBER | [RePEc API](https://ideas.repec.org/api.html) includes links and restrictions rather than universal hosted full text. [NBER metadata](https://www.nber.org/research/data/nber-working-papers-and-chapters-metadata) provides periodically updated structured working-paper/publication records. Neither establishes unlimited PDF downloading. |
| Elsevier | [TDM policy](https://www.elsevier.com/about/policies-and-standards/text-and-data-mining) supports qualified ScienceDirect full-text API use; [TDM provisions](https://dev.elsevier.com/tdm_service.html) include use and retention conditions. Do not generalize ScienceDirect eligibility to SSRN or to merely holding an EBSCO subscription. |
| Wiley | [TDM documentation](https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining) describes a token, subscription eligibility, API-based acquisition and a Python client. Applicable institutional agreement should be checked before accepting new click-through terms. |
| Sage | [TDM / AI policy](https://www.sagepub.com/tdm-ai-policy) distinguishes non-commercial TDM from AI uses; [technical guidance](https://journals.sagepub.com/page/policies/text-and-data-mining) describes Crossref links and time-dependent rates. Check current machine-readable limits rather than hard-coding one global concurrency value. |
| Springer Nature | [Full Text API](https://dev.springernature.com/docs/api-endpoints/fulltext-api/) describes agreement-dependent XML access and a 2026 endpoint migration; [service overview](https://dev.springernature.com/docs/introduction/overview-services/) separates OA, metadata and TDM. Keys and content eligibility remain untested. |
| OUP | [Standard reuse rights](https://academic.oup.com/pages/standard-publication-reuse-rights) describes non-commercial TDM; [legal notice](https://academic.oup.com/pages/legal-notice) includes TDM and AI reservations. Apply the relevant content licence and use purpose; avoid treating either page as unrestricted AI permission. |
| Taylor & Francis | [TDM policy](https://taylorandfrancis.com/our-policies/textanddatamining/) supports qualified non-commercial mining and recommends contacting support for access arrangements. No universal self-service endpoint verified here. |
| Emerald / AEA / Chicago / JSTOR | [Emerald open research](https://www.emeraldgrouppublishing.com/publish-with-us/open-research-emerald) mentions TDM support; [AEA journals](https://www.aeaweb.org/journals) verifies its journal family; [JSTOR tools](https://about.jstor.org/products/jstor-platform/features-and-tools/) describes structured text-analysis support. API/whole-PDF capabilities were not verified for these families; publisher or library arrangements remain an integration task. |

## Verification and release boundary

The result supports an API-first, multi-source design and demonstrates why a single EBSCO route is insufficient. It does not prove a corpus-level success rate, authenticated EDS access, SSRN unattended reliability, or multi-institution compatibility. “No OA route found” must remain a time-stamped observation, not a permanent negative fact.

Before claiming a stable public batch skill, execute the staged benchmarks in [the project plan](../PROJECT_PLAN.zh-CN.md), including correct-document/version checks, interruption recovery, provider-specific throttling, API-key handling, zero-budget enforcement, and real authorized institutional routes. Distribute code and bibliographic/provenance records; exclude credentials, signed session links, and downloaded subscription papers.

Planning milestone validation: 155 unique catalogue titles, all retained ISSN checksums, 408 coverage rows with consistent status fields, JSON parsing, and local Markdown links passed. Existing JavaScript was not changed, so its unit tests were not rerun; those tests would not establish the proposed batch system's feasibility or reliability.
