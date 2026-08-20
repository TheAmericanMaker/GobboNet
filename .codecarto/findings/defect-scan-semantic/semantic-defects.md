# Semantic Defects Report — GobboNet

<!--
  Output for the `defect-scan-semantic` phase (pipeline: workflow/pipeline-full-with-deep-audit.yaml).
  Covers passes 3, 4, and 5 from the defect-scan methodology — the bugs that
  need contracts and protocols context to spot reliably.
  Evidence levels: `observed fact` | `strong inference` | `open question` (per findings/defect-scan/SKILL.md).
  Action set: pre-porting pipeline → `fix before porting` | `port differently` | `leave behind`.
-->

## Scan Context

- **Source:** `../` (repository root)
- **Architecture reference:** `findings/architecture/architecture-map.md`
- **Contracts reference:** `findings/contracts/behavioral-contracts.md`
- **Protocols reference:** `findings/protocols/protocols-and-state.md`
- **Mechanical defects reference:** `findings/defect-scan-mechanical/mechanical-defects.md`
- **Pipeline:** workflow/pipeline-full-with-deep-audit.yaml
- **Date:** 2026-08-18
- **Scope:** Semantic passes only (3 concurrency, 4 security, 5 contract violations). Mechanical passes (1 logic, 2 error handling, 6 configuration) were covered earlier in `defect-scan-mechanical`; its findings (P1-*, P2-*, P6-*) are referenced, never re-flagged.

---

## Pass 3: Concurrency and Resource Management

| # | Location | Defect | Evidence | Severity | Evidence Level | Action |
|---|----------|--------|----------|----------|----------------|--------|
| 1 | fileserver.ps1:545-564 (`Handle-State`); client 06-state-sync.js:78-143 | **Closes mech-CF1.** `/state` POST/PUT is unconditional last-write-wins: the body is JSON-validated and written whole with no server-side conflict check, no version stamp, and no locking. The client's mtime protocol is advisory only — the server never compares incoming state against the stored mtime. Two devices (phone + desktop) writing within the same window silently clobber each other's changes in `.gobbonet-state.json`; the boot decision matrix (SM3) can only detect divergence *after* the clobber, and its "server newer → prompt" branch offers the clobbered copy as the restore candidate. | `Write-FileUtf8 $StatePath $body` (557) runs for any authenticated POST/PUT with no read of the existing file's mtime; `GET /state/info` exposes mtime (518-528) but nothing enforces it on write. Client-side `lastKnownMtime` (06-state-sync.js:42-54) is used only for the boot matrix, never sent as a precondition. | medium | observed fact | port differently |
| 2 | fileserver.ps1:1380-1440 (`Handle-SwapStatus`); launch.bat:1845-1858 (monitor loop) | **Closes proto-CF2.** Swap readiness promotion is lazy — `starting → ready/error` only advances when a client polls `GET /swap-status` (the health check and both timeout paths live inside the poll handler). If the client stops polling mid-swap (tab closed, phone screen locked), the `.swap-in-progress` lock persists indefinitely: launch.bat's monitor loop sees the lock and stands down forever (no crash-restart protection until the next fileserver boot), and a second swap is refused 409. Compounding: nothing supervises fileserver.ps1 itself — if it dies mid-swap, the lock survives until boot hygiene (fileserver.ps1:137-140) runs, which requires a fileserver restart that launch.bat never performs. | Promotion code exists only inside `Handle-SwapStatus` (1393-1440); the lock is removed only on ready/error promotion (1409, 1433, 1438) or boot hygiene (137-140). Monitor stand-down: `if exist "!SWAP_LOCK!" ( … goto :monitor_loop )` (launch.bat:1855-1858). Client poll budget is 180s (02-model.js:344-361) — after that the client gives up and nothing else polls. | medium | observed fact | fix before porting |

---

## Pass 4: Security and Trust Boundaries

