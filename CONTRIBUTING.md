# Contributing to UTD Paper Access

UTD Paper Access is an experimental local research tool. Focus contributions on reliable, lawful acquisition through access the user already has.

## Before opening a change

1. Open an issue for a new institution, provider route, or major behavior change.
2. Never commit downloaded papers, credentials, cookies, signed URLs, task databases, or local bridge configuration.
3. Preserve the separation between download success and paper identity validation.
4. State the operating system, Chrome version, institution, and whether a test used fixtures or a real authorized route.

## Local checks

```sh
uv sync --dev
uv run pytest
npm test
npm run check
uv build
```

Validate `skills/utd-paper-access` with the Agent Skills `quick_validate.py` helper available in your Codex skill-creator installation.

Real-source tests must use your own authorized access and must not add the resulting PDFs or session data to the repository. Include a concise description of what was verified and what remains untested.

## Pull requests

Keep changes focused. Explain the trigger, the resulting behavior, and the validation performed. For provider changes, include failure behavior for missing access, expired sessions, website verification, and a wrong-document result.
