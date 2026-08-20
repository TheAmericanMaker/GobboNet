# Reverse-Engineering Bundle — GobboNet

<!--
  Output for the `porting` phase (pipeline: workflow/pipeline-full-with-deep-audit.yaml).
  This is the pipeline's intentional compression boundary: `reimplementation-spec` starts
  from this one artifact and deep-reads upstream reports only on the triggers named in
  §Source Index. Evidence levels used throughout (per findings/porting/SKILL.md):
  `observed fact` | `strong inference` | `portability hazard` | `open question`.
  Upstream artifacts: AM = findings/architecture/architecture-map.md; BC = findings/contracts/
  behavioral-contracts.md; PS = findings/protocols/protocols-and-state.md; MD = findings/
  defect-scan-mechanical/mechanical-defects.md; SD = findings/defect-scan-semantic/semantic-defects.md.
-->

## System Summary

GobboNet is a Windows-only, fully-local AI chatbot frontend for non-technical home users: a vanilla HTML/CSS/JS chat UI served by a PowerShell HTTP file server, talking to a local llama.cpp `llama-server` (OpenAI-compatible API) over loopback, all orchestrated by a cmd batch launcher (`observed fact`: AM §System Intent). The product is a character-chat experience: character personas with system prompts, greetings, lorebooks, RAG retrieval, conversation branching and variants, macros, a scheduler, per-card JavaScript, extensions, and optional LAN access from a phone. The only network calls are one-time verified downloads (engine, GGUF models, embedding model) and an opt-in web-search proxy to Ollama; everything else runs offline with zero telemetry (`observed fact`: README.md:3,195; AM §System Intent).

The runtime is a five-process composition (`strong inference` from AM §Layer Map): (1) `launch.bat` — product shell/supervisor that provisions, downloads, spawns, and monitors everything; (2) `fileserver.ps1` — the sole LAN-facing process: password-gated HTTP server on :8080, reverse proxy to the three loopback services, `/state` rolling backup, detached generation-job spooler, and hot-swap controller; (3) `llama-server.exe` — the inference engine (chat on 11434, embeddings on 11436, `--parallel 1`); (4) a search proxy (11435) forwarding verbatim to `https://ollama.com/api`; (5) the browser frontend — 24 numbered JS files in one global namespace (load order is a declared contract, convention C01), which owns all user data in IndexedDB/localStorage and syncs a redacted copy to the server. The browser is the primary data owner; the server holds a rolling backup that patches the per-origin storage silo problem (`observed fact`: AM §Durable State, PS P4).

For a reimplementer the load-bearing shape is: **one generation at a time end-to-end** (client `isGenerating` + server `--parallel 1` + 4-worker job cap), **byte-stable detached generation** (server spools raw SSE to disk; client polls base64 chunks and replays deterministically), **degrade-safe RAG** (embed server down → tag-only retrieval, chat never blocks), and **advisory cross-device sync** (mtime-based boot decision matrix, last-write-wins server). All 34 defect findings are silent degradations, edge-case failures, or documented design choices — nothing breaks normal single-user operation (`observed fact`: MD/SD summaries, decisions D004/D011).

## Source Index

This bundle is the default compression boundary for `reimplementation-spec`. Deep-read an upstream report only when the trigger condition holds.

| Area | Canonical upstream section | Summary carried forward | Deep-read trigger |
|---|---|---|---|
| Architecture | AM §System Intent, §Layer Map, §Runtime Lifecycle, §Concurrency Model, §Porting Priorities, §Durable State | System intent, dependency direction, lifecycle, concurrency model, porting priorities | The spec needs the full package-inventory table (per-package runtime surfaces), the numbered dependency-flow narrative, or the complete boot/monitor sequence |
| Contracts | BC §Feature Contracts (55 sections), §High-Value Behaviors, §Security and Authorization, §Doc/Test Conflicts, §Black-Box Acceptance List | One row per contract in §Feature Contract Table; security model summary; 9 doc/code conflicts | An acceptance scenario needs omitted detail (exact defaults, error strings, side-effect ordering) for a specific contract; or the spec must cite a doc/code conflict verbatim |
| Protocols and state | PS §Event Catalog (P1–P18), §State Machine (SM1–SM5), §Persistent Schema Notes, §Compatibility Hazards | Load-bearing wire formats, state machines, and persistence schemas condensed in §Protocol and State Notes | The spec needs exact field lists, byte-level framing (chunk_b64 offsets), full transition tables, or the complete 19-row compatibility hazard table |
| Defects (mechanical) | MD §Pass 1/2/6 tables, §Summary, §Routed To Semantic Phase | All 17 findings in §Defect Synthesis with dispositions | The spec needs the full evidence chain (file:line citations) for a fix-before-porting item, or the mech-CF1..3 routing rationale |
| Defects (semantic) | SD §Pass 3/4/5 tables, §Carry-Forward Closure | All 17 findings in §Defect Synthesis with dispositions | The spec needs the pass-5 Spec Reference column (which contract/protocol each finding violates) or the nine-item carry-forward closure mapping |
| Public surfaces (secondary) | findings/public-surfaces/public-surfaces.md (2026-08-18 sections) | Surface summary in AM §Public Surfaces | The spec needs the full route/format inventory (every HTTP route, every file format) |
| Runtime lifecycle (secondary) | findings/runtime-lifecycle/runtime-lifecycle.md (2026-08-18 sections) | Lifecycle summary in AM §Runtime Lifecycle | The spec needs the full boot-to-shutdown sequence with per-step citations |
| State and storage (secondary) | findings/state-and-storage/state-and-storage.md (2026-08-18 sections) | Storage summary in AM §Durable State + PS §Persistent Schema Notes | The spec needs the complete storage inventory (every file, every IDB store, every migration) |
| Build and deploy (secondary) | findings/build-and-deploy/build-and-deploy.md (2026-08-18 sections) | Packaging summary in AM §Build and Packaging | The spec needs download/verification detail (pinned tag, hash flow, .part staging) |
| Config model (secondary) | findings/config-model/config-model.md (2026-08-18 sections) | Config summary in BC §Configuration Model + PS P13/P14 | The spec needs the full env-var matrix or config precedence chain |

## Layer Map With Ownership

Concept names per the porting SKILL — the target implementation must NOT mirror the source folder layout. Source packages are cited as ownership evidence, not as the layer identity.

