---
selection: language-agnostic
pipeline: workflow/pipeline-full-with-deep-audit.yaml
phase: reimplementation-spec
date: 2026-08-18
---

# Reimplementation Spec — GobboNet

<!--
  Final deliverable of the CodeCartographer full-with-deep-audit pipeline.
  Language-agnostic variant (user-selected via the Strategic Alignment Hook; closes porting-CF1).
  Primary material: findings/porting/reverse-engineering-bundle.md (the compression boundary).
  Targeted deep reads performed (recorded in §Coverage and limits): behavioral-contracts.md
  §Black-Box Acceptance List (the bundle names it as the source of acceptance detail).
  Evidence levels: `observed fact` | `strong inference` | `portability hazard` | `open question`.
-->

## System Summary

GobboNet is a Windows-only, fully-local AI chatbot frontend for non-technical home users: a browser chat UI talking to a local llama.cpp `llama-server` (OpenAI-compatible API) over loopback, served and supervised by a small host-side stack (`observed fact`: bundle §System Summary). The product is a character-chat experience — personas, lorebooks, RAG retrieval, conversation branching and variants, macros, a scheduler, per-card JavaScript, extensions, and optional LAN access from a phone. The only network calls are one-time verified downloads (engine, GGUF models, embedding model) and an opt-in web-search proxy to Ollama; everything else runs offline with zero telemetry.

The load-bearing shape a reimplementation must preserve (`strong inference`, bundle §System Summary):

- **One generation at a time end-to-end** — client `isGenerating` + server `--parallel 1` + 4-worker job cap.
- **Byte-stable detached generation** — the server spools raw SSE to disk; the client polls base64 chunks and replays deterministically after navigation.
- **Degrade-safe RAG** — embed server down → tag-only retrieval; chat never blocks.
- **Advisory cross-device sync** — mtime-based boot decision matrix over a last-write-wins server backup, patching the per-origin browser-storage silo.
- **The browser is the primary data owner**; the server holds a redacted rolling backup.

All 34 defect findings are silent degradations, edge-case failures, or documented design choices — nothing breaks normal single-user operation (`observed fact`: bundle §Defect Synthesis).

## Conceptual Module Model

Concept names only — the target implementation must not mirror the source folder layout (`observed fact`: bundle §Layer Map With Ownership).

### Product shell / supervisor

| Field | Value |
|---|---|
| **Responsibility** | Provision, download (hash-verified), spawn, and supervise every other process; first-run setup; LAN config; shutdown. |
| **Public inputs** | User console interaction (password setup, model menu); `reset-password` command. |
| **Public outputs** | Running processes; `active-model.json` / `models-list.json` metadata; `GEMMA_*` env config for the provider adapter (convention C02). |
| **Owned state** | `.gobbonet-secret` (password `salt:hash`); `.llama-launch.cmd` / `.embed-launch.cmd`; download pins. |
| **Invariants** | Health probes verify responder identity (C03); process kills scope by role (C04); downloads verified before use; monitor loop stands down during hot-swap. |
| **Collaborators** | Provider adapter, inference engine, embed server, search proxy, hardware probe. |

### Provider adapter (LAN server)

| Field | Value |
|---|---|
| **Responsibility** | The sole LAN-facing process: password-gated HTTP server, reverse proxy to the three loopback services, `/state` rolling backup, detached generation-job spooler, hot-swap controller, static serving. |
| **Public inputs** | HTTP on the listen port: `/login`, `/state`, `/llm/jobs*`, `/swap-model`, `/swap-status`, proxied `/llm/*`, `/search/*`, `/embed/*`, static paths. |
| **Public outputs** | HTTP responses; spool files; `.swap-status.json`; `.gobbonet-state.json`; rewritten launch script + model metadata on swap. |
| **Owned state** | In-memory session table; job worker registry; swap lock file. |
| **Invariants** | Auth gate on everything except `/login`/`/logout`/`OPTIONS`/`/favicon.ico`; byte-stable spool; one swap at a time; server-side write conflict check on `/state` (C05); error messages match recovery paths (C06). |
| **Collaborators** | Inference engine, embed server, search proxy, browser client, supervisor. |

### Message normalizer / model registry

| Field | Value |
|---|---|
| **Responsibility** | Turn model-family differences into one internal shape: GGUF metadata parsing, chat-template selection, thinking-format parsing, SSE line parsing, stop strings, sampler mapping, logit-bias building. |
| **Public inputs** | GGUF files; `active-model.json` / `models-list.json`; raw SSE byte streams; per-card sampler settings. |
| **Public outputs** | Model records (id, family, ctx, thinking format, template); parsed deltas (reasoning vs content); request bodies. |
| **Owned state** | Model registry; template hash registry; parser state (runtime-only). |
| **Invariants** | Parser is a pure function of the byte stream (replay-safe); `mistral-v7-tekken` normalized to `mistral-v7`; family-keyed stop strings match the registry exactly. |
| **Collaborators** | Agent loop, provider adapter, inference engine. |

