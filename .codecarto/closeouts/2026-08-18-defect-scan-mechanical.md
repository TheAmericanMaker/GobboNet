# Closeout — defect-scan-mechanical

## Summary

- Ran passes 1 (logic/correctness), 2 (error handling), 6 (config/environment) over the GobboNet source per the phase skill, with the architecture map as the prioritization guide.
- 17 findings: 6 pass-1, 5 pass-2, 6 pass-6. Severity: 0 critical, 0 high, 8 medium, 9 low. Every finding carries file:line evidence, an evidence level, and a porting action.
- Closed routed items: arch-CF3 (config hazards -> P6-1, P6-2, P6-3) and arch-CF4 (README known bugs -> P1-3, P1-4).
- Routed to defect-scan-semantic: mech-CF1 (/state last-write-wins concurrency), mech-CF2 (request-size caps, static exposure of models/, API-key console logging), mech-CF3 (logit_bias request-shape contract check).
- Open questions: q-logit-bias-root-cause, q-tekken-patch-completeness (both needs-runtime-test).

## Top findings

1. P1-1 (medium): hot-swap and crash-restart kill the embedding server by bare image name and never restart it — RAG silently degrades after every swap.
2. P1-2 (medium): any-response/substring health probes misdetect foreign services (Ollama) as healthy llama-server.
3. P6-1 (medium): engine and embedding downloads ship unpinned (empty SHA-256).
4. P6-2 (medium): per-model CTX_SIZE/KV_CACHE_TYPE overrides exist only in the download menu; hot-swaps and later launches ignore them.
5. P1-3/P1-4 (medium): README-declared broken logit bias and possibly-incomplete Tekken patch, located and classified.

## Decisions Beyond Prompt

- README known-bugs treated as observed-fact evidence for defect existence; root cause and patch completeness recorded as open questions instead of guessed.
- No critical/high severities assigned — nothing found breaks normal operation outright; severity deliberately not inflated.

## Proposed Conventions

- health-probe-must-verify-identity
- process-kill-must-scope-by-role

## Decisions Beyond Prompt

- Mechanical scan treated the README's own known-bugs section as observed-fact evidence for the existence of the logit-bias and Tekken defects, with root cause and patch completeness recorded as open questions rather than guessed.
- No critical or high severities were assigned: every finding is a silent degradation, latent risk, or config hazard; nothing found breaks normal operation outright. Severity was deliberately not inflated.
