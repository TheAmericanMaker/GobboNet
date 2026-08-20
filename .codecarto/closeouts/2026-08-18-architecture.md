# Closeout — architecture

## Summary

- Mapped GobboNet: a Windows-only, fully-local AI chatbot frontend (launch.bat orchestrator, fileserver.ps1 HTTP server/reverse proxy/hot-swap controller, vanilla HTML/CSS/JS chat UI, llama.cpp engine, optional embed + search proxies).
- Layer map: product shell (launch.bat, setup-lan.bat) → integration adapters (fileserver.ps1, search proxy, hardware-probe.ps1) → protocol/normalization (identify-model.ps1, client-side prompt/context building) → UI/rendering + persistence (chat.html, 24 numbered js files, 15 numbered css files). Stable base: js/01-config.js + js/04-state.js.
- Dependency direction: launch.bat → everything; fileserver.ps1 → upstream services; frontend → fileserver (same-origin) or localhost (file://); JS linear numbered load order, global namespace, no module system; CSS cascade 01→15. No structural cycles; intentional lock-file coordination between fileserver.ps1 and the monitor loop.
- Public surfaces: 1 user CLI (launch.bat), 1 admin script (setup-lan.bat), ~15 HTTP routes on :8080 behind password + session cookie, 3 upstream APIs (llama-server, embed server, Ollama search), 7 file formats, 8 screens/modals.
- Runtime lifecycle: 15-step host boot, 7-step browser boot, detached-job generation lifecycle, hot-swap phase machine, monitor-loop supervision, boot-time hygiene.
- Concurrency: single-threaded browser event loop (one generation at a time); single-threaded HttpListener accept loop + max-4 worker runspaces; batch monitor loop; llama-server --parallel 1.
- Build: no build step; distribution via unsigned installer (outside repo) or ZIP; one-time verified downloads; no CI.
- Porting priorities: llama-server integration, fileserver, state/persistence, chat core = core; RAG, cards, data mgmt = important; hardware probe, search proxy = optional; launch.bat = incidental.

## Coverage

- Inspected: README (full), chat.html (structure), all js/css headers + key bodies, launch.bat (majority), fileserver.ps1 (config/auth/state/jobs/swap/static/proxy/dispatch), setup-lan.bat, hardware-probe.ps1 (header/schema), identify-model.ps1 (header/GGUF parsing), default-characters.json, .gitignore, LICENSE.
- Skipped (routed to later phases): deep bodies of render/dashboard/cards/card-io/personas/utils/extensions/macros/data/card-code; hardware-probe detection layers; identify-model family tables; fileserver proxy/job-worker internals; css bodies.
- Evidence basis: source inspection only. No runtime verification (Windows-only), no tests, no CI.
- Disposition: COMPLETE.

## Open Questions

- q-installer-packaging, q-refactor-plan, q-font-shipping (needs-maintainer-decision)
- q-accept-loop-scale, q-ollama-api-version (needs-runtime-test)

## Carry-Forward

- arch-CF1 → protocols (wire formats)
- arch-CF2 → contracts (user-visible behavior)
- arch-CF3, arch-CF4 → defect-scan-mechanical (config hazards; known bugs)
- arch-CF5 → defect-scan-semantic (security posture)
- arch-CF6 → porting (portability hazard synthesis)

## Proposed Conventions

- numbered-load-order-contract
- env-var-handoff

## Decisions Beyond Prompt

- System boundary = repo contents; installer binaries recorded as open question, not guessed.
- Evidence levels follow the phase SKILL.md's four-level vocabulary with file:line citations.

## Decisions Beyond Prompt

- Architecture phase treated the repo (not the installer binaries) as the system boundary; installer packaging recorded as open question q-installer-packaging rather than guessed.
- Evidence levels used are the four SKILL.md levels (observed fact / strong inference / portability hazard / open question) with file:line citations, per the phase skill rather than the template's older fact/inference/open-question trio.