| # | Location | Defect | Evidence | Severity | Evidence Level | Action |
|---|----------|--------|----------|----------|----------------|--------|
| 1 | README.md:342 vs 02-model.js:398-400, fileserver.ps1:423-436, 1587-1589, 11-search.js:45-52 | **Closes arch-CF5 (search-privacy item) and mech-CF2(c).** README claims "identifying metadata and telemetry are stripped from your searches." The code strips nothing: `privacyFetch` is a bare `fetch` passthrough (02-model.js:398-400); the client sends the full query + `Authorization: Bearer <key>` to the search proxy (11-search.js:45-52); the fileserver `/search` proxy forwards headers (including Authorization) and body verbatim to the search proxy (fileserver.ps1:423-436, 1587-1589 — no key injection, unlike `/llm` at 442-445); the search proxy forwards verbatim to `https://ollama.com/api` (decoded launch.bat:1608). The claim is false as written — a doc/code conflict, not a code bug. | `function privacyFetch(url, options = {}) { return fetch(url, options); }` (02-model.js:398-400) with the comment "llama.cpp has zero telemetry so there's nothing to scrub" — the comment is about llama.cpp, but the README claim is about *searches*, which go to Ollama. | medium | observed fact | fix before porting |
| 2 | fileserver.ps1:1497-1531 (`/login` handler) | **Closes contracts-CF3.** No rate limiting, lockout, or backoff on `POST /login`: an on-LAN attacker can brute-force the shared password with unlimited attempts. The password hash is fast salted SHA-256 (fileserver.ps1:111-116), so offline-style guessing speeds apply to the online endpoint; the 6-char minimum (launch.bat:310-362) is the only brake. | The login branch (1497-1531) performs the constant-time compare and either sets a cookie or returns 401 — no attempt counter, no per-IP state, no delay exists anywhere in the handler or the dispatch loop (1471-1618). | medium | observed fact | fix before porting |
| 3 | fileserver.ps1:546-547 (`Handle-State`), 794-795 (`Handle-Jobs`) | **Closes mech-CF2(a).** No request-body size caps: both handlers read the entire body into memory (`StreamReader.ReadToEnd()`) before validating. An authenticated client can POST a multi-GB body to `/state` or `/llm/jobs` and exhaust the fileserver's memory (the `/state` body is also written to disk unbounded, growing `.gobbonet-state.json`). LAN-scoped (requires a valid session), but any authenticated device — including a compromised IoT device on the same Wi-Fi — can crash the server. | `$body = $reader.ReadToEnd()` at 547 and 795 with no `Content-Length` check or cap; the mechanical phase's P2-1 covers the mirror-image read-side problem (static `ReadAllBytes`), this is the write-side. | medium | observed fact | port differently |
| 4 | fileserver.ps1:363-385 (`Resolve-StaticPath`), 1597-1608 (static fallthrough) | **Closes mech-CF2(b).** Static serving exposes every non-dotfile under the project root to any authenticated client: `models/*.gguf` (4-20 GB downloads), `launch.bat`, `fileserver.ps1`, `identify-model.ps1`, `hardware-probe.ps1`, `setup-lan.bat`, `README.md`. Only traversal and dot-prefix are refused — there is no extension allowlist and no size cap. The memory-exhaustion angle of serving a GGUF is mechanical P2-1 (referenced, not re-flagged); the *exposure* itself is the security defect: the model files are the user's licensed downloads and the scripts are the product's full source, all pullable by any session holder. | `Resolve-StaticPath` rejects only `..` (369) and dot-prefixed segments (374); the fallthrough (1597-1608) serves whatever resolves. `.gobbonet-secret` and `.jobs/` are protected only by the dotfile rule. | medium | observed fact | port differently |
| 5 | js/11-search.js:26 | **Closes mech-CF2(c) (console-log half).** `webSearch` logs the API key prefix to the browser console on every search: `console.log('[search] API key present: ' + apiKey.slice(0, 6) + '...')`. Console-only and local, but it is key material in a log line, and the same file logs the raw upstream response (11-search.js:56) which may echo the key in error bodies. | Line 26 verbatim; line 56 logs `rawText.slice(0, 500)` of the proxy response. | low | observed fact | port differently |
| 6 | fileserver.ps1:78-127, 1520-1521, 353-355; setup-lan.bat:47-100 | **Closes arch-CF5 (transport item).** Plain-HTTP LAN transport: the password travels in cleartext on the LAN at login, the session cookie has no `Secure` flag (impossible on plain HTTP), and any on-path LAN device can sniff both. **Assessed as a documented design choice, not an accidental bug:** the code comments (78-88, 121-126) and the login page itself (353-355: "This connection is over your local network in plain text (not encrypted)… Avoid using it on shared or public Wi-Fi") disclose the tradeoff, and the mitigations are deliberate — 12h session TTL, 32-byte random tokens, client-fingerprint binding (259-316), firewall scoped to LocalSubnet. Residual risk: a sniffed cookie + spoofed IP/User-Agent still works for up to 12h; the fingerprint is explicitly "not a strong identity" (261-263). | All cited lines; the design rationale is written into the source. | low | observed fact | port differently |
| 7 | js/23-card-code.js:22-33, 76-121; js/19-extensions.js:19-82; README.md:320, 349 | **Closes arch-CF5 (unsandboxed-code item).** Per-card custom code and extensions run unsandboxed with full page access — a malicious card or extension can read every chat, exfiltrate state via `fetch`, or steal the session by driving the UI. **Assessed as a documented design choice, not an accidental bug:** 23-card-code.js:22-28 states plainly "WHY IT IS NOT SANDBOXED… your machine, your card, your code"; README.md:320/349 carry the same honest note; mitigations are real — imported card code is always disabled until opted in (23-card-code.js:30-33, 301-313), every hook call is wrapped so a throwing hook is disabled rather than fatal (23-card-code.js:26-28), and hooks are torn down on card switch. Residual risk: the opt-in is one checkbox away from full page compromise, and extensions have no opt-in-per-script granularity. | All cited lines. | low | observed fact | port differently |
| 8 | fileserver.ps1:198-206 (`Add-CommonHeaders`) | Wildcard CORS on every response: `Access-Control-Allow-Origin: *` with `Allow-Headers: Content-Type, Authorization`. Practical impact is blunted by `SameSite=Lax` on the session cookie (1520-1521) — cross-site fetches don't carry the cookie, so a malicious website can't ride an authenticated session — but the wildcard is still a defense-in-depth gap: it invites misconfiguration in a port (e.g., if a port switches to bearer-header auth without SameSite protection, `*` + `Authorization` becomes a real cross-site channel). | Header block verbatim at 202-204. | low | observed fact | port differently |

