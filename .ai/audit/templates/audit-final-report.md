---
name: audit-final-report
description: Structured template for final merged audit report combining all phase findings
agent: audit-orchestrator
alwaysApply: false
---

# Audit Report — mko_telepost

**Generated:** {date}
**Phases Completed:** {N}/{N}
**Validated Findings:** {N} total

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| **Overall Quality Score** | {1-10} |
| **Critical Findings** | {count} |
| **Production Readiness** | {READY \| PARTIALLY_READY \| NOT_READY} |

**Summary:**
{Brief paragraph summarizing system quality, main risks, readiness level.}

---

## 2. Architecture Summary

| Assessment Area | Score (1-10) | Notes |
|-----------------|--------------|-------|
| Command Layer | {score} | {observations} |
| Configuration | {score} | {observations} |
| Service Layer | {score} | {observations} |
| External Integrations | {score} | {observations} |
| Data Flow | {score} | {observations} |
| Security | {score} | {observations} |
| Test Quality | {score} | {observations} |
| Maintainability | {score} | {observations} |

**Strengths:**
- {List key strengths}

**Weaknesses:**
- {List key weaknesses}

---

## 3. Findings by Phase

{For each phase folder in `.ai/audit/` (excluding 00-bug_report, 99-validation, templates, validated), read `findings.md` and include its contents here.}

Source: `.ai/audit/*/findings.md` (all numbered phase folders)

---

## 4. Findings by Severity

### CRITICAL (must fix immediately)

| ID | Title | Affected Modules |
|----|-------|----------------|
| {id} | {title} | {modules} |

### HIGH (fix before production)

| ID | Title | Affected Modules |
|----|-------|----------------|
| {id} | {title} | {modules} |

### MEDIUM (technical debt)

| ID | Title | Affected Modules |
|----|-------|----------------|
| {id} | {title} | {modules} |

### LOW (nice to have)

| ID | Title | Affected Modules |
|----|-------|----------------|
| {id} | {title} | {modules} |

---

## 5. Cross-Cutting Concerns

### Config Propagation
- {Config flow findings across phases}

### Layer Interaction
- {CLI → Service → Integration boundary findings}

### Error Handling Consistency
- {Error handling findings across layers}

### Resource Cleanup
- {Temp file and cleanup findings}

### Secret Management
- {Security and credential findings across phases}

---

## 6. Fix Priority

1. **CRITICAL** — {count} issues must be fixed before any deployment
2. **HIGH** — {count} issues must be fixed before production release
3. **MEDIUM** — {count} technical debt items to address in next iteration
4. **LOW** — {count} improvements for future enhancement

---

## Merge Strategy

The orchestrator combines findings from all validated phase audits into this final report.

**Source:** `.ai/audit/*/findings.md` (all numbered phase folders)

**Process:**
1. All phase audits must be validated before final report generation
2. Each finding from per-phase files is extracted and categorized
3. Severity counts are tallied across all phases
4. Cross-cutting concerns are consolidated
5. Priority ordering follows: CRITICAL → HIGH → MEDIUM → LOW

---

## Template Field Reference

### Production Readiness Levels

- **READY** — No CRITICAL or HIGH findings, all mandatory fixes complete
- **PARTIALLY_READY** — HIGH findings exist but mitigation is possible
- **NOT_READY** — CRITICAL findings present, immediate fixes required