### Agent loop / conversation engine

| Field | Value |
|---|---|
| **Responsibility** | The chat turn pipeline: send → context build (single RAG injection seam) → request → stream → render; threads, variants, branching, lore compression, auto-continue. |
| **Public inputs** | User messages, edits, rerolls, forks, macros, scheduled prompts. |
| **Public outputs** | Rendered messages; context built for the provider; lore summaries. |
| **Owned state** | Active thread; `isGenerating`; variant/continuation trees; `thread.lore`. |
| **Invariants** | One generation at a time; user edits park prior wording as variants with continuation subtrees; lore compression is token-driven (never message-count-driven) and writes only `thread.lore`; RAG failure never blocks chat. |
| **Collaborators** | Session store, message normalizer, provider adapter, tool executor. |

### Session store / persistence

| Field | Value |
|---|---|
| **Responsibility** | Own all user data in the browser (IndexedDB v2 + localStorage mirror + migrations) and sync a redacted copy to the server `/state` backup. |
| **Public inputs** | State mutations from every module; `/state/info` + `/state` responses. |
| **Public outputs** | Loaded state; debounced pushes; boot decision (restore / prompt / noop). |
| **Owned state** | IndexedDB `gobbonet-state` v2 (meta, threads, vectors, telemetry); localStorage mirror; `lastKnownMtime`. |
| **Invariants** | `settings.apiKey` never leaves the client; migrations run on every load path; boot matrix: local empty + server data → silent auto-restore (once per tab session); server newer → prompt; quota-truncation signature → silent recovery. |
| **Collaborators** | Agent loop, provider adapter, render loop. |

### Tool executor / extension runtime

| Field | Value |
|---|---|
| **Responsibility** | Per-card code hooks, extensions, macros, scheduler, data import/export. |
| **Public inputs** | Card code, extension scripts, macro definitions, schedules, import files. |
| **Public outputs** | Hook invocations (send/reply/activate/context); macro expansions; scheduled sends; export bundles. |
| **Owned state** | Hook registry (rebuilt per card activation); macro list; schedule list. |
| **Invariants** | Imported card code is always disabled until opted in; every hook call is wrapped (throwing hook disabled, not fatal); hooks torn down on card switch; schedules run only while the tab is open. |
| **Collaborators** | Agent loop, session store, render loop. |

### Render loop / UI surface

| Field | Value |
|---|---|
| **Responsibility** | DOM rendering: chat, threads sidebar, modals, dashboard, styling; boot entry. |
| **Public inputs** | State; user DOM events. |
| **Public outputs** | Rendered UI; DOM events to the agent loop. |
| **Owned state** | DOM; scroll/pin state; UI-only preferences. |
| **Invariants** | Boot awaits state load before first render; landing page is the entry point (active thread not auto-resumed); render tick throttled (~80ms) during streaming. |
| **Collaborators** | Agent loop, session store, tool executor. |

### Hardware probe (optional tooling)

| Field | Value |
|---|---|
| **Responsibility** | First-run hardware detection (VRAM/RAM/disk) for model recommendations. |
| **Public inputs** | OS hardware queries. |
| **Public outputs** | `hardware.json`; recommended model tier. |
| **Owned state** | None durable. |
| **Invariants** | Recommendation never exceeds measured VRAM without an explicit warning. |
| **Collaborators** | Product shell. |

## Layer Split

| Module | Layer | Notes |
|---|---|---|
| Agent loop / conversation engine | core semantics | The chat turn pipeline, variants/branching, lore compression — must survive unchanged. |
| Message normalizer / model registry | core semantics | Family differences are the product's core value; parsers must be replay-safe. |
| Session store / persistence | core semantics | Data ownership, migrations, boot decision matrix — load-bearing. |
| Tool executor / extension runtime | core semantics | Hook lifecycle and opt-in semantics are the safety contract. |
| Provider adapter (LAN server) | adapter | Integrates with the inference engine, embed server, search proxy, filesystem. |
| Product shell / supervisor | adapter | Integrates with the OS (processes, downloads, firewall). |
| Hardware probe | adapter | OS hardware queries. |
| Render loop / UI surface | delivery surface | The browser UI; a port may re-skin freely while preserving behavior. |

## Required Behaviors

Derived from the bundle's feature contract table (55 contracts). Scope tiers at the end of this section.

