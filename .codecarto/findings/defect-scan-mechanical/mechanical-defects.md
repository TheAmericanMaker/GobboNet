# Mechanical Defects Report — GobboNet

<!--
  Output template for the `defect-scan-mechanical` phase.
  Covers passes 1, 2, and 6 from the defect-scan methodology — the bugs visible
  from local code reading without contracts or protocols context.
  See findings/defect-scan-mechanical/SKILL.md for instructions.
-->

## Scan Context

- **Source:** `../` (repository root)
- **Architecture reference:** `findings/architecture/architecture-map.md`
- **Pipeline:** workflow/pipeline-full-with-deep-audit.yaml
- **Date:** 2026-08-18
- **Scope:** Mechanical passes only (1 logic, 2 error handling, 6 configuration). Semantic passes (3 concurrency, 4 security, 5 contract violations) deferred to `defect-scan-semantic` after protocols.

---

## Pass 1: Logic and Correctness

| # | Location | Defect | Evidence | Severity | Evidence Level | Action |
|---|----------|--------|----------|----------|----------------|--------|
| 1 | launch.bat:1865 (monitor restart), fileserver.ps1:1125 (`Stop-LlamaServer`), launch.bat:1504-1505 | Both the crash-restart path and every hot-swap kill **all** processes named `llama-server.exe` — which includes the embedding server (launched as `llama-server.exe --embeddings`, launch.bat:1571) — and neither path restarts it. RAG semantic search silently degrades to tag-only after any chat-server crash or model swap, until the next full launch. | `taskkill /f /im llama-server.exe` (launch.bat:1865) and `Get-Process -Name 'llama-server'` (fileserver.ps1:1125) match by bare image name; the embed server is documented as outside the monitor/hot-swap loop (launch.bat:1504-1505); no embed respawn exists in `:monitor_loop` or `Handle-SwapModel`. | medium | observed fact | fix before porting |
| 2 | launch.bat:1951-1953 (`:http_probe`), 1965-1967 (`:http_health`), 1235-1238, 1842 | Health/probe checks accept **any** HTTP response (curl without `--fail`) or any body containing the substring "ok" — a foreign service on the port (Ollama, which the README itself documents as a common port-grabber, README.md:244-245) is misdetected as a healthy llama-server, and the launcher proceeds against the wrong backend. | `curl.exe -s -o nul "%~1"` returns exit 0 on 404/500; `findstr /i "ok"` matches substrings like "broken"; the "already running" branch (launch.bat:1236-1238) skips startup entirely on a false positive. | medium | observed fact | fix before porting |
| 3 | js/06-state-sync.js:725-793 (`buildLogitBias`), js/10-chat.js:161-166, README.md:264-265 | **Closes arch-CF4.** README-declared known bug: logit bias (banned words) is non-functional. The code path exists and is wired (tokenize via `/tokenize` → `logit_bias` map → merged into the request body), but the maintainer confirms the feature does not work. Root cause is not determinable from source alone. | README.md:264-265 declares the feature "non-functional rather than just hit-or-miss"; the full client path is visible at 06-state-sync.js:725-793 and 10-chat.js:161-166. Root cause: open question `q-logit-bias-root-cause`. | medium | observed fact (declaration + code path); root cause open question | fix before porting |
| 4 | identify-model.ps1:250-258, launch.bat:1335-1339, fileserver.ps1:1050-1072, README.md:267-268 | **Closes arch-CF4.** README-declared known bug: Tekken-tokenizer models misbehave; the applied patch (route to built-in C++ templates, normalize the unrecognized `mistral-v7-tekken` name) is declared "possibly not thorough enough". The patch's known delta is documented (trailing space after `[INST]`/`[SYSTEM_PROMPT]`, identify-model.ps1:246-249). | README.md:267-268: "We have identified the problem and applied a patch, but it may not be thorough enough"; the patch is present in three places (identify-model.ps1:250-258, launch.bat:1335-1339, fileserver.ps1:1050-1072). Completeness: open question `q-tekken-patch-completeness`. | medium | observed fact (patch present; README declares incompleteness) | fix before porting |
| 5 | js/02-model.js:42-47 (`loadActiveModel`) | `loadActiveModel` overwrites the user's token limit whenever it equals the default 24576 — a user who deliberately set 24576 gets it silently replaced with the model's `defaultCtx` (e.g. 16384 for gemma4-26b) and the change is persisted. | `if (tokInput && (!state.settings.tokenLimit || state.settings.tokenLimit === 24576))` then `state.settings.tokenLimit = activeModel.defaultCtx; saveState();` — the equality branch cannot distinguish "never customized" from "deliberately set to the default". | low | observed fact | port differently |
| 6 | launch.bat:1689 (`:get_lan_ip`) | LAN IP detection takes the first non-loopback IPv4 from `ipconfig` — on machines with VPN/virtual adapters (WSL, Hyper-V, Tailscale), the first match is often not the LAN adapter, so the phone URL shown is wrong. | `for /f ... in ('ipconfig ^| findstr /i "IPv4" ^| findstr /v "127.0.0.1"')` with `goto :got_ip` on the first match — first-match-wins with no adapter filtering. Wrong-IP consequence is strong inference. | low | observed fact (first-match-wins); consequence strong inference | leave behind |

