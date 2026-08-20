# Architecture Map

<!--
  Output template for the architecture phase.
  Evidence levels used throughout (per findings/architecture/SKILL.md):
  `observed fact` | `strong inference` | `portability hazard` | `open question`
-->

## System Intent

GobboNet is a Windows-only, fully-local AI chatbot frontend: a vanilla HTML/CSS/JS chat UI served by a PowerShell HTTP file server, talking to a local llama.cpp `llama-server` (OpenAI-compatible API) over loopback, all orchestrated by a cmd batch launcher. It is aimed at non-technical home users who want a private, account-free, offline chatbot with character personas, lorebooks, RAG retrieval, conversation branching, and optional LAN access from a phone. The only network calls are one-time downloads (engine, GGUF models, embedding model) and an opt-in web-search proxy to Ollama; everything else runs offline with zero telemetry (`observed fact`: README.md:3, README.md:195, chat.html:7, launch.bat:464). The repo is the complete source of the runtime; the installer binaries (`GobboNetSetup.exe`, `launch.exe`, `launchLAN.exe`) referenced by README.md:48,82,153 are not in the repo (`observed fact`: repo root listing).

## Layer Map

### Package Inventory

| Package / Module | Role | Public Entrypoints | Key Dependencies | Runtime Surface |
|---|---|---|---|---|
| `launch.bat` (1973 lines) | product shell / orchestration | `launch.bat [reset-password]` | curl.exe, certutil.exe, tar.exe, powershell.exe, tasklist/taskkill, ipconfig, ping, netsh (via setup-lan.bat) | Windows cmd console; spawns and supervises every other process |
| `setup-lan.bat` (178 lines) | product shell / one-time OS config | `setup-lan.bat` (admin) | netsh advfirewall, mDNS rules | Windows console, admin elevation |
| `fileserver.ps1` (1618 lines) | integration adapter / protocol layer | HTTP on `http://+:8080/` (see Public Surfaces) | .NET `System.Net.HttpListener`, runspaces, env vars from launch.bat, llama-server, search proxy, embed server | PowerShell process (hidden window), single-threaded accept loop + worker runspaces |
| search proxy (inline, encoded in launch.bat:1608) | integration adapter | HTTP on `127.0.0.1:11435` (`/health`, `/web_search`) | .NET HttpListener, `https://ollama.com/api` | PowerShell process (hidden window) |
| `hardware-probe.ps1` (1961 lines) | integration adapter / tooling | `-OutputPath <path> -ModelsDir <dir>` | WMI, registry, nvidia-smi, dxdiag, Win32_VideoController | PowerShell, run by launch.bat at model-menu time |
| `identify-model.ps1` (477 lines) | protocol or normalization layer | `-GgufPath <p> -Emit json\|batch -ModelsDir <d> -Active <f> -OutFile <f>` | GGUF binary format (v2/v3), filesystem | PowerShell, run by launch.bat at boot and hot-swap |
| `llama-server.exe` (external, downloaded) | core semantics (inference engine) | OpenAI-compatible HTTP on `127.0.0.1:11434` (`/v1/chat/completions`, `/health`); second instance `--embeddings` on `127.0.0.1:11436` | GGUF model files, Vulkan/CUDA/CPU backends | Native Windows process, `--parallel 1` |
| `chat.html` (906 lines) | UI or rendering / product shell (DOM) | loaded at `/` (fileserver) or `file://` | css/01–15, js/01–24, `default-characters.json` | Browser tab (desktop + phone) |
| `js/01-config.js` … `js/24-boot.js` (~11k lines) | UI or rendering + persistence or state + protocol or normalization (client side) | global functions/consts; no module system | browser APIs (fetch, IndexedDB, localStorage, sendBeacon, Page Lifecycle), fileserver routes | Browser JS event loop |
| `css/01-tokens.css` … `css/15-lore-view.css` | UI or rendering (styling) | cascade, loaded in numbered order | `fonts/atkinson-hyperlegible.woff2` (referenced, absent from repo) | Browser renderer |
| `default-characters.json` (68 lines) | persistence or state (seed data) | fetched at boot by 24-boot.js | — | static file served by fileserver |

### Dependency Direction

The stable base is the **browser frontend's config/state pair** (`js/01-config.js` constants + `js/04-state.js` state shape) — nothing else in the repo depends on them, and every other JS file reads them (`observed fact`: 01-config.js:25-26 defines `IS_SERVED`/`LLAMA_URL`; 02-model.js:382,391 derives `SEARCH_PROXY_URL`/`EMBED_URL` from `IS_SERVED`; 04-state.js:183 defines the global `state` object).

