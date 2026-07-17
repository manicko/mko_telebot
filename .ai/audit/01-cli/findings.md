## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 2 |
| LOW | 3 |

## Mandatory Fixes

- **CLI-001** (mandatory): `validate` performs existence-only check, not schema validation. Make it invoke `reader.load()` (or a schema-validate method) so invalid configs are caught before `run`.

## Advisory Recommendations

- **CLI-002** (advisory): Align docs/code on Ctrl+C exit code — doc says 0, code returns 130. Recommend updating docs to 130.
- **CLI-003** (advisory): Fix doc claim that auth failure "continues for other channels"; it actually terminates the run. Update docs.
- **CLI-004** (advisory): Run `ruff format` on `cli.py`/`main.py` to satisfy the project formatter config.
- **CLI-005** (advisory): Clarify docs: `telethon_config.yaml` is preserved regardless of `--force`.

## Doc Updates Needed

- **CLI-002**: cli-reference.md exit-code table (lines 172, 180) — Ctrl+C exit code.
- **CLI-003**: cli-reference.md error-handling table (line 173) — auth failure behavior.
- **CLI-005**: cli-reference.md `init` behavior (line 66) — credential preservation trigger.

---

## Runtime Verification Log

- **R1 — Import verification:** `uv run python -c "import mko_telebot.cli; ..."` → `IMPORTS OK`. No broken/missing dependencies.
- **R2 — Help/usage:** `mko-telebot --help`, `mko-telebot init --help` → both render usage without errors (exit 0).
- **R3 — Lint/type:**
  - `uv run ruff check src/mko_telebot/cli.py src/mko_telebot/main.py` → "All checks passed!" (exit 0).
  - `uv run ruff format --check src/mko_telebot/cli.py src/mko_telebot/main.py` → "2 files would be reformatted" (exit non-zero) — see CLI-004.
  - `uv run basedpyright src/mko_telebot/cli.py` → "0 errors, 0 warnings, 0 notes" (exit 0).
  - `uv run mypy src/mko_telebot/cli.py` → "Success: no issues found" (exit 0).
- **R4 — Test suite:** `uv run pytest tests` → `373 passed in 8.91s` (exit 0).
- **Behavioral checks:** `mko-telebot version` → "mko-telebot version 0.0.1" (exit 0); `mko-telebot config` → table renders correct Windows paths matching docs.
