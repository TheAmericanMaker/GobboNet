# Closeout — contracts

## Summary

- Extracted 40 behavioral contracts for GobboNet, split by surface: Web UI (24), CLI/launcher (6), HTTP API (6), storage/export formats (4). Every contract carries trigger, defaults, observable output, side effects, persisted state, error behavior, retry/recovery, owner (layer/package), and an evidence level with file:line citations.
- Closed arch-CF2: every feature in the README feature list (README.md:286-357) now has a contract — streaming, stop, reroll, edit, branching, lore compression, macros (built-in/custom/auto-continue), scheduler, hot-swap, data export/import/purge, extensions, card code, RAG, personas, web search, and the rest.
- Security model documented: salted SHA-256 password → HttpOnly session cookie (12h TTL, no Secure flag by design) bound to a client fingerprint; loopback-only upstreams; unsandboxed card code/extensions by design; the README search-privacy claim vs the passthrough proxy recorded as a conflict (arch-CF5 context).
- Configuration model documented: launch.bat header vars → download-menu overrides (session-only) → identify-model.ps1 ground truth → GEMMA_* env handoff → browser DEFAULT_SETTINGS/per-card fields; tokenLimit vs CTX_SIZE split; vestigial reminderFrequency flagged.
- Black-box acceptance list: 32 scenario rows a reimplementation can run without the source.
- Nine doc/code conflicts recorded explicitly (search privacy, logit bias, lorebook auto-update, file extensions, reminderFrequency, default-off features, two stale comments).

## Coverage

- Inspected: README (full), chat.html (modals/settings), 24 js files (full or large partial reads), fileserver.ps1 (auth/state/jobs/swap/proxy/static/dispatch), launch.bat (config/password/menu/launch/monitor), default-characters.json, decoded search-proxy command.
- Skipped: hardware-probe detection layers, identify-model family tables, css bodies, render/parser internals, download-menu bodies — rendering/formatting details or already covered by earlier phases; wire formats remain protocols-phase territory (arch-CF1).
- Evidence basis: source inspection only. No runtime verification (Windows-only), no tests, no CI.
- Disposition: COMPLETE.

## Open Questions

- None new. Existing questions (q-installer-packaging, q-refactor-plan, q-font-shipping, q-accept-loop-scale, q-ollama-api-version, q-logit-bias-root-cause, q-tekken-patch-completeness) were re-checked against contracts-phase reading and none became answerable from source.

## Carry-Forward

- contracts-CF1 → defect-scan-semantic (vestigial reminderFrequency UI)
- contracts-CF2 → defect-scan-semantic (lorebook auto-update claim vs code)
- contracts-CF3 → defect-scan-semantic (no login rate limiting)

## Post-Pipeline

- post-lorebook-claim-ruling (maintainer ruling on README.md:317 vs code)

## Decisions Beyond Prompt

- README feature list treated as the primary contract source; code as arbiter of defaults/error behavior; conflicts recorded, not silently resolved.
- Security posture assessment (search-privacy claim) left to defect-scan-semantic; contracts records the conflict only.

## Decisions Beyond Prompt

- Contracts phase treated the README feature list (README.md:286-357) as the primary contract source and the code as the arbiter of defaults/error behavior, per the phase SKILL.md's source-priority order; doc/code conflicts are recorded explicitly rather than silently resolved.
- The search-privacy claim (README.md:342) vs the passthrough implementation is recorded as a doc/code conflict in the contracts output and left for defect-scan-semantic (arch-CF5) to assess; the contracts phase does not rule on security posture.