Dependency flow, top to bottom (`strong inference` from load order and call sites):

1. **`launch.bat` → everything.** It spawns llama-server, the embed server, the search proxy, and fileserver.ps1; it writes `active-model.json` (launch.bat:1180-1192) and `models-list.json` (launch.bat:1214-1221) that the frontend reads; it passes configuration to fileserver.ps1 exclusively via `GEMMA_*` environment variables (launch.bat:1651-1667, fileserver.ps1:29-32).
2. **`fileserver.ps1` → upstream services.** It reverse-proxies `/llm/*` → llama-server, `/search/*` → search proxy, `/embed/*` → embed server (fileserver.ps1:1584-1596); it owns `/state`, `/llm/jobs*`, `/swap-model`, `/swap-status` itself.
3. **`chat.html`/js → fileserver (same-origin) or localhost (file://).** `IS_SERVED` switches every endpoint between `window.location.origin + '/llm'` and `http://127.0.0.1:11434` (01-config.js:25-26). In file:// mode there is no auth, no `/state` sync, and no jobs relay — the client falls back to a legacy direct stream (03-generation.js:31-34, 06-state-sync.js:22-25).
4. **JS internal: linear numbered load order, global namespace.** Each file's header states "Load order is a contract" (`observed fact`: every js/*.js header). There is no module system; files reference each other's globals freely (e.g. 10-chat.js calls `renderMessages()` from 12-render.js; 08-rag.js's `buildContextMessages` is the single RAG injection seam used by 10-chat.js). `24-boot.js` is the entry point — an async IIFE that awaits `loadState()` before first render (24-boot.js:20-76).
5. **CSS: cascade order 01→15.** 13-components.css is the former inline `<style>` block and "loads last, as it did before"; 14-card-code.css and 15-lore-view.css are hand-written and load after every generated stylesheet so their rules win (`observed fact`: css/13-components.css:1-4, css/14-card-code.css:1-5).

**Cycles:** none structural. The only cross-process coordination loops are intentional: fileserver.ps1 and launch.bat's monitor loop coordinate hot-swaps through the `.swap-in-progress` lock file (fileserver.ps1:23-27, launch.bat:1845-1858), and both may rewrite `.llama-launch.cmd` (launch.bat:246-252).

**Wrappers around shared internals:** `identify-model.ps1` is the declared "single source of truth for model identification", shared by the initial launch and the hot-swap dropdown so they "can never disagree" (`observed fact`: identify-model.ps1:3, launch.bat:699-702, 1212). The search proxy is a thin path-forwarder to `https://ollama.com/api` (`observed fact`: decoded launch.bat:1608 encoded command).

## Public Surfaces

Full inventory lives in `findings/public-surfaces/public-surfaces.md` (2026-08-18 section). Summary of the load-bearing surfaces:

- **CLI / scripts:** `launch.bat [reset-password]` (the only user-facing command; `reset-password` deletes `.gobbonet-secret`, launch.bat:144-148); `setup-lan.bat` (admin, one-time firewall + mDNS); `hardware-probe.ps1` and `identify-model.ps1` (invoked by launch.bat, not users); `fileserver.ps1` (env-configured, spawned hidden).
- **HTTP (fileserver, port 8080, password-gated):** `GET /` → chat.html; static file serving with traversal + dotfile guards (fileserver.ps1:363-385); `GET/POST /login`, `GET /logout`, `GET /favicon.ico` (unauthenticated, fileserver.ps1:1497-1551); `GET /health-fileserver`; `GET/POST/PUT /state`, `GET /state/info`; `POST /swap-model`, `GET /swap-status`; `POST /llm/jobs`, `GET /llm/jobs/<id>?from=N`; proxies `/llm/*`, `/search/*`, `/embed/*`. Auth: salted SHA-256 password → HttpOnly session cookie (12h TTL) bound to a client fingerprint (fileserver.ps1:78-127, 259-316).
- **Upstream APIs consumed:** llama-server OpenAI-compatible `/v1/chat/completions` (SSE streaming) and `/health` (03-generation.js:473, 11-search.js:199); embed server `/v1/embeddings` (08-rag.js:189); Ollama `web_search` via the search proxy (11-search.js:45).
- **File formats:** GGUF v2/v3 metadata (identify-model.ps1:18-61); character cards V1/V2/V3 as `.json`, `.png` (tEXt chunk `ccv3`/`chara`), `.charx` ZIP (16-card-io.js:1-15); `default-characters.json`; `active-model.json`; `models-list.json`; `hardware.json`; `.gobbonet-state.json`; `.gobbonet-secret` (`salt:hash`); `.swap-status.json`; `.jobs/<id>.{sse,json,cancel}`; export/import JSON bundles (21-data.js).
- **User-facing screens:** chat screen (sidebar, thread list, messages, input, model selector), landing dashboard, login page, and seven modals: settings, characters, scheduler, extensions, data manager, lore inspector, about (`observed fact`: chat.html:126,225,611,661,753,819,835).

## Runtime Lifecycle

Full sequence in `findings/runtime-lifecycle/runtime-lifecycle.md` (2026-08-18 section). Summary:

- **Host boot (launch.bat):** keep-open guard relaunch under `cmd /k` (launch.bat:11-15) → preflight probes of curl/powershell/certutil/tar + Wine detection (launch.bat:32-77) → first-run password setup (salted SHA-256, plaintext never in env, launch.bat:310-362) → engine check/download (pinned tag `b9294`, SHA-256 verified, launch.bat:232-244, 558-576) → model check/menu (hardware probe → recommended pick, launch.bat:749-807) → `:identify_model` (GGUF chat-template ground truth, launch.bat:710-744) → write `active-model.json` + `models-list.json` → `:start_server` (writes `.llama-launch.cmd`, spawns llama-server, waits on `/health` with fast-fail + 10-min cap, launch.bat:1381-1440) → `:verify_gpu` (log grep, launch.bat:1447-1496) → `:start_embed` (optional, degrade-safe, launch.bat:1507-1557) → `:start_proxy` (search proxy, launch.bat:1599-1622) → `:launch` (fileserver.ps1 with `GEMMA_*` env, launch.bat:1627-1682) → LAN IP + mDNS detection + IP-change warning (launch.bat:1687-1758) → open browser → minimize → `:monitor_loop` (15s `/health` poll; kill+restart on death; stands down while `.swap-in-progress` exists, launch.bat:1839-1895).
- **Browser boot (24-boot.js):** async IIFE: `loadState()` (IndexedDB open/migrate) → `checkServerStateOnBoot()` (conflict check vs `/state/info`) → resume pending generation jobs → fetch `default-characters.json` → `render()` → timers (5s connection check, 30s scheduler) → page-lifecycle handlers (visibilitychange/pagehide/pageshow/focus/online) for save-on-exit and wake-resume (24-boot.js:20-154).
- **Generation lifecycle:** `sendMessage` → `buildContextMessages` (RAG injection seam) → `POST /llm/jobs` (server spools raw SSE to `.jobs/<id>.sse`; client polls `?from=N`) or legacy direct stream on file:///old servers (03-generation.js:8-34, 471-475) → SSE parse → render; CoT watchdog auto-stop; Stop button cancels via `.jobs/<id>.cancel` (10-chat.js:291-298, fileserver.ps1:730).
- **Hot-swap:** `POST /swap-model` → lock file → kill llama-server → rewrite `.llama-launch.cmd` + `active-model.json` + `models-list.json` → spawn new server → 202; `GET /swap-status` promotes `starting`→`ready` on `/health`, errors on process death (>5s) or 180s timeout (fileserver.ps1:1270-1445).
- **Shutdown:** close launcher window / Ctrl+C. fileserver.ps1 has no explicit shutdown handler — it dies with the parent; job spools are swept by a 48h retention backstop or deleted on client ack (fileserver.ps1:74, 610-612). Boot-time hygiene removes stale swap lock/status files (fileserver.ps1:137-140, launch.bat:468-475).

## Concurrency Model

- **Frontend:** single-threaded browser event loop; one generation at a time (`isGenerating` global, 04-state.js:203); async/await + fetch; `setInterval` timers (5s health, 30s scheduler, auto-continue countdown — 24-boot.js:68-75, 09-threads.js:407); debounced (~2s) state-sync push; `sendBeacon` on pagehide (06-state-sync.js:78-190). `portability hazard`: relies on browser Page Lifecycle APIs (bfcache, visibilitychange, sendBeacon) — behavior differs across browsers and is absent in non-browser ports.
- **fileserver.ps1:** single-threaded `HttpListener` accept loop (fileserver.ps1:1471-1478); detached generation jobs run in **PowerShell runspaces** (worker runspaces, max 4 concurrent, 429 beyond — fileserver.ps1:75, 789-791); in-memory session hashtable; no timers — job housekeeping piggybacks on job traffic (fileserver.ps1:772-774). `portability hazard`: runspaces and HttpListener are .NET/Windows-specific; the accept loop is synchronous (one request at a time, streaming responses block the loop).
- **launch.bat:** sequential batch execution; monitor loop polls every 15s; cross-process coordination with fileserver via the `.swap-in-progress` lock file (launch.bat:1845-1858). `portability hazard`: cmd batch, `taskkill`/`tasklist`, `start /min`, console window manipulation via P/Invoke (launch.bat:1900-1906).
- **llama-server:** `--parallel 1` pins a single slot to avoid KV-cache slot churn between concurrent requests (launch.bat:1292-1299). `strong inference`: the whole system is designed around one generation at a time end-to-end.
- **Backpressure:** job concurrency cap (4) on the server; client-side token limits and CoT watchdog; no other rate limiting. `open question`: whether the synchronous accept loop degrades under multiple LAN clients has no evidence in-repo.

## Build and Packaging

Details in `findings/build-and-deploy/build-and-deploy.md` (2026-08-18 section). Summary:

- **No build step.** The frontend is plain files; the "build" is the numbered file split (headers note files were "Moved verbatim from chat.html" by a refactor-split.py that is not in the repo — `observed fact`: js/*.js headers; `open question`: REFACTOR-PLAN.md is referenced by every split header but absent from the repo).
- **Distribution:** GitHub Releases `GobboNetSetup.exe` (unsigned, per-user, no admin — README.md:48-52) or manual ZIP (README.md:60-82). Installer sources not in repo (`open question`).
- **Runtime downloads (one-time, verified):** llama.cpp pinned release zip (tag `b9294`, SHA-256 verified against GitHub API digest, launch.bat:232-244, 558-576); GGUF models from HuggingFace (LFS pointer SHA-256 verified via certutil, launch.bat:1080-1128); embedding model (nomic-embed-text, optional pin, launch.bat:278-288, 1522-1548). Downloads deliberately avoid PowerShell staging to dodge behavioral AV (launch.bat:536-557).
- **No CI/CD visible in the repo** (`observed fact`: no .github/workflows).
- **.gitignore** excludes secrets, models, engine binaries, logs, and runtime state (`.gitignore`:1-29).

## Porting Priorities

| Component | Priority | Rationale |
|---|---|---|
| llama-server integration (OpenAI-compatible API, SSE streaming, chat templates/--jinja, thinking-format parsing) | core | The entire product is a frontend for this API; every chat feature depends on it. |
| fileserver.ps1 (auth gate, reverse proxy, `/state` sync, `/llm/jobs` spool, hot-swap) | core | Owns the LAN surface, detached generation, and cross-device state; the client's served-mode behavior is built around it. |
| Frontend state model + persistence (IndexedDB schema, localStorage mirror, migrations) | core | All user data lives here; schema and migration behavior are load-bearing. |
| Chat core (threads, streaming render, edit/reroll/branch, prompt/context building) | core | The primary user workflow. |
| RAG dual retriever + lore compression | important | Major differentiator; degrade-safe by design, so not blocking for a first port. |
| Character cards V1/V2/V3 import/export, personas, macros, scheduler | important | Parity on major workflows; formats are documented in 16-card-io.js. |
| Data export/import/purge, extensions, per-card code | important | User-facing data portability and customization; card code is unsandboxed by design (23-card-code.js:20-24). |
| Model registry + identify-model.ps1 (GGUF parsing) | important | Needed for hot-swap and template correctness across model families. |
| hardware-probe.ps1, model download menu, GPU verification | optional | First-run convenience; a port can assume pre-placed models. |
| Search proxy (Ollama web_search) | optional | Opt-in feature; needs an external key. |
| launch.bat orchestration (keep-open guard, AV-avoidance, monitor loop) | incidental | Source-specific ergonomics; a port would replace it with its own supervisor. |

## Durable State

Full inventory in `findings/state-and-storage/state-and-storage.md` (2026-08-18 section). Summary:

- **Browser (per-origin):** IndexedDB `gobbonet-state` v2 — stores `meta` (settings, cards, personas, folders, macros), `threads` (keyPath `id`), `vectors` (RAG embedding cache), `telemetry` (05-persistence.js:20-54); localStorage `gobbonet_chat_state` mirror with legacy `gemma4_chat_state` migration (04-state.js:8-9, 05-persistence.js:357-392). `portability hazard`: per-origin storage means each LAN IP/hostname is a separate data silo — the `/state` server sync exists specifically to patch this (06-state-sync.js:1-25).
- **Server-side (project root):** `.gobbonet-secret` (salt:hash), `.gobbonet-state.json` (rolling backup), `.swap-status.json`, `.swap-in-progress` (lock), `.llama-launch.cmd`, `.embed-launch.cmd`, `.jobs/` (spool), `.last-lan-ip`, `active-model.json`, `models-list.json`, `hardware.json`, `llama-server.log`, `embed-server.log`.
- **Config:** launch.bat top-of-file variables (SERVER_PORT=11434, CTX_SIZE=16384, GPU_LAYERS=99, KV_CACHE_TYPE=q8_0, MODEL_*, EMBED_*, LLAMA_PIN_TAG/SHA256 — launch.bat:112-290); `GEMMA_*` env handoff to fileserver.ps1; user settings inside browser state (DEFAULT_SETTINGS, 04-state.js:57-81). Details in `findings/config-model/config-model.md`.

## Coverage and limits

- Inspected scope: README.md (full); chat.html (structure, modals, script/style load order); all 24 js/*.js headers + key bodies (01-config, 04-state, 24-boot in full; 02, 03, 05, 06, 07, 08, 09, 10, 11, 22 in part); all 15 css/*.css headers; launch.bat (preflight, password, main flow, model menu, identify, download, start server, embed, proxy, fileserver launch, LAN/mDNS, monitor loop, helpers — the large majority of the file); fileserver.ps1 (config, auth, state, jobs, swap, static resolution, proxy, dispatch loop); setup-lan.bat (firewall + mDNS); hardware-probe.ps1 (header, schema, exit codes); identify-model.ps1 (header, GGUF parsing); default-characters.json; .gitignore; LICENSE; git log.
- Skipped scope (deliberately, per GUIDE context budget): full bodies of 12-render, 13-dashboard, 14-scroll, 15-cards, 16-card-io, 17-personas, 18-utils, 19-extensions, 20-macros, 21-data, 23-card-code; remaining bodies of 02, 03, 05, 06, 07, 08, 09, 10, 11, 22; hardware-probe.ps1 detection layers (lines 200-1961); identify-model.ps1 family tables (lines 62-477); fileserver.ps1 proxy/job-worker internals (lines 395-498, 589-1266); css bodies. These are classified by header contract and will be deep-read by contracts/protocols/defect phases.
- Evidence basis: source inspection only. No runtime verification (Windows-only; not executable in this environment), no tests in repo, no upstream findings beyond the README's own known-bugs section.
- Known blind spots: (1) the installer binaries and their packaging are outside the repo; (2) `REFACTOR-PLAN.md` is referenced by every split header but absent from the repo; (3) `fonts/atkinson-hyperlegible.woff2` is referenced by css/01-tokens.css but the `fonts/` directory is absent (graceful fallback documented); (4) the Ollama `web_search` request/response schema is only visible through the encoded proxy, which forwards paths verbatim; (5) exact SSE spool byte format and `/llm/jobs` chunk framing were not extracted line-by-line (protocols phase territory).
- Coverage disposition: COMPLETE (the map is stable enough to explain where behavior lives, per SKILL.md's stop condition; deep bodies are routed to later phases).

## Open Questions

| ID | Kind | Description | Deferred Reason |
|---|---|---|---|
| q-installer-packaging | needs-maintainer-decision | `GobboNetSetup.exe`, `launch.exe`, `launchLAN.exe` are referenced by README but absent from the repo; installer internals (how it lays out files, registers Start Menu entries, uninstaller behavior) are unknown. | No later phase in this pipeline can close it; requires the maintainer or the release artifacts. |
| q-refactor-plan | needs-maintainer-decision | Every js/css split header says "see REFACTOR-PLAN.md before reordering" but the file is not in the repo. | Missing artifact; only the maintainer can supply it. |
| q-font-shipping | needs-maintainer-decision | `fonts/atkinson-hyperlegible.woff2` is referenced by css/01-tokens.css:30 but `fonts/` is absent from the repo; whether the installer ships it is unknown. | Not resolvable from source; cosmetic (documented fallback stack). |
| q-accept-loop-scale | needs-runtime-test | fileserver.ps1's synchronous `GetContext()` accept loop handles one request at a time; behavior under multiple concurrent LAN clients (phone + desktop + streaming) is unmeasured. | Requires live load testing against the running Windows service. |
| q-ollama-api-version | needs-runtime-test | The search proxy forwards to `https://ollama.com/api` + path; the exact `web_search` request/response contract and its stability are not pinned anywhere in-repo. | Requires a live capture against Ollama's API; wire-format extraction is also routed to protocols (arch-CF1). |

## Carry-Forward

| ID | Target Phase | Description | Deferred Reason |
|---|---|---|---|
| arch-CF1 | protocols | Wire formats: SSE spool byte format + `/llm/jobs` chunk framing (`chunk_b64`, `from`/`max` offsets), `/state` JSON schema + mtime protocol, swap-status phase machine, GGUF metadata fields consumed, character-card V1/V2/V3 field mapping, Ollama web_search schema. | Wire-format extraction is the protocols phase's rubric; the architecture phase only names the surfaces. |
| arch-CF2 | contracts | User-visible behavior contracts for the README feature list (streaming, reroll, branching, lore compression, macros, scheduler, hot-swap, data export/import, extensions) — triggers, defaults, outputs, side effects, error behavior. | The contracts phase owns black-box behavior recovery; the architecture map only locates where behavior lives. |
| arch-CF3 | defect-scan-mechanical | Config hazards: `LLAMA_PIN_SHA256` and `EMBED_PIN_SHA256` ship empty (downloads unpinned until first run, launch.bat:244,288); the batch-only password-file check is deliberately looser than the PowerShell consumer (launch.bat:404-409); CTX_SIZE/KV_CACHE_TYPE per-model overrides in the download menu can silently diverge from the header defaults. | Pass 6 (config and environment) is the mechanical scan's rubric. |
| arch-CF4 | defect-scan-mechanical | README-declared known bugs need location/severity/evidence treatment: logit bias broken (banned words non-functional, README.md:264-265) and Tekken-tokenizer models misbehaving with a possibly-incomplete patch (README.md:267-268). | Pass 1 (logic and correctness) is the mechanical scan's rubric. |
| arch-CF5 | defect-scan-semantic | Security posture: plain-HTTP LAN transport with password + 12h session TTL + client-fingerprint cookie binding (fileserver.ps1:78-127); unsandboxed per-card JS and extensions (23-card-code.js:20-24, chat.html:703-705); README's "identifying metadata and telemetry are stripped from your searches" claim (README.md:342) vs `privacyFetch` being a passthrough (02-model.js:398-400) and the proxy forwarding body+Authorization verbatim. | Passes 4 (security and trust) and 5 (API contract violations) are the semantic scan's rubric. |
| arch-CF6 | porting | Portability hazard inventory: PowerShell HttpListener + runspaces, cmd batch orchestration (taskkill/tasklist/start/netsh), browser storage + Page Lifecycle APIs, mDNS/.local origin stability, Windows-only System32 tooling, AV-avoidance download patterns. | The porting phase synthesizes hazards into a porting-oriented view. |

---

## Validation

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | The system intent is documented. | PASS | §System Intent (paragraph with cited facts). |
| 2 | The layer map and dependency direction are documented. | PASS | §Layer Map → Package Inventory (table) and Dependency Direction (numbered flow, cycles, wrappers). |
| 3 | Public surfaces are identified. | PASS | §Public Surfaces (CLI, HTTP routes, upstream APIs, file formats, screens) + full inventory in findings/public-surfaces/public-surfaces.md. |
| 4 | Runtime lifecycle, concurrency model, and porting priorities are summarized. | PASS | §Runtime Lifecycle, §Concurrency Model, §Porting Priorities (table). |
| 5 | Findings are marked with evidence levels. | PASS | Every conclusion carries `observed fact` / `strong inference` / `portability hazard` / `open question` with file:line citations. |
| 6 | Coverage and limits name inspected scope, skipped scope, evidence basis, and blind spots. | PASS | §Coverage and limits lists all four plus disposition (COMPLETE). |

**Validated by:** architecture phase, delegated subagent session (2026-08-18)
**Overall:** PASS