---

## Pass 5: API Contract Violations

| # | Location | Defect | Severity | Evidence Level | Action | Spec Reference |
|---|----------|--------|----------|----------------|--------|----------------|
| 1 | js/03-generation.js:375, 452-465; fileserver.ps1:872-880 | **Closes proto-CF1.** Session expiry mid-generation: the job poll returns 401 → the client classifies it as a terminal outcome, clears the breadcrumb, and sends `DELETE /llm/jobs/<id>` — which the server turns into a cancel flag for the still-running job (fileserver.ps1:874-878), killing the live generation. The error message shown to the user — "file-server login session expired — reload the page and sign in to re-attach" (03-generation.js:453) — promises re-attachment that the code path has already foreclosed: the job is cancelled, the spool is swept, and the breadcrumb is gone. Error behavior violates the documented recovery contract. | medium | observed fact | fix before porting | P5 (Auth/session protocol) "Restart or resume behavior" (protocols-and-state.md); SM1 row "(client) attached \| Poll 401 \| — \| unauthorized \| Error note; breadcrumb cleared; DELETE ack **cancels the live job**"; contracts "Generation job resume (after navigation)" — Error behavior ("Server unreachable → breadcrumb kept, retried later") and "Authentication: login / logout / session" — Retry or recovery ("Re-login"). |
| 2 | js/06-state-sync.js:725-793 (esp. 734, 774); js/10-chat.js:161-166 | **Closes mech-CF3.** The client builds `logit_bias` as a **map of token-id strings** (`logitBias[String(id)] = strength`, 06-state-sync.js:774) and merges it into the `/v1/chat/completions` body (10-chat.js:166). llama-server's OpenAI-compatible endpoint expects `logit_bias` as an **array of `{id, bias}` objects** (OpenAI shape); the native `/completion` endpoint is the one that takes a map. A map sent to the OpenAI-compatible endpoint fails to parse into the expected vector and is silently dropped — which matches the README-declared symptom (banned words "non-functional rather than just hit-or-miss", README.md:264-265). The `/tokenize` usage itself (POST `{content}` → `{tokens}`, 06-state-sync.js:734, 765-772) matches the documented endpoint. The shape mismatch is the most likely root cause of mechanical P1-3; definitive confirmation still needs a live capture against the pinned build (q-logit-bias-root-cause). | medium | strong inference | fix before porting | P17 (`/tokenize` + `logit_bias`) "Required fields" — "`logit_bias` = map of token-id **strings** → strength" (protocols-and-state.md); contracts "Banned words (logit bias)" — Observable output + the README-declared non-functional note; mechanical P1-3. |
| 3 | chat.html:165-166; js/04-state.js:59; js/15-cards.js:35 | **Closes contracts-CF1.** The CONFIG UI exposes "Reminder every N msgs" (`reminderFrequency`) and `saveSettings` persists it (15-cards.js:35), but no code path consumes it: personality became a persistent context block (08-rag.js:912-913: "The old periodic personality reminder is gone — personality is now a persistent block up top"; 13-dashboard.js:710-711 mirrors the accounting). The setting is a dead UI control — a UI-contract violation (control promises an effect that no longer exists). | low | observed fact | port differently | Contracts "Configuration Model" — "Vestigial setting (contracts-CF1)"; Doc/Test Conflicts #5 (chat.html:165-166 vs 08-rag.js:912, 13-dashboard.js:711). |
| 4 | README.md:317 vs js/07-prompt.js:262-268, js/09-threads.js:172-175 | **Closes contracts-CF2.** README claims "Lorebook + RAG lorebook work together to auto-update new information from extended conversations." The code never does this: compression writes only `thread.lore` (the running summary — `setThreadLore`, 07-prompt.js:266-268), and card lorebooks (`startingLore`, `ragStorybook`) are never auto-updated by any path; thread creation explicitly keeps authored lore on the card and the summary in the thread (09-threads.js:172-175). Both features exist and work separately; the claimed *combination* (auto-updating card lorebooks from conversations) does not exist. Doc/behavior drift; which side is intended needs the maintainer (post-lorebook-claim-ruling). | low | observed fact | fix before porting | README.md:317 (feature list); contracts Doc/Test Conflicts #3; contracts "Memory + summarization (lore compression)" — Persisted state ("`thread.lore` (running summary only — authored lore stays on the card)"). |
| 5 | js/07-prompt.js:260 | Stale in-code comment: "Keeps last 40 messages verbatim, everything else → lore." The implementation is token-driven — "Message counts are never used as thresholds" (08-rag.js:518-531). The comment misdocuments the compression trigger for any future maintainer. | low | observed fact | leave behind | Contracts Doc/Test Conflicts #7; contracts "Memory + summarization (lore compression)" — Trigger or input (token-budget driven). |
| 6 | js/16-card-io.js:25 | Stale in-code comment: "personality → personality (periodic reminder)". Personality is injected persistently on every turn, not on a cadence (08-rag.js:667-670). Same class as #5 — the import-mapping comment misdocuments the field's runtime behavior. | low | observed fact | leave behind | Contracts Doc/Test Conflicts #8; contracts "User personas" / "Memory + summarization" (persistent personality block). |
| 7 | README.md:345 vs js/18-utils.js:534-547 | README claims "Save AI output as a `.txt` or `.json` file. (Other file types are intentionally left out…)". `downloadFile` downloads whatever filename the model wrote in a ` ```file:` block — no extension restriction exists in code; the restriction is prompt-level only (the default card instructs the model, 04-state.js:16). A model that emits ` ```file:evil.exe ` produces a working download button. Cosmetic doc/code drift (the model is the only filename source), but the README states a safety property the code doesn't enforce. | low | observed fact | port differently | Contracts Doc/Test Conflicts #4; contracts "Save AI output as a file" — Evidence level note ("README claims only .txt/.json are supported but the code does not restrict the extension"). |