**Chat core (core):** send/streaming reply (sampler params + family stop strings + logit_bias merged into the request; `max_tokens:-1` with client-side cap); stop (partial text kept with honest note; cancel via job flag or abort); reroll (variants flippable, never regenerated); edit (user edit truncates + regenerates, prior wording parked as variant with continuation subtree; assistant edit in place); delete/copy; threads (create/rename/delete/switch/search; array order is the list's source of truth); branching (fork with deep-copied shared history); chain-of-thought view (reasoning split from content, excluded from history); response controls (sampler presets mapped to provider API names); model selector + hot-swap; cross-device state sync and restore; generation job resume after navigation.

**Characters and lore (important):** characters CRUD (last card undeletable); card import V1/V2/V3 (lorebook flattened to always-on lore — lossy; imported code always disabled); card export (V3 PNG with `ccv3` + `chara` chunks); RAG lorebook dual retriever (degrade-safe); per-card custom code (unsandboxed by design, wrapped hooks, teardown on switch); user personas; system prompt editing + carousel; greetings + alternate greetings; lore compression (token-driven, writes only `thread.lore`).

**Automation (important):** built-in macros (`{{char}}`, `{{user}}`, `{{current_DAT}}` resolved at send, `{{continue}}`, `{{fast_forward}}`); auto-continue chains (20s gap, 50-post cap, runtime-only); custom macros (trigger validation + reserved names); scheduler (tab-open only, 30s check, no catch-up).

**Data (important):** export/import (merge by ID; full backup replaces everything); purge (factory reset behind confirm); save AI output as a file (extension restriction is prompt-level in source — see defect 5.7).

**Host (core/important):** authentication (salted SHA-256 password, fingerprint-bound HttpOnly cookie, 12h TTL, in-memory sessions); `/state` + `/state/info` (mtime in ms); `/llm/jobs` relay (byte-stable spool, base64 chunks, 4-worker cap → 429); `/swap-model` + `/swap-status` (lock file, phase machine); reverse proxies (streaming; `/llm` key injected server-side); static serving (traversal + dotfile guards); LAN setup + phone URL (mDNS/`.local`); first-run setup (password, engine, model, embed downloads — hash-verified).

**Optional:** token counter, CoT watchdog (default off), smart response limit (default off), banned words (broken in source — see defect accounting), web search (opt-in, needs Ollama key), file attachments, dashboard, avatar/background customization, model download menu, password reset.

### Scope Tiers

**Minimum viable port:** chat core (send/stream/stop/reroll/edit/threads), auth gate, provider adapter with `/llm` proxy + jobs relay, session store with IndexedDB + `/state` sync, message normalizer (SSE parsing + thinking formats), model selector + hot-swap, static serving. This is a usable single-user chatbot.

**Major-workflow parity:** everything in MVP plus characters/cards (import/export), RAG lorebook, lore compression, branching, macros, scheduler, data export/import/purge, extensions + per-card code, personas, system prompt carousel, LAN phone access.

**Full parity:** everything above plus web search, CoT watchdog, smart limit, banned words (fixed or honestly dropped), file attachments, hardware probe + download menu, installer/packaging.

## Protocols and Persisted State

Restated from the bundle §Protocol and State Notes. A reimplementation must preserve these exactly where marked.

**Wire formats:**

- **Chat completions + SSE parsing.** Request `{model:'local', messages, stream:true, max_tokens:-1}` + sampler params + family stop strings + logit_bias. Response `text/event-stream`; accept `data: {json}`, bare `{json}`, `data: [DONE]`/`[DONE]`; delta priority `reasoning_content → reasoning → content` plus Ollama-format tolerances. Parser must be a pure function of the byte stream.
- **Detached job relay.** `POST /llm/jobs` (body = byte-exact upstream request) → 202 `{id, status:'running'}`; `GET /llm/jobs/<id>?from=N[&max=M]` → `{id, status, size, next, chunk_b64?}`; `chunk_b64` = base64 of raw spool bytes from `from`; `max=0` = status-only peek. Job id = 32 lowercase hex. Terminal statuses `done|cancelled|error|interrupted`. Byte-stable transcript: replay from byte 0 is deterministic. 4-worker cap → 429; 48h retention; server restart flips running jobs to `interrupted`.
- **`/state` + mtime.** `GET /state/info` → `{mtime, size}` + `X-State-Mtime`; `GET /state` → body + header; `POST/PUT` → JSON-validated → `{status:'ok', mtime}`. mtime = file mtime in **milliseconds**. (Source is last-write-wins — the port must add a server-side conflict check per C05.)
- **Auth/session.** `POST /login` form-encoded `password=`; cookie `gobbonet_session` (HttpOnly, SameSite=Lax, Max-Age 43200, no Secure); token = 32 random bytes base64url; session bound to `SHA256(ip|User-Agent)`; in-memory table; `X-Gobbonet-Token` header fallback.
- **Hot-swap.** `POST /swap-model {file}` → 202 `{phase:'starting', …}`; `GET /swap-status` → `{phase, file, name, message, started_at, updated_at}`; phases `idle|starting|ready|error`; readiness = provider `/health` 200; lock file created first, removed only on ready/error/boot. (Source promotion is lazy — the port must add a server-side promotion timer per defect 3.2.)
- **Reverse proxies.** Path prefix stripped, query preserved; streaming chunked; `/llm` client Authorization replaced with server-side key; `/search` forwards Authorization verbatim (defect 4.1 — fix or correct the claim).
- **Embeddings.** `POST /v1/embeddings {input:'<prefix>'+text, model:'embed'}`; prefixes `search_document: `/`search_query: `; response `data.data[0].embedding`; cache key FNV-1a of `'d:'+text`.
- **web_search.** Client → proxy `POST /web_search {query, max_results:5}` + Bearer key; proxy → `https://ollama.com/api` verbatim; client-visible response `{results:[{title, content, url}]}`.
- **GGUF.** Magic `GGUF`, versions 2/3 only; consumed keys `tokenizer.chat_template`, `general.architecture`, `*.context_length`; template identity = SHA-256 of trimmed template; parse failure → filename-heuristic fallback.
- **Character cards.** `.json` (V1 flat / V2-V3 under `.data`), `.png` (tEXt/zTXt/iTXt `ccv3` preferred, `chara` fallback, base64 UTF-8), `.charx` ZIP (methods 0/8 only). Lorebook import is lossy (flattened).
- **Model metadata.** `active-model.json` `{id, name, family, ggufFile, maxCtx, defaultCtx, thinkingFormat}`; `models-list.json` `{active, models:[{file, id, name, family, thinkingFormat, maxCtx, useJinja, chatTemplate, chatTemplateFile, templateHash, active}]}`.
- **Env + secret.** `GEMMA_*` env handoff (C02); `.gobbonet-secret` = `<salt>:<hash>` (SHA-256 of salt+password, lowercase hex); consumer regex `^([0-9a-fA-F]+):([0-9a-fA-F]+)$`.
- **Export bundles.** Envelope `{gobbonet_export: threads|cards|personas|full, version:1, exported:<ms>, …}`; import merges by ID, full replaces.
- **`/tokenize` + logit_bias.** `POST {content}` → `{tokens}`; client builds map of token-id strings → strength (default -20); 8 case/space variants per phrase. **The port must send the OpenAI array shape `[{id, bias}]`** (defect 5.2).
- **Launch script.** Quoted exe + `--model --port 11434 --host 127.0.0.1 --ctx-size --n-gpu-layers --cache-type-k --cache-type-v --parallel 1` + one of `--jinja`/`--chat-template-file`/`--chat-template` + `--reasoning-format auto` [+ `--api-key`]; `mistral-v7-tekken` normalized to `mistral-v7`.

**State machines:**

- **Job lifecycle.** POST → running (202 is the only synchronous barrier); upstream 4xx/5xx → error; cancel flag → cancelled; EOF → done; restart → interrupted; DELETE on running → cancel flag; DELETE on terminal → deleted; >48h → deleted. Client: terminal+drained → folded; 404 → lost; 401 → unauthorized (source cancels the live job — defect 5.1, fix before porting); 50 network failures → unreachable (breadcrumb kept).
- **Swap phase machine.** idle → starting (lock first); health 200 → ready (lock removed); process dead >5s → error; >180s → error; boot → idle (stale lock/status deleted). Promotion must be server-side, not poll-driven (defect 3.2).
- **State-sync + boot decision matrix.** 2s debounced push, single-flight, transient-state guard, force-flush on settle, beacon on pagehide when settled. Boot: local empty + server data → silent auto-restore (once per tab session); server newer → prompt (unless server <50% local size → keep local, re-publish); older/match → noop; quota-truncation signature (server >1.2× local, not newer) → silent recovery.
- **Stream parser phases.** pre/thinking/content/between/done per thinking format; `serverSplit` latch on first server-routed reasoning delta; finalize at end-of-stream (flush, reparent implicit-think, scrub markers, unwrap tool-call envelope).
- **Jobs-availability probe.** unknown → 404/405 pins legacy-direct-stream forever; 202 pins relay; transient error → unknown (fall back this turn, re-probe next send).

**Persistence schemas:**

- **IndexedDB `gobbonet-state` v2:** stores `meta` (key `'app'`), `threads` (keyPath `id`), `vectors` (keyPath `hash`), `telemetry` (keyPath `turn_id`, ring 200). Thread order persisted separately as `threadOrder`. All migrations run on every load path.
- **localStorage mirror:** key `gobbonet_chat_state` (legacy `gemma4_chat_state` renamed); whole-blob rewrite; quota errors → `storageQuotaHit` → server backup becomes source of truth.
- **`/state` server blob:** shape = `buildStateBlob()`; `settings.apiKey` stripped; whole-file rewrite; mtime (ms) is the only version stamp (port adds a conflict check per C05).
- **Job spool** `.jobs/<id>.{sse,json,cancel}`: `.sse` append-only raw bytes; `.json` mutable with torn-read retry; `.cancel` flag file.
- **Swap state:** `.swap-status.json` + `.swap-in-progress` presence-only lock; both deleted at server boot.
- **Model metadata:** `active-model.json` / `models-list.json` whole-rewrite, no locking between writers.
- **`.gobbonet-secret`:** write-once; rename-to-`.bad` on verification failure.
- **Export bundles:** snapshot JSON, merge-by-ID import.

## External Dependencies

| Dependency | Stance (replace/wrap/emulate/postpone) | Rationale |
|---|---|---|
| llama.cpp `llama-server` (inference engine) | wrap | The product is a frontend for this API; the port wraps the same OpenAI-compatible surface (chat + embeddings + `/tokenize` + `/health`). |
| Browser (IndexedDB, localStorage, Page Lifecycle, fetch) | wrap | The UI surface is a browser app; a port keeps the browser and wraps its storage/lifecycle APIs behind the session store. |
| Ollama web_search API | wrap | Opt-in feature; the port keeps the proxy-forwarder shape (or implements the claimed privacy stripping — defect 4.1). |
| PowerShell HttpListener + runspaces | replace | Windows/.NET-specific; replace with a real async HTTP server and a bounded worker pool (keep the 4-worker cap semantics). |
| cmd batch orchestration (taskkill/tasklist/start/netsh) | replace | Windows-only; replace with the port's own supervisor (keep the supervision contract: health poll, restart from launch script, stand-down during swap). |
| Windows System32 tooling (curl/certutil/tar, ipconfig) | replace | Target-platform equivalents; keep the hash-verification discipline. |
| mDNS/`.local` | emulate | Target-platform zero-config hostname; keep the stable-bookmark advice + IP-change warning. |
| GGUF parsing | wrap | Parse v2/v3 metadata in the target language; keep the version gate + filename-heuristic fallback. |
| Character-card formats (PNG tEXt, ZIP) | wrap | Target-language PNG/ZIP libraries; keep the `ccv3`/`chara` chunk contract and the lossy-lorebook-flatten semantics. |
| AV-avoidance download patterns | postpone | Windows-Defender-specific; irrelevant on other platforms. Keep `.part` staging + hash verification regardless. |
| Installer/packaging (GobboNetSetup.exe) | postpone | Installer internals are outside the repo (q-installer-packaging); a port defines its own packaging. |

## Portability Hazards

Consolidated from the bundle §Portability Hazards (28 rows). The load-bearing ones for a reimplementation:

- **file:// vs served mode split** — two client modes with different capabilities. A port can drop file:// mode if it always serves; keep the endpoint-switch semantics if both modes are kept.
- **Client/server version skew** — keep the jobs-availability probe semantics (only a definitive 404/405 pins the fallback).
- **mtime protocol is advisory** — the port must add a server-side conflict check (C05).
- **GGUF v2/v3 only** — keep the version gate + fallback.
- **Card format versions + lossy lorebook flatten** — keep the field mapping; document the lossiness.
- **`mistral-v7-tekken` not registered in the pinned build** — keep the normalization to `mistral-v7`.
- **BOM-less UTF-8 discipline** — emit BOM-less UTF-8 for all server JSON.
- **Session state in-memory** — keep or improve (persist sessions); fix the 401 path (5.1).
- **Lazy swap readiness promotion** — add a server-side promotion timer (3.2).
- **Base64 chunk framing + byte offsets** — preserve `from`/`next`/`size` semantics exactly.
- **`max_tokens:-1` + client-side cap** — reproduce the client-side smart limit.
- **Family-keyed stop strings** — keep the family key registry.
- **Job id regex `^[0-9a-f]{32}$`** — keep the id format or update both sides.
- **`DecompressionStream` requirement** — target-runtime zlib equivalent.
- **No `crypto.subtle` on plain HTTP** — keep the FNV-1a fallback.
- **Wildcard CORS + cookie auth** — keep SameSite=Lax; scope CORS to the LAN origin.
- **Plain-HTTP LAN transport** — documented design choice with disclosed tradeoffs; the port re-makes the choice consciously (TLS, or keep + disclose).
- **Unsandboxed card code / extensions** — documented design choice; the port re-makes the choice consciously (keep opt-in + wrapped hooks, or sandbox).
- **Installer binaries absent from repo** — q-installer-packaging (needs-maintainer-decision).

## Implementation Sequence

1. **Provider adapter skeleton** — HTTP server, auth gate, `/llm` reverse proxy, static serving. Verify against a running llama-server.
2. **Message normalizer** — SSE parser, thinking-format parsers, model registry, GGUF metadata reader. Unit-test replay determinism (same bytes → same parse).
3. **Session store** — IndexedDB schema, migrations, localStorage mirror, `/state` sync + boot decision matrix.
4. **Agent loop** — send/stream/stop/reroll/edit/threads/branching against the adapter + store.
5. **Render loop** — chat UI, sidebar, modals, dashboard.
6. **Detached job relay** — spool, base64 chunks, resume, cancel, retention.
7. **Hot-swap** — lock file, phase machine with server-side promotion timer, metadata rewrite.
8. **Characters and RAG** — card import/export, dual retriever, lore compression.
9. **Automation** — macros, auto-continue, scheduler.
10. **Tool executor** — extensions, per-card code hooks, data export/import/purge.
11. **Supervisor** — process supervision, downloads with hash verification, first-run setup, LAN config.
12. **Optional features** — web search, CoT watchdog, smart limit, banned words (fixed per 5.2 or dropped), hardware probe, packaging.

## Acceptance Scenarios

Restated language-agnostically from behavioral-contracts.md §Black-Box Acceptance List (32 scenarios; targeted deep read — the bundle names this section as the source of acceptance detail).

| # | Scenario | Input | Expected Output / Side Effect |
|---|----------|-------|-------------------------------|
| 1 | First-run password | No secret file; run launcher; enter 5-char password | Rejected ("at least 6 characters"); re-prompt. |
| 2 | Login | Server running, password set; open the app URL | Login page; correct password → chat; wrong password → 401 with "Wrong password." |
| 3 | Session expiry | Valid session; wait 12h (or restart server) | Next request → 401/login; re-login works. |
| 4 | Cookie replay from another client | Session cookie copied to a different browser/device | Rejected (client fingerprint mismatch). |
| 5 | Streaming | Model loaded, thread open; send a message | Reply appears incrementally; token counter updates; thread floats to top. |
| 6 | Stop | Generation in flight; click Stop | Partial text kept with a stop note; input re-enabled; auto-continue chain (if any) cancelled. |
| 7 | Reroll variants | A completed assistant reply; reroll twice, then flip | Three variants flippable; flipping never regenerates; each variant's text/timer preserved. |
| 8 | Edit preserves branches | A user message with downstream replies; edit it | Old wording + its AI replies restorable via flip; new branch regenerated from the edit. |
| 9 | Branch | Any message; click Branch | New thread with shared history up to the branch point; original untouched. |
| 10 | Lore compression | Long thread, small token budget; keep chatting past it | "compressing…" indicator; older messages dimmed; summary in the lore inspector; chat never blocks. |
| 11 | Compression failure | Kill the inference engine mid-compression; send a message | Previous lore retained; failure reason recorded in the lore inspector. |
| 12 | Auto-continue | Type `{{auto_continue_3}}`; send | 3 total posts, 20s apart; indicator shows progress; CANCEL stops the chain. |
| 13 | Scheduler | One-time schedule 1 minute ahead; keep tab open; wait | Prompt injected into the target thread and sent; schedule removed. |
| 14 | Scheduler while closed | Schedule due; tab closed; wait past the time, reopen | Nothing fired (schedules run only while the chat is open). |
| 15 | Hot-swap | Two models available; pick the other in the dropdown | "Swapping…" → "Active: …"; dropdown disabled during swap; new model answers. |
| 16 | Hot-swap failure | Pick a model whose file was deleted | 404 surfaced in a toast; dropdown reverts to the previous model. |
| 17 | Export/import threads | Two devices or origins; export on A, import on B | Threads with new IDs added; existing IDs skipped with counts reported. |
| 18 | Full backup restore | A full backup file; import as full backup, confirm | All state replaced; extensions re-applied; settings from the backup active. |
| 19 | Purge | Data present; purge all, confirm | Factory defaults; data manager closes. |
| 20 | Card import | A V3 `.png` card with embedded code | Card appears; lorebook flattened to always-on lore; custom code present but **disabled**. |
| 21 | Card export | A card with a storybook; export | PNG downloads; contains `ccv3` + `chara` chunks; re-import round-trips the storybook. |
| 22 | Extensions | Add an inline script that changes the Send button text; enable; save | Script runs on save and on every boot; disabling removes it. |
| 23 | Card code teardown | Card A with code active; switch to card B | A's hooks discarded; B's code (if any) applied; switching back re-evaluates A. |
| 24 | Web search | API key set, toggle on; send a message | "searching…" then "found N results"; results block saved on the user message and included in context. |
| 25 | Web search without key | Toggle on, no key; send | "search ON but no API key set"; chat proceeds without search. |
| 26 | File save | Model outputs a ` ```file:notes.txt ` block; click Save | File downloads with that name and content. |
| 27 | Job resume | Send a message, immediately navigate away, return; reopen | Reply folded in silently (or re-attached live if still running); toast reports it. |
| 28 | Server restart mid-job | Generation in flight; restart the server; reload the client | Job status `interrupted`; partial text kept with an honest note. |
| 29 | State restore | New origin (cleared browser data), server has backup; open the app | Local empty → silent auto-restore from `/state`; chats reappear. |
| 30 | State conflict | Two devices edited; server newer than local; open the app | Prompt asking whether to restore; no silent clobber. |
| 31 | RAG degrade | Embed server down; chat with a card that has a storybook | Tag-only retrieval still works; chat never blocked. |
| 32 | Banned words | Card with banned phrases; send | Request body contains a `logit_bias` map — but per the source's README the words are NOT reliably suppressed (known bug; the port fixes per defect 5.2 or drops the feature). |

## Defect Accounting

All 34 findings (17 mechanical + 17 semantic) are accounted for. Dispositions carried forward from the bundle §Defect Synthesis.

**Designed-around (27)** — the port's design must handle these differently or fix them:

- **Fix before porting (12):** P1-1 (role-scoped process targeting, C04), P1-2 (identity-verified health probes, C03), P1-3 + 5.2 (logit_bias array shape), P1-4 (Tekken template re-verification), P6-1 (pin hashes at release), P6-2 (persist per-model ctx/kv), 3.2 (server-side swap promotion timer), 4.1 (implement search-privacy stripping or correct the claim), 4.2 (login rate limiting/lockout), 5.1 (error message matches recovery path, C06; keep the job alive across re-login), 5.4 (correct the lorebook auto-update claim or implement it).
- **Port differently (15):** P1-5 (distinguish never-customized from deliberately-default token limit), P2-1 (stream static responses; cap/allowlist paths), P2-2 (timeouts on all client fetches), P2-4 (unify proxy/job timeouts), P6-4 (configurable port + identity-verified probe), P6-5 (replace the Windows orchestration stack — this is the port itself), 3.1 (server-side compare-and-swap on `/state`, C05), 4.3 (request-body size caps), 4.4 (extension allowlist + explicit serve roots), 4.5 (no key material in logs), 4.6 (re-make the plain-HTTP choice consciously), 4.7 (re-make the unsandboxed-code choice consciously), 4.8 (scope CORS; keep SameSite=Lax), 5.3 (drop the vestigial reminderFrequency control), 5.7 (enforce the file-extension restriction or correct the README).

**Left behind (7)** — source-specific, won't survive porting: P1-6 (first-IPv4 LAN detection), P2-3 (PowerShell download fallback timeout), P2-5 (misleading fileserver-failure message), P6-3 (batch-only password check looseness), P6-6 (batch quoting of GGUF paths), 5.5 + 5.6 (stale in-code comments — write correct comments in the new code).

## Deliberate Non-Goals

- **file:// mode** — a port that always serves can drop it; keep only if both modes are wanted.
- **AV-avoidance download staging** — Windows-Defender-specific.
- **cmd batch ergonomics** (keep-open guard, console window manipulation) — replaced by the port's own supervisor.
- **Installer/packaging parity** — installer internals are outside the repo (q-installer-packaging); the port defines its own packaging.
- **Banned words (logit bias)** — broken in source; fix per 5.2 or drop honestly rather than reproduce the broken behavior.
- **Vestigial reminderFrequency setting** — dead control; do not reproduce.

## Coverage and limits

- Inspected scope: findings/porting/reverse-engineering-bundle.md (the compression boundary, read in full); targeted deep read of findings/contracts/behavioral-contracts.md §Black-Box Acceptance List (32 scenarios) — the bundle names it as the source of acceptance detail; CONVENTIONS.md (C01–C06), DECISIONS.md (D001–D011), workflow/status.yaml, the phase prompt, and templates/reimplementation-spec.md. No other upstream reports were deep-read — the bundle was self-sufficient for everything else.
- Skipped scope: no new source reading (synthesis phase; the bundle is the primary material). The five secondary outputs were not re-read (their summaries are carried in the bundle).
- Evidence basis: upstream findings (source inspection by six prior phases, all with file:line citations). No runtime verification (Windows-only; not executable in this environment), no tests in repo, no CI.
- Known blind spots: the 10 open questions carried from earlier phases (see §Known Unknowns); the Ollama web_search upstream schema beyond `{results:[{title,content,url}]}`; the definitive logit-bias root cause (5.2 is strong inference); installer binaries, REFACTOR-PLAN.md, and the fonts directory remain absent from the repo.
- Coverage disposition: COMPLETE — every load-bearing invariant, acceptance obligation, compatibility hazard, and defect disposition from the bundle is carried forward; porting-CF1 is closed by the language-agnostic selection recorded in the front-matter.

## Known Unknowns

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

Reimplementation-spec is the terminal phase; post-pipeline work goes here (per the template, target_phase values are spike/delta/amendment).

| ID | Target Phase | Description | Deferred Reason |
|---|---|---|---|
| post-lorebook-claim-ruling | amendment | README.md:317 claims lorebooks auto-update from conversations; code writes only `thread.lore`. Which side is intended needs the maintainer; the spec assumes the code is correct (defect 5.4). | Maintainer ruling; the pipeline cannot decide intent. |
| post-search-privacy-ruling | amendment | README.md:342 claims search metadata/telemetry are stripped; the code strips nothing (defect 4.1). The spec instructs the port to implement stripping or correct the claim — the maintainer picks which. | Maintainer ruling on the product's privacy promise. |

## Spike List

- **Logit-bias shape confirmation** — capture a live request against the pinned llama-server build (b9294) with the array-of-{id,bias} shape to confirm 5.2 before building the fix (q-logit-bias-root-cause).
- **SSE terminal bytes** — capture the pinned build's stream end (`data: [DONE]` vs close) to pin the spool contract (q-sse-done-marker).
- **Concurrent LAN clients** — load-test the accept-loop replacement under phone + desktop + streaming to validate the async server design (q-accept-loop-scale).
- **Tekken models** — run a Tekken-tokenizer model against the pinned build to measure the patch's residual misbehavior (q-tekken-patch-completeness).
- **Ollama web_search capture** — capture the upstream response schema to pin the search adapter (q-ollama-api-version, q-websearch-response-fields).

---

## Validation

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Concept-level modules are defined. | PASS | §Conceptual Module Model: 8 modules, each with responsibility, public inputs/outputs, owned state, invariants, collaborators. |
| 2 | Required behaviors are stated. | PASS | §Required Behaviors restates the bundle's 55 feature contracts grouped by area, with §Scope Tiers (MVP / major-workflow parity / full parity). |
| 3 | Protocol and persisted state expectations are stated. | PASS | §Protocols and Persisted State: 16 wire formats, 5 state machines, 8 persistence schemas, each with the exact semantics a port must preserve. |
| 4 | Acceptance scenarios and known unknowns are included. | PASS | §Acceptance Scenarios (32 rows, restated language-agnostically); §Known Unknowns (10 open questions with kinds and reasons). |
| 5 | Defects identified in either scan are explicitly designed-around or noted as "left behind", with the choice cited. | PASS | §Defect Accounting: all 34 findings (17 mechanical + 17 semantic) — 27 designed-around (12 fix before porting + 15 port differently) and 7 left behind, each with its disposition and design consequence. |
| 6 | Findings are marked with evidence levels. | PASS | Every section carries `observed fact` / `strong inference` / `portability hazard` / `open question` tags with upstream pointers; the two strong-inference items (5.2, layer composition) are labeled as such. |
| 7 | Coverage and limits name inspected scope, skipped scope, evidence basis, and blind spots. | PASS | §Coverage and limits lists all four plus disposition (COMPLETE) and names the one targeted deep read performed. |
| 8 | Lower-level findings are deep-read only when the porting bundle identifies a gap, conflict, missing acceptance detail, or defect rationale. | PASS | Exactly one targeted deep read (behavioral-contracts.md §Black-Box Acceptance List, named by the bundle as the source of acceptance detail); everything else came from the bundle. |

**Validated by:** reimplementation-spec phase, orchestrator inline session (2026-08-18)
**Selection:** language-agnostic (user-confirmed via the Strategic Alignment Hook; closes porting-CF1)
**Overall:** PASS
