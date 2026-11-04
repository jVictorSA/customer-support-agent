# Pre-Commit Code Review

**Date**: YYYY-MM-DD HH:MM:SS
**Branch**: `<branch>`
**Staged scope**: N files, +A / -B lines
**Review route**: Express | Full
**Verdict**: READY TO COMMIT | COMMIT WITH FOLLOW-UP | BLOCK COMMIT

## Summary

| Severity | Count |
|----------|-------|
| Critical | N |
| High | N |
| Medium | N |
| Low | N |

**Rationale**: One concise sentence tying the verdict to confirmed risk.

## Positive Findings

<!-- Include only genuine strengths observed in the staged work. Omit when empty. -->

- **Title** — Why this decision is valuable in this codebase.

## Critical Findings

### [SEC-01] Short title

- **Location**: `path/to/file.py:42`
- **Category**: Security | Correctness | Contract | Architecture | AI | Performance
- **Evidence**:
  ```python
  concise relevant code
  ```
- **Impact**: Concrete failure mode or risk.
- **Suggested correction**: A specific direction, not an unverified implementation.

## High Findings

<!-- Use the same finding structure. Omit this section when empty. -->

## Medium Findings

<!-- Use the same finding structure. Omit this section when empty. -->

## Low Findings

<!-- Use the same finding structure. Omit this section when empty. -->

## Non-Blocking Observations

<!-- Related but outside the changed line, or acceptance/contract context needing follow-up. Omit when empty. -->

- **Title** — Evidence and why it is not blocking this commit.

## Suggested Follow-Up

- [ ] Resolve all Critical and High findings.
- [ ] Decide whether Medium findings belong in this commit or tracked follow-up.
- [ ] Run the standard checks defined in the project's validation context.
- [ ] Run targeted validation appropriate to the changed contract, when available.
- [ ] Re-stage changes and request another pre-commit review.
