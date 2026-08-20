# Closeout — defect-scan-semantic

## Summary

- Ran the three semantic passes sequentially against the contracts and protocols outputs as the spec: Pass 3 (concurrency and resources), Pass 4 (security and trust boundaries), Pass 5 (API contract violations).
- 17 findings total: Pass 3 → 2 (both medium); Pass 4 → 8 (4 medium, 4 low); Pass 5 → 7 (2 medium, 5 low). No critical or high severities — nothing found that breaks normal single-user operation outright.
- Top findings: the false search-privacy claim (4.1), /state last-write-wins clobber (3.1), the mid-generation 401 cancel-with-misleading-message (5.1), the logit_bias shape mismatch (5.2, strong inference), and the unthrottled /login brute-force surface (4.2).

## Routed item closure

- arch-CF5 closed: search-privacy claim assessed as a false doc claim (4.1, medium, fix before porting); plain-HTTP transport (4.6) and unsandboxed card code/extensions (4.7) assessed as documented design choices with residual risk (low, port differently).
- mech-CF1 closed: /state unconditional last-write-wins assessed as a concurrency defect (3.1, medium, observed fact, port differently).
- mech-CF2 closed: (a) no body-size caps on /state and /llm/jobs POST (4.3, medium); (b) static serving exposes models/*.gguf and the product scripts to any authenticated client (4.4, medium); (c) API-key prefix console log (4.5, low) — all under pass 4.
- mech-CF3 closed: logit_bias map-of-string-keys vs llama-server's OpenAI-compatible array-of-{id,bias} shape mismatch recorded as the likely root cause of P1-3 (5.2, medium, strong inference); runtime confirmation remains q-logit-bias-root-cause.
- contracts-CF1 closed: vestigial reminderFrequency CONFIG control assessed as a UI-contract violation (5.3, low, port differently).
- contracts-CF2 closed: README.md:317 lorebook auto-update claim vs thread.lore-only compression assessed as doc/behavior drift (5.4, low, fix before porting); maintainer ruling on which side is intended stays post-pipeline (post-lorebook-claim-ruling).
- contracts-CF3 closed: no rate limiting or lockout on POST /login assessed under pass 4 (4.2, medium, fix before porting).
- proto-CF1 closed: mid-generation 401 → terminal classification → DELETE-ack cancels the live job while the message promises re-attach, assessed as a pass-5 error-behavior contract violation (5.1, medium, fix before porting).
- proto-CF2 closed: lazy swap readiness promotion + orphaned .swap-in-progress lock standing the monitor loop down indefinitely, assessed as a pass-3 concurrency/lifecycle defect (3.2, medium, fix before porting).

## Decisions Beyond Prompt

- Security-posture items (plain HTTP, unsandboxed code) are design choices documented in the source with deliberate mitigations — assessed as residual risk, not accidental bugs; tagged 'port differently' so a port re-makes the choice consciously.
- The logit_bias shape mismatch is recorded as strong inference, not observed fact; definitive confirmation stays with q-logit-bias-root-cause.
- No critical/high severities assigned; severity deliberately not inflated (extends D004).

## Coverage

- Inspected: fileserver.ps1 (auth, static resolution, proxy, /state, jobs, swap, dispatch loop), js/03-generation.js transport, js/06-state-sync.js, js/11-search.js, js/02-model.js, js/08-rag.js context blocks, js/13-dashboard.js, js/18-utils.js, js/15-cards.js, js/04-state.js, js/07-prompt.js, js/09-threads.js, js/10-chat.js, js/16-card-io.js, js/19-extensions.js, js/23-card-code.js, chat.html CONFIG modal, launch.bat monitor loop + metadata writers, README.md known-bugs + feature list; upstream findings read in full as the spec basis.
- Skipped: css/*, hardware-probe.ps1, identify-model.ps1 bodies, setup-lan.bat, js/14-scroll, 17-personas, 20-macros, 21-data, 22-scheduler, 24-boot bodies, thinking-parser internals, IDB migration bodies, retriever internals, launch.bat download-menu bodies, Build-LaunchScript internals — covered by earlier phases.
- Evidence basis: source inspection only (Windows-only, no runtime verification possible). Disposition: COMPLETE.

## Decisions Beyond Prompt

- The two security-posture items (plain-HTTP LAN transport; unsandboxed per-card JS and extensions) are assessed as documented design choices with residual risk rather than accidental bugs, because the source itself discloses the tradeoffs and ships deliberate mitigations (12h TTL, fingerprint binding, imported-code opt-in, wrapped hooks); they are tagged 'port differently' so a port re-makes the choice consciously.
- The logit_bias shape mismatch (map of token-id strings vs llama-server's OpenAI-compatible array-of-{id,bias}) is recorded as a strong-inference root cause for the README-declared broken banned-words feature (P1-3), not an observed fact; definitive confirmation stays with q-logit-bias-root-cause (needs-runtime-test).
- No critical or high severities were assigned in the semantic scan: every finding is a silent degradation, edge-case failure, defense-in-depth gap, or documented design choice; severity was deliberately not inflated (extends D004 to the semantic pass).
