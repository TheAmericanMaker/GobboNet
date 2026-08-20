# Thread Log — Index

This file is an **index** of per-session closeouts. Each session writes a full closeout to
`closeouts/<YYYY-MM-DD>-<phase-or-module>.md` using `templates/closeout-template.md`, and
appends one line here pointing to it.

The body of each session lives in the closeout file, not in this index. This pattern scales
forever: per-session files are individually small and read-budget-cheap, and avoid the
heredoc-vs-edit sync risks that bite append-to-large-file workflows once the file grows past
~50 KB.

## Format

```
- YYYY-MM-DD — <phase-or-module> — <one-line-summary> — [closeout](closeouts/YYYY-MM-DD-phase-or-module.md)
```

## De-dup discipline

Before appending, scan the bottom 5 entries. If you see a line with the same date AND same
phase-or-module AND same summary, do not append — the prior session already wrote it. The
framework has no programmatic dedup gate; this is human-discipline. (See
`Apply 20 spec deltas to Thaumaturge.txt` for the incident that established this rule.)

A one-liner to surface duplicates from the shell:

```bash
grep -E '^- [0-9]{4}-[0-9]{2}-[0-9]{2}' .codecarto/THREAD_LOG.md | sort | uniq -d
```

## Entries

<!--
  Append one line per session below this marker.
  Example:
  - 2026-05-02 — framework-feedback-pass — applied 6 spec-blockers + 5 clarifications from FEEDBACK_INDEX.md — [closeout](closeouts/2026-05-02-framework-feedback-pass.md)
-->

- 2026-05-02 — framework-feedback-pass — applied 6 spec-blockers + 5 clarifications from FEEDBACK_INDEX.md; 14 deferred to BACKLOG.md — [closeout](closeouts/2026-05-02-framework-feedback-pass.md)
- 2026-08-18 — architecture — Architecture phase complete: layer map, dependency direction, public surfaces, runtime lifecycle, concurrency model, build/packaging, and porting priorities mapped for GobboNet (Windows-only local AI chat frontend: batch launcher + PowerShell file server + vanilla JS browser UI + llama.cpp). All five secondary outputs written. Validation PASS (6/6 criteria). Six carry-forward entries routed to protocols, contracts, defect-scan-mechanical, defect-scan-semantic, and porting; five open questions recorded. — [closeout](closeouts/2026-08-18-architecture.md)
- 2026-08-18 — defect-scan-mechanical — Mechanical defect scan complete: 17 findings across passes 1/2/6 (0 critical, 0 high, 8 medium, 9 low), arch-CF3 and arch-CF4 closed, 3 semantic items routed to defect-scan-semantic, validation PASS. — [closeout](closeouts/2026-08-18-defect-scan-mechanical.md)
- 2026-08-18 — contracts — Contracts phase complete: 40 user-visible behavior contracts across four surfaces (web UI, CLI/launcher, HTTP API, storage/export formats), security and authorization model, configuration model, ownership mapping, 32-row black-box acceptance list, and 9 doc/code conflicts. Routed item arch-CF2 closed. All four secondary outputs appended. Validation PASS (7/7 criteria). Three new carry-forward entries routed to defect-scan-semantic (contracts-CF1..CF3); one post-pipeline maintainer ruling (post-lorebook-claim-ruling). — [closeout](closeouts/2026-08-18-contracts.md)
- 2026-08-18 — protocols — Protocols phase complete: 18 protocol/event-stream entries (P1-P18) with producer/consumer/transport/ordering/required/optional/identifiers/error/restart fields, 5 state machines with guards and side effects, persistent schema notes for 8 storage mechanisms, 19 compatibility hazards, coverage section, and validation PASS (6/6 criteria). Routed item arch-CF1 closed (all six wire formats extracted with file:line citations, including the decoded search-proxy command). All four secondary outputs appended with dated 2026-08-18 protocols sections. Two new carry-forward entries routed to defect-scan-semantic (proto-CF1, proto-CF2); four open questions recorded (q-ollama-api-version, q-websearch-response-fields, q-sse-done-marker, q-llama-server-diag-endpoints). — [closeout](closeouts/2026-08-18-protocols.md)
- 2026-08-18 — defect-scan-semantic — Semantic defect scan complete: 17 findings across passes 3 (2), 4 (8), and 5 (7) — 0 critical, 0 high, 8 medium, 9 low — each with location, severity, evidence level, and action; pass-5 findings cite their contract/protocol references. All nine routed carry-forward items closed (arch-CF5, mech-CF1, mech-CF2, mech-CF3, contracts-CF1, contracts-CF2, contracts-CF3, proto-CF1, proto-CF2) with none re-routed. Security-posture items assessed as documented design choices with residual risk. Validation: PASS (7/7 criteria). — [closeout](closeouts/2026-08-18-defect-scan-semantic.md)
- 2026-08-18 — porting — Porting phase complete: reverse-engineering bundle synthesized from all five upstream artifacts (55 feature contracts, 34 defects, 28 portability hazards, protocol/state notes, Source Index with deep-read triggers); arch-CF6 closed; five secondary outputs appended; validation PASS (7/7). — [closeout](closeouts/2026-08-18-porting.md)
- 2026-08-18 — reimplementation-spec — Reimplementation-spec phase complete: language-agnostic build plan and acceptance spec synthesized from the porting bundle (8 modules, 55 behaviors, 32 acceptance scenarios, 34/34 defects accounted for); porting-CF1 closed; validation PASS (8/8). — [closeout](closeouts/2026-08-18-reimplementation-spec.md)