---

## Pass 2: Error Handling and Resilience

| # | Location | Defect | Evidence | Severity | Evidence Level | Action |
|---|----------|--------|----------|----------|----------------|--------|
| 1 | fileserver.ps1:1603 (static handler), 1545 (favicon), 363-385 (`Resolve-StaticPath`) | Static file serving reads entire files into memory (`ReadAllBytes`) with no size cap and no extension allowlist; any large file under the project root — `models/*.gguf` files are the natural case, 4-20 GB — can exhaust the fileserver's memory and crash it. | `[System.IO.File]::ReadAllBytes($full)` with no size check; `Resolve-StaticPath` permits any non-dotfile under root, including `models/`. | medium | observed fact | port differently |
| 2 | js/08-rag.js:189-200 (`ragEmbedRaw`), js/11-search.js:45-52 | Client-side fetches to the embed server and search proxy have no timeout/AbortSignal — a wedged-but-listening upstream hangs the RAG path (which runs on the generation path via `buildContextMessages`) or the search UI indefinitely. In served mode the fileserver proxy bounds the hang at its 10-minute read timeout; file:// mode talks to loopback directly with no bound. | No `AbortSignal`/timeout in either `fetch`; proxy timeout at fileserver.ps1:420-421. | medium | observed fact | port differently |
| 3 | launch.bat:1941 (`:http_get` PowerShell fallback) | The PowerShell download fallback (used when curl is missing) sets no explicit timeout — it relies on .NET `WebClient` defaults (100s request / 300s read-write), so a stalled or slow connection aborts or hangs the launcher with no progress feedback. | `$w.DownloadFile($env:GN_URL, $env:GN_OUT)` with no `Timeout`/`ReadWriteTimeout` assignment. | low | observed fact | leave behind |
| 4 | fileserver.ps1:420-421 vs 689-690 | The legacy direct-stream proxy path uses a 10-minute read timeout while the detached-job worker uses 30 minutes — long prompt processing (large contexts on CPU) can exceed 10 minutes of silence and abort a direct-stream generation that the job path would have survived. | `$req.Timeout = 600000; $req.ReadWriteTimeout = 600000` in `Invoke-Proxy` vs `1800000` in the job worker. | low | observed fact | port differently |
| 5 | launch.bat:1674-1677, 1826 | When the fileserver fails to start, the launcher prints "Desktop chat still works normally" and opens the browser to `http://127.0.0.1:8080` — but desktop chat is served by that same fileserver, so the browser lands on a dead port and the message is wrong. | The fallback message at 1674-1677 and the unconditional `start "" "http://127.0.0.1:8080"` at 1826. | low | observed fact | leave behind |

---

## Pass 6: Configuration and Environment Hazards