---

## Summary

### Findings by Severity

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 8 |
| Low | 9 |
| **Total** | **17** |

No critical or high severities were assigned: every semantic finding is a silent degradation, an edge-case failure, a defense-in-depth gap, or a documented design choice with residual risk. Nothing found breaks normal single-user operation outright (consistent with the mechanical phase's D004 discipline).

### Findings by Pass

| Pass | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| 3. Concurrency and resources | 0 | 0 | 2 | 0 | 2 |
| 4. Security and trust | 0 | 0 | 4 | 4 | 8 |
| 5. API contract violations | 0 | 0 | 2 | 5 | 7 |

### Top Findings

1. **Pass 4 #1** (medium, observed fact) — README's search-privacy claim ("identifying metadata and telemetry are stripped") is false: `privacyFetch` is a bare passthrough and the proxy forwards body + Authorization verbatim to ollama.com. **fix before porting.**
2. **Pass 3 #1** (medium, observed fact) — `/state` is unconditional last-write-wins with no server-side conflict check; concurrent two-device writes silently clobber. **port differently.**
3. **Pass 5 #1** (medium, observed fact) — Mid-generation session expiry (401) cancels the still-running job via the DELETE-ack path while the error message promises re-attachment. **fix before porting.**
4. **Pass 5 #2** (medium, strong inference) — `logit_bias` sent as a map of string keys where llama-server's OpenAI-compatible endpoint expects an array of `{id, bias}` — the likely root cause of the README-declared broken banned-words feature. **fix before porting.**
5. **Pass 4 #2** (medium, observed fact) — No rate limiting or lockout on `POST /login`; on-LAN brute force with no backoff. **fix before porting.**

### Carry-Forward Closure

All nine carry_forward entries routed to `defect-scan-semantic` are closed by the findings above; the ids are recorded in the phase handoff's `carry_forward_closures` so completion removes them atomically.

| ID | Source Phase | Closed Because |
|----|--------------|---------------|
| arch-CF5 | architecture | Assessed under pass 4: search-privacy claim → finding 4.1 (medium, fix before porting); plain-HTTP transport → 4.6 (documented design choice, residual risk); unsandboxed card code/extensions → 4.7 (documented design choice, residual risk). |
| mech-CF1 | defect-scan-mechanical | Assessed under pass 3 → finding 3.1 (medium, observed fact, port differently). |
| mech-CF2 | defect-scan-mechanical | Assessed under pass 4: (a) body-size caps → 4.3; (b) static exposure of models/*.gguf → 4.4; (c) API-key console log → 4.5 (folds into arch-CF5's search-privacy item, 4.1). |
| mech-CF3 | defect-scan-mechanical | Assessed under pass 5 → finding 5.2 (logit_bias map-of-strings vs array-of-{id,bias} shape mismatch, strong inference; runtime confirmation remains q-logit-bias-root-cause). |
| contracts-CF1 | contracts | Assessed under pass 5 → finding 5.3 (vestigial reminderFrequency UI, low, port differently). |
| contracts-CF2 | contracts | Assessed under pass 5 → finding 5.4 (README lorebook auto-update claim vs thread.lore-only compression, low, fix before porting; maintainer ruling tracked post-pipeline as post-lorebook-claim-ruling). |
| contracts-CF3 | contracts | Assessed under pass 4 → finding 4.2 (no login rate limiting, medium, fix before porting). |
| proto-CF1 | protocols | Assessed under pass 5 → finding 5.1 (401 mid-generation cancels live job + misleading re-attach message, medium, fix before porting). |
| proto-CF2 | protocols | Assessed under pass 3 → finding 3.2 (lazy swap promotion + orphaned lock stands the monitor loop down indefinitely, medium, fix before porting). |

---

## Coverage and limits

- **Inspected scope:** fileserver.ps1 (auth 78-127, 239-316; login page 318-358; static resolution 360-385; proxy 387-497; /state 499-567; jobs 569-967; swap helpers 1140-1269; swap handlers 1270-1445; dispatch loop 1447-1618); js/03-generation.js (330-517: job transport, poll, outcome handling); js/06-state-sync.js (60-110 sync scheduling, 700-819 logit bias); js/11-search.js (1-60); js/02-model.js (1-60, 330-466: loadActiveModel, swap client); js/08-rag.js (660-684, 895-934: personality/lore blocks); js/13-dashboard.js (128-247 renderMessages, 700-729 context meter); js/12-render.js (grep-level: escapeHtml usage); js/18-utils.js (100-170 escapeHtml/parseSearchData, 530-548 downloadFile); js/15-cards.js (9-48 settings); js/04-state.js (50-79 defaults); js/07-prompt.js (255-284 lore); js/09-threads.js (165-185 thread creation); js/10-chat.js (155-184 request body); js/16-card-io.js (15-34 mapping comments); js/19-extensions.js (1-30, 220-231); js/23-card-code.js (15-49); chat.html (155-180 CONFIG modal); launch.bat (1175-1219 metadata writers, 1839-1895 monitor loop); README.md (255-268 known bugs, 310-357 feature list). Upstream findings (architecture map, behavioral contracts, protocols-and-state, mechanical defects) read in full as the spec basis.
- **Skipped scope:** css/*; hardware-probe.ps1; identify-model.ps1 bodies; setup-lan.bat; js/14-scroll.js, 17-personas.js, 20-macros.js, 21-data.js, 22-scheduler.js, 24-boot.js bodies; js/03-generation.js thinking-parser internals (518-1120); js/05-persistence.js migration bodies; js/08-rag.js retriever internals; launch.bat download-menu bodies (500-1590); fileserver.ps1 Build-LaunchScript internals (1011-1111). These were covered by earlier phases (architecture/contracts/protocols/mechanical) and their contracts were checked against the code paths this phase did read.
- **Evidence basis:** source inspection only, cross-checked against the contracts and protocols outputs (which serve as the spec for pass 5). No runtime verification possible (Windows-only; not executable in this environment), no tests in repo, no CI, no upstream findings beyond the README's own known-bugs section.
- **Known blind spots:** (1) definitive root cause of the logit-bias breakage needs a live capture against the pinned llama-server build (q-logit-bias-root-cause — finding 5.2 is a strong inference, not a proof); (2) behavior of the synchronous accept loop under multiple concurrent LAN clients is unmeasured (q-accept-loop-scale); (3) the Ollama web_search upstream schema beyond `{results:[{title,content,url}]}` is invisible in-repo (q-ollama-api-version, q-websearch-response-fields); (4) SSE terminal bytes of the pinned build (q-sse-done-marker); (5) `/props` and `/apply-template` response shapes (q-llama-server-diag-endpoints); (6) Tekken patch completeness (q-tekken-patch-completeness); (7) installer binaries, REFACTOR-PLAN.md, and the fonts/ directory remain absent (q-installer-packaging, q-refactor-plan, q-font-shipping).
- **Coverage disposition:** COMPLETE — all three semantic passes produced findings, all nine routed carry-forward items are assessed and closed, and the remaining unknowns are runtime-test questions already tracked as open questions, not source gaps.

## Validation

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | All three semantic passes (3, 4, 5) produced findings or documented "no defects found." | PASS | §Pass 3 (2 findings), §Pass 4 (8 findings), §Pass 5 (7 findings) — all three passes produced findings. |
| 2 | Each finding has location, severity, evidence level, and recommended action. | PASS | Every row in the three pass tables carries Location, Defect, Evidence, Severity, Evidence Level, and Action columns (pass 5 adds Spec Reference). |
| 3 | Pass 5 findings cite the contract or protocol reference they violate. | PASS | Every pass-5 row's Spec Reference cell names the protocol entry (P5, P17), state-machine row (SM1), and/or contracts section (Doc/Test Conflicts #3-#8, Configuration Model, feature contracts) it violates. |
| 4 | Findings are organized by pass and sorted by severity; summary tables match the detailed findings. | PASS | One section per pass, medium findings precede low within each pass. §Summary: 17 total = 2 (P3) + 8 (P4) + 7 (P5); severity counts 0/0/8/9 match the detailed rows exactly. |
| 5 | Any carry_forward entries that targeted defect-scan-semantic have been resolved or explicitly re-routed. | PASS | §Carry-Forward Closure addresses all nine routed items (arch-CF5, mech-CF1, mech-CF2, mech-CF3, contracts-CF1, contracts-CF2, contracts-CF3, proto-CF1, proto-CF2), each mapped to a finding; all nine ids are recorded in the phase handoff's `carry_forward_closures`. None required re-routing. |
| 6 | Findings are marked with evidence levels. | PASS | Every finding carries `observed fact` or `strong inference` (finding 5.2, with the runtime confirmation explicitly deferred to q-logit-bias-root-cause). |
| 7 | Coverage and limits name inspected scope, skipped scope, evidence basis, and blind spots. | PASS | §Coverage and limits lists all four plus disposition (COMPLETE); blind spots map to the existing open questions. |

**Validated by:** defect-scan-semantic phase, delegated subagent session (2026-08-18)
**Overall:** PASS