| Layer / Module (concept) | Role | Owns (source packages) |
|---|---|---|
| **Product shell / supervisor** | Provisioning, first-run setup, verified downloads, process supervision, LAN config, shutdown | `launch.bat` (1973 lines), `setup-lan.bat` (178) |
| **Provider adapter** | Reverse proxy to llama-server/embed/search; detached generation-job spooler; hot-swap controller; auth gate; static serving | `fileserver.ps1` (1618); search proxy (encoded in launch.bat:1608); `llama-server.exe` (external, the provider itself) |
| **Message normalizer / model registry** | GGUF metadata parsing, chat-template registry, thinking-format parsers, SSE line parser, stop strings, sampler mapping, logit-bias builder | `identify-model.ps1` (477); client-side js/02-model.js, js/03-generation.js (parsers), js/06-state-sync.js (sampler/stop/logit-bias) |
| **Agent loop / conversation engine** | The chat turn pipeline: send → context build (RAG injection seam) → request → stream → render; threads, variants, branching, lore compression, auto-continue | js/07-prompt.js, js/08-rag.js, js/09-threads.js, js/10-chat.js |
| **Session store / persistence** | Browser state ownership (IndexedDB v2 + localStorage mirror + migrations), server `/state` rolling backup, sync protocol, job breadcrumbs | js/04-state.js, js/05-persistence.js, js/06-state-sync.js; fileserver.ps1 Handle-State |
| **Tool executor / extension runtime** | Per-card code hooks, extensions, macros, scheduler, data import/export | js/16-card-io.js, js/19-extensions.js, js/20-macros.js, js/21-data.js, js/22-scheduler.js, js/23-card-code.js |
| **Render loop / UI surface** | DOM rendering, modals, dashboard, styling | chat.html (906), js/12-render.js, js/13-dashboard.js, js/14-scroll.js, js/15-cards.js, js/17-personas.js, js/18-utils.js, js/24-boot.js (boot entry), css/01–15 |
| **Hardware probe (optional tooling)** | First-run hardware detection for model recommendations | `hardware-probe.ps1` (1961) |

