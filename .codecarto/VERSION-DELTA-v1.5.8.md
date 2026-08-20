# Version delta: findings re-verified against v1.5.8

**Status: targeted re-verification, NOT a completed pipeline phase.** No phase handoff was
written, no validation block appended, `workflow/status.yaml` untouched. The pipeline record still
reflects the 7/7 run against `5524fd4`. This document exists so nothing stale goes upstream.

- **Findings were produced against:** `5524fd4` (v1.5.1-era)
- **Current upstream:** `f1b9f50` (v1.5.8) — 2,025 insertions across 22 files
- **Re-verified:** 2026-08-20

## Why this was needed

`fileserver.ps1` grew by 405 lines and `launch.bat` by 368. Every line citation in the defect
scans had drifted by 120–350 lines. A maintainer clicking `fileserver.ps1:1497-1531` for the login
handler would land in unrelated code, and the whole report would read as careless.

## Citation drift

| Cited location | Old | Current | Note |
|---|---:|---:|---|
| `/login` handler | 1497–1531 | **1843** | Pass 4 #2 |
| `Resolve-StaticPath` | 363–385 | **491** | Pass 4 #4 |
| `Add-CommonHeaders` | 198–206 | **326** | Pass 4 #8 |
| `Handle-State` | 545–564 | **629** | Pass 3 #1, Pass 4 #3 |
| `Handle-Jobs` | 794–795 | **956** | Pass 4 #3 |
| `ReadToEnd()` sites | 547, 795 | **675, 896, 999, 1501, 1592, 1848** | Pass 4 #3 |
| `js/11-search.js:26` | 26 | **26** | unchanged — file not touched |
| `js/06-state-sync.js:774` | 774 | **774** | unchanged — file not touched |

## Status changes

| Finding | Status at v1.5.8 |
|---|---|
| mech **P1-2** — health probe misdetects Ollama as llama-server | **Headline fixed.** Default `SERVER_PORT` moved `11434` → `11437` (`launch.bat:134`), so the collision is now unlikely. The mechanism is unchanged: `:http_probe` still runs `curl.exe -s -o nul` with no `-f`, so any HTTP response including a 404 reads as healthy. Note `fileserver.ps1:49` still falls back to `11434` when `GEMMA_LLM_PORT` is unset, so a directly-started server can still land on Ollama. **Downgrade to low.** |
| mech **P6-1** — downloads unpinned | **Still valid.** `LLAMA_PIN_SHA256=` and `EMBED_PIN_SHA256=` are still empty (`launch.bat:359`, `:412`) though the verification path exists (`:706`). |
| mech **P1-3** — logit bias broken | **Still valid.** `logitBias[String(id)]` unchanged at `06-state-sync.js:774`, still merged into the OpenAI-compatible body at `10-chat.js:166`, still listed under Known Bugs. |
| sem **Pass 4 #1** — search privacy claim | **Overstated — corrected by runtime capture.** See `findings/runtime-egress-verification/`. The relay builds a fresh header set, so browser metadata *is* stripped before egress. Claim is true of metadata, false of content. |
| sem **Pass 4 #2** — no login rate limiting | **Still valid.** No rate-limit, lockout, or backoff machinery anywhere in the new `fileserver.ps1`. |
| sem **Pass 4 #3** — no request body size caps | **Still valid.** No `Content-Length` gate or 413 path; handlers still `ReadToEnd()` before validating. |
| sem **Pass 4 #4** — static serving exposes project root | **Still valid.** `Resolve-StaticPath` still rejects only traversal and dot-prefixed segments; no extension allowlist, no size cap. |
| sem **Pass 4 #5** — API key prefix logged to console | **Still valid, same line.** `js/11-search.js:26`. |
| sem **Pass 4 #6** — plaintext LAN transport | **Still valid, and now better documented upstream.** `SECURITY.md` is explicit about it. The residual gap is that neither `SECURITY.md` nor the README notes that the password itself crosses the LAN in cleartext at login — so a sniffer beats a guesser. `README.md`'s "never leaves your computer" still contradicts the sign-in page. |
| sem **Pass 4 #7** — unsandboxed card code / extensions | **Still valid, and now documented upstream.** `SECURITY.md` → "What this does not protect against" covers malicious cards. Still absent: that a URL-loaded **extension** is an outbound network path. `SECURITY.md` → "What leaves your machine" does not list it. |
| sem **Pass 4 #8** — wildcard CORS | **Still valid.** `Access-Control-Allow-Origin: *` with `Allow-Headers: Content-Type, Authorization` at `Add-CommonHeaders` (now `:326`). |

## Open questions closed or narrowed by runtime evidence

The runtime phase's captures answer two questions the static passes had to leave open.

- **`q-font-shipping` — narrowed.** The cold-boot capture shows the browser **does** request
  `GET /fonts/atkinson-hyperlegible.woff2` (referenced at `css/01-tokens.css:30`), and `fonts/` is
  absent from the repo, so it **404s in any git-clone install** and the page falls back. The font is
  not inlined. What remains unknown is only whether the packaged installer ships it — untestable
  without the installer.
- **`q-ollama-api-version` — narrowed.** The relay's outbound call was captured directly:
  `POST https://ollama.com/api/web_search`, headers `Authorization` + `Content-Type` only, body
  `{"query":…,"max_results":5}`, 30s timeout. The request half of the contract is now observed
  rather than inferred. The response schema remains unknown (the capture stubbed the reply, so
  `q-websearch-response-fields` stays open).

## Not covered by this delta

The 2,025 new lines have **not** been scanned for new defects. Unscanned surface:

- `SECURITY.md` (new, 110 lines) and `TROUBLESHOOTING.md` (new, 205 lines)
- dynamic port allocation — `GEMMA_LISTEN_PORT` → `.gobbonet-port` → `9066` (`fileserver.ps1:62-90`)
- `fileserver.ps1` +405, `launch.bat` +368, `chat.html` +268, `js/07-prompt.js` +263,
  `js/02-model.js` +174, `setup-lan.bat` +191
- the client-side egress results (R1, R2, R3, R8) were measured on `5524fd4` and not re-measured

A full re-run of `defect-scan-mechanical` and `defect-scan-semantic` against `f1b9f50` would cover
that surface and is the correct next step if these findings are going to be relied on as current.
