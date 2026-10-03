# UTD Paper Access

**Give your AI research assistant the full paper, not just the abstract.**

UTD Paper Access is a local-first Agent Skill and Chrome bridge for reading papers in the **UTD Top 24 business-journal set** and related SSRN working papers through access the user already has.

[中文说明](README.zh-CN.md) · [Install](INSTALL.md) · [Privacy](PRIVACY.md) · [Contributing](CONTRIBUTING.md)

> **UTD means the University of Texas at Dallas Top 24 journal set. It does not mean the University of Toronto.** University of Toronto is the institution used by the currently validated INFORMS LibKey/EBSCO route. The official and current journal list is maintained by [UT Dallas](https://jsom.utdallas.edu/the-utd-top-100-business-school-research-rankings/index.php).

## Quick start

Current requirements: macOS, Google Chrome, and a local Codex environment that can run commands. Paste this into Codex:

> Install UTD Paper Access from https://github.com/LIMYOYO/utd-paper-access. Read INSTALL.md and skills/utd-paper-access/references/installation.md first. Set up the CLI, skill, Chrome extension, and native bridge, then verify each route I need by downloading one real paper. Ask me only when Chrome permission, institutional login, MFA, or website verification needs my action.

Codex handles the local setup. You normally need to load the unpacked extension, approve its website permissions, authenticate through your own institution when needed, and keep that Chrome profile open.

Installing only `SKILL.md` is insufficient: browser acquisition also uses the CLI, extension, and native bridge in this repository. The preferred command is `utd-paper-access`; the legacy `paper-access` command, data directory, and native bridge identifiers remain available for existing installations.

## Use it naturally

You do not need to name the skill after installation:

```text
Find recent UTD Top 24 and SSRN papers about mobile AED deployment.
When an abstract is insufficient to judge relevance, download the paper and read the relevant sections.
```

You can also provide an INFORMS DOI or SSRN URL:

```text
Download and read https://pubsonline.informs.org/doi/10.1287/mnsc.2018.3061.
Compare its model with mine and give page-level evidence.
```

## UTD Top 24 coverage

The official UTD ranking currently tracks 24 journals. This project does **not** yet provide a dedicated automated publisher route for all 24.

| Coverage | Journals or sources | Current behavior |
| --- | --- | --- |
| Dedicated browser route | **Information Systems Research; INFORMS Journal on Computing; Marketing Science; Management Science; Operations Research; Manufacturing & Service Operations Management; Organization Science** | INFORMS DOI → LibKey → University of Toronto/EBSCO → local PDF. Up to 10 papers per INFORMS batch; subscription and identity results remain per paper. |
| Open-copy and local-file support | All 24 journals | Can reuse an existing authorized PDF or try a stable open repository copy when the requested version permits it. Availability is not guaranteed. |
| Working-paper route | SSRN, which is not itself a UTD Top 24 journal | Single-paper Chrome route with separate download and identity checks. |
| No dedicated publisher automation yet | **The Accounting Review; Journal of Accounting and Economics; Journal of Accounting Research; Journal of Finance; Journal of Financial Economics; Review of Financial Studies; MIS Quarterly; Journal of Consumer Research; Journal of Marketing; Journal of Marketing Research; Journal of Operations Management; Production and Operations Management; Academy of Management Journal; Academy of Management Review; Administrative Science Quarterly; Journal of International Business Studies; Strategic Management Journal** | Currently limited to open copies, an existing local PDF, or a manually completed authorized browser download. |

## Support status and roadmap

| Capability | Status now | Planned direction |
| --- | --- | --- |
| UTD24 INFORMS journals | Supported through the validated University of Toronto LibKey/EBSCO route | Improve resilience as publisher and EBSCO pages change. |
| Other institutions | Link planning accepts institution name, LibKey library ID, OpenAthens domain, and OpenURL resolver | Add institution profiles and configurable EBSCO tenants. Users currently need to adapt the route to their own library subscription and test one real paper. |
| SSRN | Single-paper acquisition | Add bounded batch requests after the single-paper route is stable across more samples. |
| Other 17 UTD24 journals | Open copy, local import, or manual authorized download only | Add publisher routes in small validated groups rather than claiming blanket coverage. |
| Platforms and browsers | macOS + Google Chrome | Validate Windows/Linux and additional Chromium browsers; Firefox is not supported. |
| Supplementary files, datasets, and code | Not a dedicated acquisition target | Add explicit artifact types and validation before automating them. |

## Research-use boundary

UTD Paper Access is designed to improve an AI research assistant's ability to read papers that the user is already authorized to access for personal research. It is not a paper-distribution service.

Do not use it to bypass subscriptions, login, MFA, CAPTCHA, website verification, rate limits, or license terms; mass-download a collection beyond the user's authorization; or redistribute, republish, or publicly share acquired PDFs. Institutional access and permission to read a paper do not automatically grant redistribution, text-and-data-mining, or AI-processing rights. The user remains responsible for the applicable library and publisher terms.

The project has no hosted backend, analytics, advertising, or account system. It does not export passwords, cookies, MFA responses, or institutional credentials. PDFs and task data stay on the user's computer. See [PRIVACY.md](PRIVACY.md).

## How it works

```mermaid
flowchart LR
    A[Research question or paper link] --> B[utd-paper-access skill]
    B --> C[Local CLI and native bridge]
    C --> D[User's Chrome profile]
    D --> E[SSRN]
    D --> F[LibKey / EBSCO]
    E --> G[Local PDF]
    F --> G
    G --> H[Download check]
    H --> I[Identity check]
    I --> J[AI reads authorized full text]
```

Download success and paper identity are separate gates. Advisory mode can read a complete PDF whose identity still needs review; strict mode requires both gates before analysis.

## Verification

The current preview has been tested on one macOS + Chrome installation with single-paper INFORMS and SSRN downloads, a 10-paper INFORMS batch, and mixed success/failure isolation. Every new institution and machine still needs its own real-paper acceptance test.

```sh
uv sync --dev
uv run pytest
npm test
npm run check
uv build
```

Real-browser acceptance requires the user's own authorized access. The repository contains no publisher PDFs, credentials, cookies, or session data.

## Repository layout

| Path | Purpose |
| --- | --- |
| `python/paper_access/` | CLI, task store, source adapters, validation, and native bridge |
| `src/`, `manifest.json` | Chrome extension loaded with **Load unpacked** |
| `skills/utd-paper-access/` | Agent Skill and Codex installation references |
| `profiles/providers/` | Declared provider capabilities and limits |
| `tests/` | Python and extension tests |
| `docs/` | Design notes, access research, and acceptance evidence |

UTD Paper Access is released under the [MIT License](LICENSE).