Dependency direction (`strong inference`, AM §Layer Map): product shell → everything (spawns all processes, writes `active-model.json`/`models-list.json`, passes config via `GEMMA_*` env — convention C02); provider adapter → upstream services (proxies `/llm/*`→11434, `/search/*`→11435, `/embed/*`→11436; owns `/state`, `/llm/jobs*`, `/swap-*`); UI surface → provider adapter (same-origin) or loopback (file:// mode, switched by `IS_SERVED`); JS internal: linear numbered load order, global namespace, no module system; CSS cascade 01→15. No structural cycles; the only cross-process loops are the intentional hot-swap lock-file coordination and the monitor loop.

## Feature Contract Table

Synthesized from BC §Feature Contracts. Priorities per the porting SKILL tiers, anchored to AM §Porting Priorities where it exists. Defect refs carry the upstream disposition (fix before porting / port differently / leave behind).

**Count note (conflict surfaced):** the contracts phase's owner_notes and validation block claim 40 contracts (24 Web UI); the file itself contains 55 contract sections (39 Web UI + 6 CLI + 6 HTTP + 4 storage). This table follows the file — it is the source of truth. The orchestrator should reconcile the owner_notes claim.

| Feature | Surface | Priority | Key Contracts (upstream) | Defect refs (disposition) | Notes |
|---|---|---|---|---|---|
| Send message / streaming reply | Web UI | core | BC §Send message; PS P1/P3 | — | Request pipeline: context build → RAG → jobs relay or legacy stream; sampler params + stop strings + logit_bias merged |
| Stop button | Web UI | core | BC §Stop button | — | Cancel via job cancel flag (~250ms) or AbortController; partial text kept with honest note |
| Reroll (variants) | Web UI | core | BC §Reroll | — | `variants[]` + `activeVariant`; flipping is free, never regenerates |
| Edit message (user/assistant) | Web UI | core | BC §Edit message | — | User edit truncates + regenerates; old wording parked as variant with continuation subtree |
| Delete / copy message; copy code block | Web UI | core | BC §Delete/copy | — | Delete is permanent, no undo |
| Threads: create/rename/delete/switch/search | Web UI | core | BC §Threads | — | `state.threads` array order is the list's source of truth |
| Folders, tags, pins | Web UI | important | BC §Folders | — | Filtered views over the one ordered array |
| Branching (fork) | Web UI | core | BC §Branching | — | `forkSource:{threadId, at}`; deep-copies shared history incl. variants |
| Greeting + alternate greetings | Web UI | important | BC §Greeting | — | Injected verbatim, never model-generated; alts are flippable variants |
| Lore compression (memory + summarization) | Web UI | important | BC §Memory+summarization | 5.4 (fix before porting) | Token-driven; writes only `thread.lore`; README's lorebook auto-update claim is false |
| Token counter / context meter | Web UI | optional | BC §Token counter | — | Mirrors `buildContextMessages` accounting exactly |
| Chain-of-thought (reasoning) view | Web UI | core | BC §CoT view; PS SM4 | — | Thinking-format parsers (deepseek/harmony/gemma); reasoning excluded from history |
| CoT watchdog (auto-stop) | Web UI | optional | BC §CoT watchdog | — | Disabled by default |
| Smart response limit | Web UI | optional | BC §Smart limit | — | Disabled by default; client-side cap (server gets `max_tokens:-1`) |
| Banned words (logit bias) | Web UI | optional | BC §Banned words; PS P17 | P1-3, 5.2 (fix before porting) | README-declared non-functional; map-of-strings vs array-of-{id,bias} shape mismatch is the strong-inference root cause (D010) |
| System prompt editing + carousel | Web UI | important | BC §System prompt | — | Injected as `[Narrative direction for this response]` before the final user turn |
| Response controls (sampler presets) | Web UI | core | BC §Response controls | — | Params mapped to llama-server API names (`min_p`, `top_k`, `xtc_probability`, …) |
| Built-in macros | Web UI | important | BC §Built-in macros | — | `{{char}}`, `{{user}}`, `{{current_DAT}}` (resolved at send), `{{continue}}`, `{{fast_forward}}` |
| Auto-continue chain | Web UI | important | BC §Auto-continue | — | `{{auto_continue_N}}`; 20s gap, 50-post cap; runtime-only, dies on reload |
| Custom macros | Web UI | important | BC §Custom macros | — | Trigger validation + reserved-name set |
| Characters: create/edit/copy/delete/activate | Web UI | important | BC §Characters | — | `DEFAULT_CARD` "Assistant"; last card undeletable |
| Character card import (V1/V2/V3) | Web UI | important | BC §Card import; PS P11 | — | Lorebook flattened to always-on lore (lossy); imported code always disabled |
| Character card export (V3 PNG) | Web UI | important | BC §Card export; PS P11 | — | Writes both `ccv3` + `chara` tEXt chunks |
| RAG lorebook (dual retriever) | Web UI | important | BC §RAG lorebook; PS P8 | P1-1 (fix before porting) | Degrade-safe: embed down → tag-only; embed server killed by swap/crash-restart degrades silently |
| Per-card custom code | Web UI | important | BC §Card code | 4.7 (port differently) | Unsandboxed by design; wrapped hooks; teardown on switch |
| User personas | Web UI | important | BC §Personas | — | `injectionFrequency`; block lands before final user message |
| Model selector + hot-swap | Web UI | core | BC §Model selector; PS P6/P12, SM2 | P1-1, 3.2 (fix before porting) | Swap phase machine; lock file; lazy readiness promotion |
| Web search (optional) | Web UI | optional | BC §Web search; PS P9 | 4.1 (fix before porting), 4.5 (port differently) | Opt-in; needs Ollama key; proxy forwards verbatim |
| File attachments (drag-and-drop) | Web UI | optional | BC §Attachments | — | Text embedded in context; images reference-only |
| Save AI output as a file | Web UI | optional | BC §Save as file | 5.7 (port differently) | No extension restriction in code (README claim is prompt-level) |
| Data export / import | Web UI | important | BC §Export/import; PS P16 | — | Merge by ID; full backup replaces everything |
| Purge | Web UI | important | BC §Purge | — | Factory reset behind confirm |
| Extensions (mod controls) | Web UI | important | BC §Extensions | 4.7 (port differently) | Unsandboxed by design; URL or inline scripts |
| Scheduler | Web UI | important | BC §Scheduler | — | Tab-open only; 30s check; no catch-up |
| Landing page / dashboard | Web UI | optional | BC §Dashboard | — | Boot screen; active thread not auto-resumed |
| Connection status indicator | Web UI | important | BC §Connection status | — | 5s health poll; `serverConnected` gates the scheduler |
| Cross-device state sync and restore | Web UI | core | BC §State sync; PS P4, SM3 | 3.1 (port differently) | Boot decision matrix; mtime advisory; apiKey redacted |
| Generation job resume (after navigation) | Web UI | core | BC §Job resume; PS P2, SM1 | 5.1 (fix before porting) | Byte-stable replay; breadcrumbs; 401 path cancels live job (defect) |
| Avatar, background, text-color | Web UI | optional | BC §Avatar | — | Cosmetic |
| First-run setup (password, engine, model, embed) | CLI | optional | BC §First-run | P6-1 (fix before porting) | Password provisioning is core; the batch walkthrough is incidental |
| Password reset | CLI | optional | BC §Password reset | — | Deletes `.gobbonet-secret` |
| Model download menu | CLI | optional | BC §Model menu | P6-2 (fix before porting) | Per-model CTX/KV overrides are session-only |
| Monitor loop (crash supervision) | CLI | incidental | BC §Monitor loop | P1-1, P1-2 (fix before porting) | Capability worth reproducing in the port's own supervisor |
| LAN setup and phone URL | CLI | important | BC §LAN setup | P1-6 (leave behind) | mDNS/`.local`; firewall scoped to LocalSubnet |
| Shutdown | CLI | incidental | BC §Shutdown | — | No shutdown handler; boot hygiene cleans stale locks |
| Authentication: login/logout/session | HTTP | core | BC §Auth; PS P5 | 4.2 (fix before porting) | Salted SHA-256; fingerprint-bound HttpOnly cookie, 12h TTL; in-memory sessions |
| /state and /state/info | HTTP | core | BC §/state; PS P4 | 3.1, 4.3 (port differently) | Last-write-wins; mtime in ms; no size cap |
| /llm/jobs (detached generation relay) | HTTP | core | BC §/llm/jobs; PS P2, SM1 | 4.3 (port differently) | Spool files; base64 chunks; 4-worker cap → 429 |
| /swap-model and /swap-status | HTTP | core | BC §Swap; PS P6, SM2 | 3.2 (fix before porting) | Lock file; lazy promotion; 180s timeout |
| Reverse proxies (/llm, /search, /embed) | HTTP | core | BC §Proxies; PS P7 | P2-4 (port differently) | Streaming; `/llm` key injection server-side; `/search` forwards Authorization verbatim |
| Static file serving | HTTP | core | BC §Static | P2-1, 4.4 (port differently) | Traversal + dotfile guards only; no size cap, no allowlist |
| Export bundles | Storage | important | BC §Export bundles; PS P16 | — | Envelope `{gobbonet_export, version:1, exported}` |
| Import semantics | Storage | important | BC §Import | — | Merge by ID; personas patched with defaults |
| Character card carriers | Storage | important | BC §Card carriers; PS P11 | — | `.json` / `.png` (tEXt chunks) / `.charx` ZIP |
| State blob and redaction | Storage | core | BC §State blob; PS §Persistent Schema Notes | — | `settings.apiKey` stripped from every `/state` push |

Priority counts: **core 19, important 22, optional 12, incidental 2** (55 total).

## Protocol and State Notes

Load-bearing wire formats, state machines, and persistence schemas a reimplementation must preserve. Condensed from PS; deep-read PS on the triggers in §Source Index.

### Wire formats (PS §Event Catalog)

- **P1/P3 — chat completions + SSE parsing.** Request `{model:'local', messages, stream:true, max_tokens:-1}` + sampler params + family stop strings + logit_bias. Response `text/event-stream`; client accepts `data: {json}`, bare `{json}`, `data: [DONE]`/`[DONE]`; delta priority `reasoning_content → reasoning → content` plus Ollama-format tolerances. Parser is a pure function of the byte stream (replay-safe by construction).
- **P2 — detached job relay.** `POST /llm/jobs` (body = byte-exact upstream request) → 202 `{id, status:'running'}`; `GET /llm/jobs/<id>?from=N[&max=M]` → `{id, status, size, next, chunk_b64?}`; `chunk_b64` = base64 of raw spool bytes from `from`; `max=0` = status-only peek. Job id = 32 lowercase hex (`^[0-9a-f]{32}$`). Terminal statuses `done|cancelled|error|interrupted`. Byte-stable transcript: replay from byte 0 is deterministic. 4-worker cap → 429; 48h retention; fileserver restart flips running jobs to `interrupted`.
- **P4 — /state + mtime.** `GET /state/info` → `{mtime, size}` + `X-State-Mtime`; `GET /state` → body + header; `POST/PUT` → JSON-validated → `{status:'ok', mtime}`. mtime = `LastWriteTimeUtc` in **milliseconds**. Last-write-wins, no server-side conflict check (defect 3.1).
- **P5 — auth/session.** `POST /login` form-encoded `password=`; cookie `gobbonet_session` (HttpOnly, SameSite=Lax, Max-Age 43200, no Secure); token = 32 random bytes base64url; session bound to `SHA256(ip|User-Agent)`; in-memory table (restart logs everyone out); `X-Gobbonet-Token` header fallback.
- **P6 — hot-swap.** `POST /swap-model {file}` → 202 `{phase:'starting', …}`; `GET /swap-status` → `{phase, file, name, message, started_at, updated_at}`; phases `idle|starting|ready|error`; readiness = llama-server `/health` 200; lock file `.swap-in-progress` created first, removed only on ready/error/boot.
- **P7 — reverse proxies.** Path prefix stripped, query preserved; streaming chunked (4KB flush); `/llm` client Authorization replaced with server-side `GEMMA_LLM_API_KEY`; `/search` forwards Authorization verbatim; 10-min proxy timeouts vs 30-min job worker (P2-4).
- **P8 — embeddings.** `POST /v1/embeddings {input:'<prefix>'+text, model:'embed'}`; prefixes `search_document: `/`search_query: `; response `data.data[0].embedding`; cache key FNV-1a of `'d:'+text` (no crypto.subtle on plain HTTP).
- **P9 — web_search.** Client → proxy `POST /web_search {query, max_results:5}` + Bearer key; proxy → `https://ollama.com/api` **verbatim**; client-visible response `{results:[{title, content, url}]}`; upstream schema beyond that is invisible in-repo (q-websearch-response-fields).
- **P10 — GGUF.** Magic `GGUF`, versions 2/3 only; consumed keys `tokenizer.chat_template`, `general.architecture`, `*.context_length`; template identity = SHA-256 of trimmed template → `HashDerivations` registry; parse failure → filename-heuristic fallback.
- **P11 — character cards.** `.json` (V1 flat / V2-V3 under `.data`), `.png` (tEXt/zTXt/iTXt `ccv3` preferred, `chara` fallback, base64 UTF-8), `.charx` ZIP (methods 0/8 only). Field mapping in BC §Card import; lorebook import is lossy (flattened to always-on lore).
- **P12 — model metadata.** `active-model.json` `{id, name, family, ggufFile, maxCtx, defaultCtx, thinkingFormat}`; `models-list.json` `{active, models:[{file, id, name, family, thinkingFormat, maxCtx, useJinja, chatTemplate, chatTemplateFile, templateHash, active}]}`; whole-rewrite, no locking.
- **P13/P14 — env + secret.** `GEMMA_*` env handoff (convention C02; full set in config-model.md); `.gobbonet-secret` = `<salt>:<hash>` (16-byte salt, SHA-256 of `salt+password`, lowercase hex); consumer regex `^([0-9a-fA-F]+):([0-9a-fA-F]+)$`.
- **P16 — export bundles.** Envelope `{gobbonet_export: threads|cards|personas|full, version:1, exported:<ms>, …}`; import merges by ID, full replaces.
- **P17 — /tokenize + logit_bias.** `POST {content}` → `{tokens}`; client builds map of token-id **strings** → strength (default -20); 8 case/space variants per phrase. Shape mismatch vs llama-server's array-of-{id,bias} is the likely logit-bias root cause (5.2).
- **P18 — launch script + lock.** `.llama-launch.cmd` line: quoted exe + `--model --port 11434 --host 127.0.0.1 --ctx-size --n-gpu-layers --cache-type-k --cache-type-v --parallel 1` + one of `--jinja`/`--chat-template-file`/`--chat-template` + `--reasoning-format auto` [+ `--api-key`]; `mistral-v7-tekken` normalized to `mistral-v7`; sidecar template sanity checks.

### State machines (PS §State Machine)

- **SM1 — job lifecycle.** POST → running (202 is the only synchronous barrier: status + spool exist before the worker starts); upstream 4xx/5xx → error; cancel flag (≤250ms check) → cancelled; EOF → done; restart → interrupted; DELETE on running → cancel flag; DELETE on terminal → deleted; >48h → deleted. Client: terminal+drained → folded; 404 → lost; 401 → unauthorized **and cancels the live job** (defect 5.1); 50 network failures → unreachable (breadcrumb kept).
- **SM2 — swap phase machine.** idle → starting (lock first); poll: health 200 → ready (lock removed); process dead >5s → error; >180s → error; boot → idle (stale lock/status deleted). Readiness promotion is **lazy** (poll-driven) — defect 3.2.
- **SM3 — state-sync + boot decision matrix.** 2s debounced push, single-flight, transient-state guard, force-flush on settle, sendBeacon on pagehide when settled. Boot: local empty + server data → silent auto-restore (once per tab session); server newer → prompt (unless server <50% local size → keep local, re-publish); older/match → noop; quota-truncation signature (server >1.2× local, not newer) → silent recovery.
- **SM4 — stream parser phases.** pre/thinking/content/between/done per thinking format; `serverSplit` latch on first server-routed reasoning delta; `finalizeStreamMessage` at end-of-stream (flush, reparent implicit-think, scrub markers, unwrap tool-call envelope).
- **SM5 — jobsAvailable probe.** null → 404/405 pins false (legacy direct stream forever); 202 pins true; transient error → null (fall back this turn, re-probe next send).

### Persistence schemas (PS §Persistent Schema Notes)

- **IndexedDB `gobbonet-state` v2**: stores `meta` (key `'app'`), `threads` (keyPath `id`), `vectors` (keyPath `hash`), `telemetry` (keyPath `turn_id`, ring 200). Thread order persisted separately as `threadOrder`. All migrations run in `applyLoadedState` on every load path.
- **localStorage mirror**: key `gobbonet_chat_state` (legacy `gemma4_chat_state` renamed); whole-blob rewrite; quota errors → `storageQuotaHit` → server backup becomes source of truth.
- **`/state` server blob**: shape = `buildStateBlob()`; `settings.apiKey` stripped; whole-file rewrite, no locking/versioning/compaction; mtime (ms) is the only version stamp.
- **Job spool** `.jobs/<id>.{sse,json,cancel}`: `.sse` append-only raw bytes; `.json` mutable with 3×25ms torn-read retry; `.cancel` flag file.
- **Swap state**: `.swap-status.json` + `.swap-in-progress` presence-only lock; both deleted at fileserver boot.
- **Model metadata**: `active-model.json` / `models-list.json` whole-rewrite, no locking between writers.
- **`.gobbonet-secret`**: write-once; rename-to-`.bad` on verification failure.
- **Export bundles**: snapshot JSON, merge-by-ID import.

## Portability Hazards

Consolidated from all prior phases. **This section closes arch-CF6** (the architecture phase's portability hazard inventory: PowerShell HttpListener + runspaces, cmd batch orchestration, browser storage + Page Lifecycle APIs, mDNS/.local origin stability, Windows-only System32 tooling, AV-avoidance download patterns) — each item is folded into the rows below and the closure is recorded in the phase handoff's `carry_forward_closures`. These are risks, not certainties (`portability hazard` evidence level throughout).

| Hazard | Source Phase | Impact | Mitigation |
|---|---|---|---|
| PowerShell HttpListener + runspaces; synchronous `GetContext()` accept loop | architecture (arch-CF6), protocols | Server core is .NET/Windows-specific; streaming responses block the single-threaded loop; runspace arg-order quirks | Replace with a real HTTP server (async I/O, bounded worker pool); keep the 4-worker job cap semantics |
| cmd batch orchestration (taskkill/tasklist/start/netsh, P/Invoke console control) | architecture (arch-CF6), mechanical P6-5 | Launcher/supervisor is Windows-only | Replace with the port's own supervisor; keep the supervision contract (15s health poll, restart from launch script, stand-down during swap) |
| Browser storage + Page Lifecycle APIs (IndexedDB/localStorage, bfcache, visibilitychange, sendBeacon) | architecture (arch-CF6), protocols | Per-origin silos; save-on-exit depends on browser lifecycle behavior that differs across browsers and is absent in non-browser ports | Reproduce the `/state` sync + boot decision matrix (SM3); design save-on-exit for the target runtime |
| mDNS/`.local` origin stability | architecture (arch-CF6) | Phone URL changes with IP rotation; each origin is a separate data silo | Keep the `.local` bookmark advice + IP-change warning; server-side state sync is the patch |
| Windows-only System32 tooling (curl/certutil/tar, ipconfig, netsh) | architecture (arch-CF6), mechanical P6-5 | First-run downloads and LAN setup are Windows-only | Replace with target-platform equivalents; keep the hash-verification discipline |
| AV-avoidance download patterns (no PowerShell staging, .part rename) | architecture (arch-CF6) | Download staging logic is tuned to Windows Defender behavior | Irrelevant on other platforms; keep the `.part` + hash-verify discipline regardless |
| file:// vs served mode split (`IS_SERVED`) | protocols | Two client modes with different capabilities (no auth/sync/jobs/swap on file://) | A port can drop file:// mode if it always serves; keep the endpoint-switch semantics if both modes are kept |
| Client/fileserver version skew (jobsAvailable probe) | protocols | Old server + new client breaks generation | Keep the probe semantics (only definitive 404/405 pins the fallback) |
| mtime protocol is advisory (last-write-wins) | protocols, semantic 3.1 | Concurrent two-device writes silently clobber | Server-side conflict check (convention C05) |
| GGUF v2/v3 only | protocols | v1 GGUFs rejected; unknown KV types abort parse | Keep the version gate + filename-heuristic fallback |
| Card format versions + lossy lorebook flatten | protocols | Import/export fidelity loss | Keep the field mapping; document the lossiness |
| `mistral-v7-tekken` not registered in pinned build | protocols | Passed bare to `--chat-template` it becomes a literal template body | Keep the normalization to `mistral-v7` |
| BOM-less UTF-8 discipline | protocols | PowerShell 5.1 writes BOMs; a BOM breaks the client's `JSON.parse` on `/state` | Emit BOM-less UTF-8 for all server JSON |
| ASCII-only server console output | protocols | Batch echo mangles non-ASCII on legacy code pages | Target-runtime console encoding |
| Session state is in-memory | protocols | Server restart logs everyone out; mid-generation 401 cancels the live job (5.1) | Keep or improve (persist sessions); fix the 401 path |
| Lazy swap readiness promotion | protocols, semantic 3.2 | Orphaned lock blocks the monitor loop indefinitely | Server-side promotion timer (fix before porting) |
| Base64 chunk framing + byte offsets | protocols | Replay determinism depends on exact `from`/`next`/`size` semantics | Preserve byte-offset semantics exactly |
| `max_tokens:-1` + client-side cap | protocols | No server-side token cap; replies grow unbounded without the client cap | Reproduce the client-side smart limit |
| Family-keyed stop strings | protocols | Key must match identify-model.ps1's family strings exactly or delimiters leak | Keep the family key registry |
| Job id regex `^[0-9a-f]{32}$` | protocols | Changing id format breaks the route | Keep the id format or update both sides |
| `DecompressionStream` requirement | protocols | Compressed cards unreadable without it | Target-runtime zlib equivalent |
| No `crypto.subtle` on plain HTTP | protocols | RAG cache key must not depend on SubtleCrypto | Keep the FNV-1a fallback |
| Wildcard CORS + cookie auth | semantic 4.8 | `*` + `Authorization` becomes a real cross-site channel if a port switches to bearer-header auth without SameSite protection | Keep SameSite=Lax; scope CORS to the LAN origin |
| Plain-HTTP LAN transport | semantic 4.6 | Password and cookie sniffable on the LAN | Documented design choice with disclosed tradeoffs; a port re-makes the choice consciously (TLS, or keep + disclose) |
| Unsandboxed card code / extensions | semantic 4.7 | Malicious card/extension = full page compromise | Documented design choice; a port re-makes the choice consciously (keep opt-in + wrapped hooks, or sandbox) |
| Installer binaries absent from repo | architecture | Packaging internals unknown | q-installer-packaging (needs-maintainer-decision) |

## Defect Synthesis

Consolidation of MD (17 findings) and SD (17 findings) — **34 total, all covered below**. Grouped by disposition so a reimplementer sees the fix list, the design list, and the discard list separately; within each group, medium before low. Dispositions are the upstream reports' recommendations, carried forward verbatim.

### Fix before porting (12) — the defect would carry into a new implementation

| Defect ID | Source Report | One-line Description | Severity | Disposition | Required design consequence |
|---|---|---|---|---|---|
| P1-1 | MD | Hot-swap and crash-restart kill **all** `llama-server.exe` processes (incl. the embed server) by bare image name and never restart it; RAG silently degrades to tag-only | medium | fix before porting | Role-scoped process targeting or coordinated respawn (convention C04) |
| P1-2 | MD | Health/probe checks accept any HTTP response or any body containing "ok"; foreign services (Ollama) misdetected as healthy llama-server | medium | fix before porting | Health probes must verify responder identity (convention C03) |
| P1-3 | MD | Logit bias (banned words) is README-declared non-functional; code path wired but broken | medium | fix before porting | Resolve root cause (see 5.2) or drop the feature honestly |
| P1-4 | MD | Tekken-tokenizer patch is README-declared possibly incomplete; known delta (trailing space after `[INST]`) | medium | fix before porting | Re-verify template handling against the pinned build; keep the normalization |
| P6-1 | MD | `LLAMA_PIN_SHA256`/`EMBED_PIN_SHA256` ship empty; fresh installs download engine + embed model unpinned | medium | fix before porting | Pin hashes at release time; verify before use |
| P6-2 | MD | Per-model CTX_SIZE/KV_CACHE_TYPE overrides live only in the download menu; hot-swaps and later launches ignore them | medium | fix before porting | Persist per-model ctx/kv in the model record |
| 3.2 | SD | Lazy swap readiness promotion: orphaned `.swap-in-progress` lock stands the monitor loop down indefinitely | medium | fix before porting | Server-side promotion timer independent of client polling |
| 4.1 | SD | README's search-privacy claim ("metadata and telemetry stripped") is false: passthrough proxy forwards body + Authorization verbatim | medium | fix before porting | Either implement stripping or correct the claim |
| 4.2 | SD | No rate limiting or lockout on `POST /login`; on-LAN brute force with no backoff | medium | fix before porting | Attempt counter, lockout, or delay |
| 5.1 | SD | Mid-generation 401 cancels the still-running job via the DELETE-ack path while the error message promises re-attachment | medium | fix before porting | Error message must match the recovery path (convention C06); keep the job alive across re-login |
| 5.2 | SD | `logit_bias` sent as map of token-id strings where llama-server's OpenAI-compatible endpoint expects array of `{id, bias}` — likely root cause of P1-3 | medium (strong inference) | fix before porting | Send the OpenAI array shape; runtime confirmation remains q-logit-bias-root-cause |
| 5.4 | SD | README claims lorebooks auto-update from conversations; code writes only `thread.lore` | low | fix before porting | Correct the README or implement the claimed behavior (maintainer ruling: post-lorebook-claim-ruling) |

### Port differently (15) — the new implementation should handle this case differently by design

| Defect ID | Source Report | One-line Description | Severity | Disposition | Required design consequence |
|---|---|---|---|---|---|
| P1-5 | MD | `loadActiveModel` overwrites `tokenLimit` whenever it equals the default 24576 — deliberate 24576 silently replaced | low | port differently | Distinguish "never customized" from "deliberately set to default" |
| P2-1 | MD | Static serving reads entire files into memory with no size cap; `models/*.gguf` (4-20 GB) can exhaust the server | medium | port differently | Stream file responses; cap or allowlist static paths |
| P2-2 | MD | Client fetches to embed server and search proxy have no timeout/AbortSignal; wedged upstream hangs RAG/search | medium | port differently | Timeouts on all client fetches |
| P2-4 | MD | 10-min proxy read timeout vs 30-min job worker; long CPU prompt processing can abort direct streams | low | port differently | Unify timeouts; prefer the job path |
| P6-4 | MD | Listen port hardcoded to 8080; "already running" probe accepts any HTTP responder | low | port differently | Configurable port + identity-verified probe |
| P6-5 | MD | Entire orchestration stack is Windows-coupled by design | low | port differently | Replace launch.bat/fileserver.ps1/setup-lan.bat wholesale (this is the port itself) |
| 3.1 | SD | `/state` POST/PUT is unconditional last-write-wins; concurrent two-device writes silently clobber | medium | port differently | Server-side compare-and-swap on a version stamp (convention C05) |
| 4.3 | SD | No request-body size caps on `/state` and `/llm/jobs`; multi-GB bodies exhaust memory | medium | port differently | Content-Length checks / streaming body limits |
| 4.4 | SD | Static serving exposes every non-dotfile under the project root (models, scripts, source) to any authenticated client | medium | port differently | Extension allowlist + explicit serve roots |
| 4.5 | SD | `webSearch` logs the API key prefix to the console; raw upstream response logged too | low | port differently | No key material in logs |
| 4.6 | SD | Plain-HTTP LAN transport: password and cookie sniffable | low | port differently | Documented design choice with disclosed tradeoffs; re-make consciously (TLS or keep + disclose) |
| 4.7 | SD | Per-card code and extensions run unsandboxed with full page access | low | port differently | Documented design choice; re-make consciously (keep opt-in + wrapped hooks, or sandbox) |
| 4.8 | SD | Wildcard CORS on every response | low | port differently | Scope CORS; keep SameSite=Lax |
| 5.3 | SD | Vestigial `reminderFrequency` UI setting: persisted but never consumed | low | port differently | Drop the dead control |
| 5.7 | SD | README claims only .txt/.json file saves; code has no extension restriction | low | port differently | Enforce the restriction or correct the README |

### Leave behind (7) — source-specific, won't survive porting

| Defect ID | Source Report | One-line Description | Severity | Disposition | Required design consequence |
|---|---|---|---|---|---|
| P1-6 | MD | LAN IP detection takes the first non-loopback IPv4; VPN/virtual adapters yield the wrong phone URL | low | leave behind | Target-platform network enumeration |
| P2-3 | MD | PowerShell download fallback has no explicit timeout (WebClient defaults) | low | leave behind | Dies with the batch launcher |
| P2-5 | MD | Fileserver-failure message says "Desktop chat still works normally" but opens the browser at the dead port | low | leave behind | Dies with the batch launcher |
| P6-3 | MD | Batch-only password-file check deliberately looser than the PowerShell consumer | low | leave behind | Latent inconsistency in a path unreachable when PowerShell is absent |
| P6-6 | MD | GGUF paths interpolated into PowerShell command lines; `&`/`%`/`^`/`!` in filenames break invocations | low | leave behind | Dies with the batch launcher (env-var handoff, convention C02, is the fix pattern) |
| 5.5 | SD | Stale in-code comment: "Keeps last 40 messages verbatim" (implementation is token-driven) | low | leave behind | Write correct comments in the new code |
| 5.6 | SD | Stale in-code comment: "personality → personality (periodic reminder)" (personality is persistent) | low | leave behind | Write correct comments in the new code |

Disposition counts: **fix before porting 12, port differently 15, leave behind 7** (34 total). Severity across both reports: 0 critical, 0 high, 16 medium, 18 low (decisions D004/D011 — no severity inflation).

## Observed Facts vs. Inferred Structure

### Observed Facts

Direct statements from docs, code, and upstream findings (all with file:line citations in the cited upstream sections):

- Windows-only, fully-local chatbot frontend; zero telemetry; only network calls are one-time verified downloads + opt-in web search (README.md:3,195; AM §System Intent).
- No build step: plain files; the "build" is the numbered file split; no package.json/lockfile; no CI (AM §Build and Packaging).
- Numbered JS/CSS load order is a declared contract; global namespace, no module system; 24-boot.js is the entry point (convention C01; AM §Layer Map).
- Cross-process config passes exclusively via `GEMMA_*` env vars (convention C02; PS P13).
- llama.cpp pinned tag `b9294`, SHA-256 verified; ports 11434 (chat), 11435 (search proxy), 11436 (embeddings), 8080 (fileserver, hardcoded).
- `--parallel 1`; one generation at a time end-to-end; 4-worker job cap → 429.
- Auth: salted SHA-256 password, 32-byte random session token, HttpOnly/SameSite=Lax cookie, 12h TTL, client-fingerprint binding, in-memory sessions, no rate limiting.
- Job relay: byte-stable spool, base64 chunk framing, 48h retention, `interrupted` on restart.
- GGUF v2/v3 only; card formats V1/V2/V3 in .json/.png/.charx; export envelope `{gobbonet_export, version:1, exported}`.
- IndexedDB `gobbonet-state` v2 + localStorage mirror + `/state` server blob; `settings.apiKey` redacted from sync.
- README-declared known bugs: logit bias non-functional (README.md:264-265); Tekken patch possibly incomplete (README.md:267-268).
- No tests, no CI, no runtime verification possible in this environment (Windows-only).
- Installer binaries (`GobboNetSetup.exe`, `launch.exe`, `launchLAN.exe`), `REFACTOR-PLAN.md`, and `fonts/atkinson-hyperlegible.woff2` are referenced but absent from the repo.
- 34 defect findings: 17 mechanical + 17 semantic; 0 critical, 0 high, 16 medium, 18 low.

### Inferred Structure

Architectural conclusions drawn from multiple facts (`strong inference`):

- The whole system is designed around **one generation at a time end-to-end** (client `isGenerating` + `--parallel 1` + job cap).
- The browser is the **primary data owner**; the server `/state` blob is a rolling backup whose real job is patching the per-origin storage silo.
- The fileserver is the **sole LAN-facing process**; llama-server, embed server, and search proxy bind loopback only.
- The system is a composition of six reusable concepts (product shell, provider adapter, message normalizer, agent loop, session store, render loop/UI surface) — the layer map above is the porting target, not the source folder layout.
- RAG is **degrade-safe by design**: every failure path falls back to tag-only retrieval or no retrieval, never blocking chat.
- The logit_bias shape mismatch (map of string keys vs OpenAI array of `{id, bias}`) is the most likely root cause of the README-declared broken banned-words feature (D010; runtime confirmation pending).
- The two security-posture items (plain-HTTP transport, unsandboxed code) are deliberate, documented design choices with residual risk, not accidental bugs (D009).

## Domain Glossary

| Term | Definition | Where Used |
|---|---|---|
| GGUF | Binary model container format; GobboNet parses v2/v3 metadata (chat template, architecture, context length) | identify-model.ps1; PS P10 |
| Chat template / jinja | The prompt-formatting template that turns messages into model input; selected from GGUF metadata or sidecar `.jinja` files | PS P10/P18 |
| Thinking format | Per-family parser for reasoning deltas (none/deepseek/harmony/gemma); splits reasoning from content | 02-model.js, 03-generation.js; SM4 |
| CoT (chain-of-thought) | The model's step-by-step reasoning, rendered separately and excluded from history | BC §CoT view |
| Lore / lorebook | Card-authored world info; `startingLore` (always-on) and `ragStorybook` (retrieved on demand) | 07-prompt.js, 08-rag.js |
| Lore compression | Token-driven summarization of old messages into `thread.lore` (never message-count-driven) | BC §Memory+summarization |
| Character card | Persona definition (name, description, personality, greeting, lore, sampler params, custom code); V1/V2/V3 formats | 16-card-io.js; PS P11 |
| Persona | The user's self-profile injected into context on a cadence | 17-personas.js |
| Macro | `{{trigger}}` text shortcut; built-ins (`char`, `user`, `current_DAT`, `continue`, `fast_forward`) + custom | 20-macros.js |
| Auto-continue | `{{auto_continue_N}}` chain: N posts, 20s apart, runtime-only | 09-threads.js |
| Smart limit | Client-side reply-length cap (sentence-boundary trim, ✂ marker); server gets `max_tokens:-1` | 03-generation.js |
| Hot-swap | Replacing the running GGUF without rebooting; lock-file-coordinated kill → rewrite → spawn | fileserver.ps1; SM2 |
| Jobs relay / spool | Server-side detached generation: raw SSE spooled to `.jobs/<id>.sse`, client polls base64 chunks | fileserver.ps1; PS P2 |
| mtime protocol | `/state` versioning by file mtime in milliseconds; advisory only (last-write-wins) | PS P4 |
| `IS_SERVED` / file:// mode | Client mode switch: served (same-origin proxy, auth, sync, jobs, swap) vs file:// (direct loopback, none of those) | 01-config.js |
| `GEMMA_*` env | The env-var config channel from launch.bat to fileserver.ps1 (convention C02) | PS P13 |
| `.gobbonet-secret` | Password file: `<salt>:<hash>` (SHA-256 of salt+password) | PS P14 |
| Tekken | Mistral tokenizer family with a known template patch (possibly incomplete) | P1-4 |
| Logit bias | Token-level probability bias for banned words; broken in source (P1-3/5.2) | 06-state-sync.js; PS P17 |
| KV cache | llama-server cache quantization (`q8_0` default; per-model overrides exist only in the download menu) | launch.bat; P6-2 |
| Runspace | PowerShell worker thread hosting a detached job worker (max 4) | fileserver.ps1 |
| mDNS / `.local` | Zero-config hostname for the phone URL (`http://<hostname>.local:8080`) | setup-lan.bat, launch.bat |
| sendBeacon / bfcache | Browser Page Lifecycle APIs used for save-on-exit and wake-resume | 06-state-sync.js, 24-boot.js |
| Variant / continuation | Reroll/edit model: each message holds `variants[]`; edited-away subtrees are parked as continuations | 10-chat.js |
| Fork / branch | Copying a conversation from a message into a new thread (`forkSource`) | 09-threads.js |
| Extensions | User-injected stylesheets/scripts (URL or inline), unsandboxed by design | 19-extensions.js |
| Card code | Per-card JavaScript with wrapped hooks (activate/deactivate/send/reply/context), unsandboxed by design | 23-card-code.js |
| Scheduler | Time-based prompt sender (HH:MM, once/daily); runs only while the tab is open | 22-scheduler.js |
| Search proxy | Loopback HttpListener forwarding `/web_search` verbatim to `https://ollama.com/api` | launch.bat:1608; PS P9 |
| Embed server | Second llama-server instance (`--embeddings`) on 11436 for RAG semantic retrieval | launch.bat; PS P8 |
| `active-model.json` / `models-list.json` | Server-side model metadata files the browser reads for token limits, thinking format, and the dropdown | PS P12 |
| `.swap-in-progress` | Presence-only lock file coordinating hot-swap with the monitor loop | PS P18 |
| `.llama-launch.cmd` | The launch script the monitor loop re-runs on crash | PS P18 |
| `default-characters.json` | Seed characters fetched at boot | 24-boot.js |
| Hardware probe | First-run WMI/GPU detection for model recommendations | hardware-probe.ps1 |

## Coverage and limits

- **Inspected scope:** all five upstream artifacts read in full — AM (architecture-map.md), BC (behavioral-contracts.md, 978 lines), PS (protocols-and-state.md, 465 lines), MD (mechanical-defects.md, 17 findings), SD (semantic-defects.md, 17 findings); plus CONVENTIONS.md (C01–C06), DECISIONS.md (D001–D011), workflow/status.yaml, the porting phase prompt, and the five secondary outputs (tails, to append correctly). Targeted source verification was limited to cross-checking upstream citations (no new source reading was needed — this is a synthesis phase; the upstream artifacts are the primary material).
- **Skipped scope:** no new source reading beyond the upstream artifacts (per the phase prompt, source is read only to resolve ambiguity the upstream findings leave open — none required it). The five secondary outputs were appended, not rewritten.
- **Evidence basis:** upstream findings (source inspection by five prior phases, all with file:line citations). No runtime verification (Windows-only; not executable in this environment), no tests in repo, no CI.
- **Known blind spots:** (1) the 10 open questions carried from earlier phases remain open (see §Open Questions) — all are runtime-test or maintainer-decision items, none answerable from source; (2) the Ollama `web_search` upstream schema beyond `{results:[{title,content,url}]}`; (3) the definitive logit-bias root cause (5.2 is strong inference); (4) installer binaries, REFACTOR-PLAN.md, and the fonts directory remain absent from the repo.
- **Conflicts surfaced (not hidden):** (1) the contracts phase's owner_notes/validation claim 40 contracts (24 Web UI) while the file contains 55 contract sections (39 Web UI) — this bundle follows the file; (2) the README search-privacy claim vs the passthrough implementation (defect 4.1); (3) the README lorebook auto-update claim vs thread.lore-only compression (defect 5.4); (4) the README .txt/.json file-save claim vs the unrestricted code path (defect 5.7).
- **Coverage disposition:** COMPLETE — every load-bearing invariant, acceptance obligation, compatibility hazard, and defect disposition from the five upstream artifacts is carried forward; arch-CF6 is closed by §Portability Hazards; the Source Index names the exact deep-read triggers for everything compressed.

## Open Questions

All 10 open questions from earlier phases were re-triaged against this phase's reading; none became answerable from source. They remain tracked in `workflow/status.yaml` under their originating phases and are listed here for bundle self-sufficiency. No new open questions from this phase.

| ID | Kind | Description | Deferred Reason |
|---|---|---|---|
| q-installer-packaging | needs-maintainer-decision | Installer binaries absent from repo; packaging internals unknown | Requires the maintainer or release artifacts |
| q-refactor-plan | needs-maintainer-decision | REFACTOR-PLAN.md referenced by every split header but absent | Missing artifact; only the maintainer can supply it |
| q-font-shipping | needs-maintainer-decision | fonts/atkinson-hyperlegible.woff2 referenced but absent; installer shipping unknown | Not resolvable from source; cosmetic |
| q-accept-loop-scale | needs-runtime-test | Synchronous accept loop behavior under multiple concurrent LAN clients unmeasured | Requires live load testing |
| q-logit-bias-root-cause | needs-runtime-test | Definitive root cause of the broken logit bias (5.2 is strong inference) | Requires a live capture against the pinned build |
| q-tekken-patch-completeness | needs-runtime-test | Whether the Tekken patch is sufficient | Requires running Tekken models against the pinned build |
| q-ollama-api-version | needs-runtime-test | Exact web_search request/response contract and stability | Requires a live capture against Ollama's API |
| q-websearch-response-fields | needs-runtime-test | Whether upstream returns fields beyond title/content/url; whether max_results is honored | Proxy forwards verbatim; not visible in-repo |
| q-sse-done-marker | needs-runtime-test | Whether the pinned build terminates streams with `data: [DONE]` or closes | Requires a live capture against the pinned build |
| q-llama-server-diag-endpoints | needs-runtime-test | `/props` and `/apply-template` response shapes (diagnostic-only) | Requires a live call against the pinned build |

## Carry-Forward

| ID | Target Phase | Description | Deferred Reason |
|---|---|---|---|
| porting-CF1 | reimplementation-spec | The Strategic Alignment Hook (language-agnostic vs opinionated spec) must be run before the spec phase; this bundle is written language-agnostic and does not pre-lock a target stack, project identity, or scope cuts. | The hook is a user conversation the spec phase owns (GUIDE.md §Strategic Alignment Hook); under `--auto` the spec defaults to language-agnostic and records the choice as an open question. |

---

## Validation

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | The system summary, layer map, contract table, protocol notes, and porting findings are synthesized. | PASS | §System Summary; §Layer Map With Ownership (8 concept-named layers); §Feature Contract Table (55 rows); §Protocol and State Notes (wire formats, SM1–SM5, 8 persistence schemas); §Portability Hazards (28 rows). |
| 2 | Portability hazards and open questions are separated from facts. | PASS | §Portability Hazards is a dedicated section marked `portability hazard`; §Open Questions lists the 10 open questions; §Observed Facts vs. Inferred Structure separates `observed fact` from `strong inference`. |
| 3 | Feature importance is sorted for porting. | PASS | §Feature Contract Table assigns core (19) / important (22) / optional (12) / incidental (2) to all 55 contracts, anchored to AM §Porting Priorities. |
| 4 | Defect Synthesis consolidates mechanical-defects.md and semantic-defects.md with porting recommendations (fix before porting / port differently / leave behind). | PASS | §Defect Synthesis covers all 34 findings (17 MD + 17 SD) grouped by disposition: fix before porting 12, port differently 15, leave behind 7, each with a required design consequence. |
| 5 | Findings are marked with evidence levels. | PASS | Every section carries `observed fact` / `strong inference` / `portability hazard` / `open question` tags with upstream file:line pointers; the two strong-inference items (5.2, layer composition) are labeled as such. |
| 6 | Coverage and limits name inspected scope, skipped scope, evidence basis, and blind spots. | PASS | §Coverage and limits lists all four plus disposition (COMPLETE) and explicitly surfaces four conflicts instead of hiding them. |
| 7 | The Source Index makes the bundle a self-contained compression boundary and identifies targeted deep-read triggers. | PASS | §Source Index covers architecture, contracts, protocols/state, both defect reports, and all five secondary outputs, each with the summary carried forward and the exact condition that should trigger a targeted deep read. |

**Validated by:** porting phase, delegated subagent session (2026-08-18)
**Overall:** PASS
