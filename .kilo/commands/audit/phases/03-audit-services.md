---
name: 03-services
status: complete
validated: no
executor: auditor
problems-only: true
---

# Phase 03 Audit — Service Layer & Business Logic

## Output Mode

`problems-only: true` — **only problems, bugs, and deviations are documented.**

- **Do NOT** write sections that say "X is correct" or "no issues found in Y".
- **Do NOT** include checklist rows where the check passes — omit them entirely.
- If a dimension has zero findings after investigation, **omit the dimension entirely**.
- Every finding must be actionable: it describes a real problem, its evidence (code/logs/output), and its impact.

---

## Discovery Stage

Before performing audit checks, discover the service layer architecture:

1. **Service Discovery** — Locate all service modules. Map their responsibilities: what does each module do? What are its dependencies?
2. **Module Responsibility Mapping** — For each module: what is its purpose? Does it have a focused, single responsibility?
3. **Dependency Graph** — Map how modules depend on each other. Identify the composition root (where components are instantiated and wired together).
4. **Message Processing Chain** — Trace how Telegram messages are processed for forwarding: entity resolution, keyword matching, album grouping, and message sending. Identify each transformation step.

---

## Mandatory Runtime Verification

**Before evaluating any checklist item, you MUST complete these steps. Use the commands provided in the project's commands file. Skip only if a step is impossible — document why.**

### Step R1 — Import Verification

Import all service modules. Verify no import errors or missing dependencies.

### Step R2 — Linter and Type Checker

Run the project's configured linter and type checker commands.

- Record exit codes and output.

### Step R3 — Run Test Suite

Run the project's test suite, focusing on service-layer tests.

- Record pass/fail counts and failure output.

### Step R4 — Dead Code Search

Search for functions/methods defined but never called outside tests.

- Record each instance with file path and line number.

---

## Audit Scope

Service classes (monitor_forward.py, monitor_client.py), Task model, business logic, Telegram message processing.

---

## Audit Dimensions

### 1. Single Responsibility

| Check | Description |
|-------|-------------|
| Each module has focused responsibilities | `monitor_forward.py` handles message processing and forwarding. `monitor_client.py` handles Telethon client wrapper. |
| Task combines config and resolution | Task is designed to hold channel configuration with integrated entity resolution methods. |

**Evidence required:** Read each module. Verify the design follows the documented purpose: "Per-channel state management."

### 2. Dependency Direction

| Check | Description |
|-------|-------------|
| Services depend on abstractions/models | Services receive Pydantic models, not raw dicts or YAML data. |
| No circular dependencies | Import chains between modules are acyclic. |
| Composition root is clear | `monitor.py` coordinates the monitoring loop with Task and client. |

**Evidence required:** Trace import chains between modules. Verify the dependency graph is acyclic.

### 3. Message Processing Correctness

| Check | Description |
|-------|-------------|
| Keyword filtering is correct | Messages are filtered by configured keywords using the parser module. |
| Album grouping works | Messages with grouped media are correctly grouped before forwarding. |
| Duplicate prevention | `last_msg_id` prevents re-processing of already-seen messages. |
| Forwarding handles errors | `forward_to_users` retries on FloodWaitError and RPCError. |

**Evidence required:** Read `monitor_forward.py`. Trace the message processing pipeline. Check for keyword matching and album grouping logic.

---

## Report Output

Write findings to: `/.ai/audit/03-services/findings.md` using template `/.ai/audit/templates/audit-findings.md`.

**Write the file incrementally — append blocks of ≤100 lines each. Never write the entire report in a single call.**

Use prefix `SRV-` for finding IDs.

**`problems-only: true` rules:**
- The report contains **only findings** — real problems discovered during investigation.
- Do NOT include sections, dimensions, or checklist rows where everything is correct.
- If after completing all Runtime Verification steps and all Audit Dimensions, no problems were found, write a single line: `No problems found in this phase.`
- Every finding MUST include:
  1. **Runtime evidence** — import errors, test failures, dead code proof (file:line), logic bugs.
  2. **Not just:** "violates invariant X" — show the exact code that violates it and the exact consequence.