| # | Location | Defect | Evidence | Severity | Evidence Level | Action |
|---|----------|--------|----------|----------|----------------|--------|
| 1 | launch.bat:244, 288, 585, 1535 | **Closes arch-CF3.** `LLAMA_PIN_SHA256` and `EMBED_PIN_SHA256` ship empty, so on every fresh install the engine zip and the embedding GGUF are downloaded with no hash verification (HTTPS + pinned tag only); the script prints the hash and asks the user to paste it back. Model downloads are verified against HF LFS pointers (launch.bat:1094-1127), so the gap is the engine and embed files. | `set "LLAMA_PIN_SHA256="` (244) and `set "EMBED_PIN_SHA256="` (288); `if not defined LLAMA_PIN_SHA256 goto :llama_hash_unpinned` (585) and the equivalent embed branch (1535) skip verification. | medium | observed fact | fix before porting |
| 2 | launch.bat:909-1027 (per-model `CTX_SIZE`/`KV_CACHE_TYPE`), identify-model.ps1:181-184 (record shape), fileserver.ps1:1079-1082 (`Build-LaunchScript`) | **Closes arch-CF3.** Per-model `CTX_SIZE`/`KV_CACHE_TYPE` overrides exist only in the download menu and are not persisted anywhere: `models-list.json` records carry no ctx/kv fields, so hot-swaps use the boot-time `GEMMA_CTX_SIZE`/`GEMMA_KV_CACHE_TYPE` for every model; and the same model runs with a different KV cache type on its first run (menu override, e.g. `f16` for choice 1) vs later launches (header default `q8_0`). | The menu sets `CTX_SIZE`/`KV_CACHE_TYPE` per choice (e.g. 909-920, 957-968); the identify-model.ps1 record (181-184) has no such fields; `Build-LaunchScript` uses `$CtxSize`/`$KvCacheType` for all swaps (1079-1082). | medium | observed fact | fix before porting |
| 3 | launch.bat:404-409 vs fileserver.ps1:99 | **Closes arch-CF3.** The batch-only password-file check accepts any "something:something" while the PowerShell consumer requires `^([0-9a-fA-F]+):([0-9a-fA-F]+)$`. The looseness is deliberate and documented (launch.bat:405-408), and the batch path is only reachable when PowerShell is absent — in which case the PowerShell consumer cannot run anyway — so the practical risk is nil; it is a latent inconsistency, not an active bug. | Both checks read; the comment at 405-408 explains the deliberate looseness ("a validator that is stricter than its consumer rejects working configurations"). | low | observed fact | leave behind |
| 4 | fileserver.ps1:54, launch.bat:1636-1640 | The listen port is hardcoded to 8080 with no env override, and the "already running" probe accepts any HTTP responder — a foreign service on 8080 is misdetected as GobboNet's fileserver and the launcher proceeds against it. | `$ListenPort = 8080` (fileserver.ps1:54); the probe at launch.bat:1636 is the same any-response check as finding P1-2. | low | observed fact | port differently |
| 5 | launch.bat:32-77, 1900-1906; fileserver.ps1:1452-1453; setup-lan.bat:47-154 | The entire orchestration stack is Windows-coupled by design (System32 curl/certutil/tar, tasklist/taskkill, netsh, PowerShell HttpListener + runspaces, P/Invoke console control) — documented as Windows-only, but any port must replace launch.bat, fileserver.ps1, and setup-lan.bat wholesale. | Tool usage throughout the cited ranges; README declares Windows-only. | low | observed fact | port differently |
| 6 | launch.bat:728, 777, 1218 | GGUF paths are interpolated into PowerShell command lines from batch variables — a model filename containing `&`, `%`, `^`, or `!` breaks the identify-model/hardware-probe invocations (the class of problem convention C02's env-var handoff exists to avoid). | `-GgufPath "!GGUF_PATH!"` style interpolation at all three sites (728, 777, 1218). | low | observed fact | leave behind |

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

### Findings by Pass

| Pass | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| 1. Logic and correctness | 0 | 0 | 4 | 2 | 6 |
| 2. Error handling | 0 | 0 | 2 | 3 | 5 |
| 6. Config and environment | 0 | 0 | 2 | 4 | 6 |

### Top Findings

1. **P1-1** (medium, observed fact) — Hot-swap and crash-restart kill the embedding server by bare image name and never restart it; RAG semantic search silently degrades after every swap. **fix before porting.**
2. **P1-2** (medium, observed fact) — Any-response/substring health probes misdetect foreign services (Ollama) as healthy llama-server; the launcher proceeds against the wrong backend. **fix before porting.**
3. **P6-1** (medium, observed fact) — Engine and embedding downloads ship unpinned (empty SHA-256); fresh installs verify nothing beyond HTTPS + pinned tag. **fix before porting.**
4. **P6-2** (medium, observed fact) — Per-model CTX_SIZE/KV_CACHE_TYPE overrides live only in the download menu; hot-swaps and later launches ignore them, so the same model runs with different settings run to run. **fix before porting.**
5. **P1-3** (medium, observed fact + open question) — Logit bias (banned words) is README-declared broken; code path located, root cause needs runtime/contract confirmation. **fix before porting.**
6. **P1-4** (medium, observed fact + open question) — Tekken-tokenizer patch is README-declared possibly incomplete; patch located in three places, completeness needs runtime testing. **fix before porting.**

### Routed To Semantic Phase

| ID | Description | Why Routed |
|----|-------------|-----------|
| mech-CF1 | `/state` POST/PUT is unconditional last-write-wins with no server-side conflict check or locking (fileserver.ps1:545-564); concurrent writes from two devices silently clobber. | Concurrency is pass 3 of the semantic scan. |
| mech-CF2 | (a) No request-body size caps on `/state` POST/PUT (fileserver.ps1:546-547) or `/llm/jobs` POST (fileserver.ps1:794-795); (b) static serving exposes every non-dotfile under the project root to authenticated clients, including `models/*.gguf` (fileserver.ps1:363-385, 1597-1608); (c) `webSearch` logs the API key prefix to the console (11-search.js:26) — folds into arch-CF5's search-privacy item. | Security and trust boundaries are pass 4 of the semantic scan. |
| mech-CF3 | The client's `logit_bias` request shape (map of token-id strings, 06-state-sync.js:774) and its `/tokenize` usage (06-state-sync.js:734) should be compared against the contracts phase's llama-server API documentation — a shape mismatch is the likely root cause of the README-declared broken logit bias (P1-3). | Contract drift is pass 5 of the semantic scan, which runs after contracts/protocols. |

---

## Coverage and limits

- **Inspected scope:** full reads of launch.bat (1973 lines), fileserver.ps1 (1618), identify-model.ps1 (477), setup-lan.bat (178), js/11-search.js (222), js/23-card-code.js (313); partial reads of hardware-probe.ps1 (1-200 of 1961: header, schema, exit codes), js/01-config.js (1-120 of 170), js/02-model.js (1-200, 370-466 of 466), js/03-generation.js (1-500 of 1120), js/04-state.js (1-120 of 227), js/05-persistence.js (1-450 of 667), js/06-state-sync.js (1-300, 700-819 of 854), js/08-rag.js (1-200 of 961), js/10-chat.js (130-209 of 996), js/16-card-io.js (1-200 of 737), js/19-extensions.js (1-200 of 249), js/24-boot.js (1-120 of 154); README.md (240-299: troubleshooting + known bugs).
- **Skipped scope:** chat.html (structure covered by the architecture phase; behavior lives in the split JS files), css/*, js/07-prompt.js, 09-threads.js, 12-render.js, 13-dashboard.js, 14-scroll.js, 15-cards.js, 17-personas.js, 18-utils.js, 20-macros.js, 21-data.js, 22-*.js, default-characters.json, .gitignore; hardware-probe.ps1 detection layers (201-1961); the encoded search-proxy command (launch.bat:1608) was not fully decoded.
- **Evidence basis:** source inspection only. No runtime verification (Windows-only; not executable in this environment), no tests in repo, no CI, no upstream findings beyond the README's own known-bugs section.
- **Known blind spots:** (1) root cause of the logit-bias breakage (`q-logit-bias-root-cause`); (2) Tekken patch completeness (`q-tekken-patch-completeness`); (3) unread JS files may contain additional mechanical defects; (4) the search proxy's upstream behavior is only visible through the encoded command.
- **Coverage disposition:** COMPLETE

## Validation

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | At least two of the three mechanical passes (1, 2, 6) produced findings or documented "no defects found." | PASS | All three passes produced findings: §Pass 1 (6), §Pass 2 (5), §Pass 6 (6). |
| 2 | Each finding has location, severity, evidence level, and recommended action. | PASS | Every row in the three pass tables carries Location, Defect, Evidence, Severity, Evidence Level, and Action columns. |
| 3 | Findings are organized by pass and sorted by severity. | PASS | One section per pass; within each pass, medium findings precede low findings. |
| 4 | Summary tables are complete and counts match the detailed findings. | PASS | §Summary: 17 total = 6 (P1) + 5 (P2) + 6 (P6); severity counts 0/0/8/9 match the detailed rows exactly. |
| 5 | Items spotted that are actually semantic in nature are routed onward via a carry_forward entry in the phase handoff targeting defect-scan-semantic. | PASS | §Routed To Semantic Phase lists mech-CF1, mech-CF2, mech-CF3; all three are recorded as `carry_forward` entries with `target_phase: defect-scan-semantic` in scratch/handoffs/defect-scan-mechanical.yaml. |
| 6 | Findings are marked with evidence levels. | PASS | Every finding carries `observed fact`, `strong inference`, or `open question` (with the observed-fact base named where a sub-claim is an open question). |
| 7 | Coverage and limits name inspected scope, skipped scope, evidence basis, and blind spots. | PASS | §Coverage and limits lists all four plus disposition (COMPLETE). |

**Validated by:** defect-scan-mechanical phase, delegated subagent session (2026-08-18)
**Overall:** PASS
