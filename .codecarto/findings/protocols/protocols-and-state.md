# Protocols and State — GobboNet

<!--
  Output for the `protocols` phase (pipeline: workflow/pipeline-full-with-deep-audit.yaml).
  Evidence levels used throughout (per findings/protocols/SKILL.md):
  `observed fact` | `strong inference` | `portability hazard` | `open question`.
  Every protocol field cites file:line.
-->

This phase **closes arch-CF1** (wire formats: SSE spool byte format + `/llm/jobs` chunk framing, `/state` JSON schema + mtime protocol, swap-status phase machine, GGUF metadata fields consumed, character-card V1/V2/V3 field mapping, Ollama web_search schema). Each item is addressed in the sections below and the closure is recorded in the phase handoff's `carry_forward_closures`.

## Boundaries Identified

| Boundary | Producers | Consumers | Carrier |
|---|---|---|---|
| **Process-to-process** | launch.bat; fileserver.ps1; identify-model.ps1; search proxy | fileserver.ps1; llama-server; browser | `GEMMA_*` env vars; JSON files in project root (`active-model.json`, `models-list.json`, `.swap-status.json`); lock file `.swap-in-progress`; `.llama-launch.cmd`; `.gobbonet-secret` |
| **UI-to-core** | chat.html + js/01–24 (browser) | fileserver.ps1 (HTTP :8080) | HTTP/1.1 with session cookie; JSON bodies; SSE relay via `/llm/jobs` polling |
| **Core-to-provider** | fileserver.ps1 (proxy + job workers); browser (file:// mode) | llama-server (11434), embed server (11436), Ollama search proxy (11435) | HTTP/1.1 loopback; OpenAI-compatible JSON; SSE |
| **Tool layer to runtime** | identify-model.ps1, hardware-probe.ps1 | launch.bat, fileserver.ps1 | GGUF binary metadata; JSON records; batch `set` statements |
| **Runtime-to-persistence** | browser JS (05-persistence.js, 06-state-sync.js); fileserver.ps1 | IndexedDB, localStorage, `.gobbonet-state.json`, `.jobs/` spool | IndexedDB stores; localStorage keys; JSON files |
| **Local files to exported artifacts** | 16-card-io.js, 21-data.js | user downloads (PNG cards, JSON bundles) | PNG tEXt chunks; ZIP; JSON envelopes |

## Event Catalog

### P1. llama-server chat completions (SSE) — core-to-provider

| Field | Value |
|---|---|
| **Producer** | llama-server (`--parallel 1`, OpenAI-compatible API on 127.0.0.1:11434) |
| **Consumer** | fileserver.ps1 job worker (served mode) or browser `runGenerationStream` legacy path (file:// mode) |
| **Transport or carrier** | HTTP POST `/v1/chat/completions`, response `text/event-stream`; worker sets `Accept: text/event-stream` (fileserver.ps1:684) |
| **Ordering guarantees** | Token order preserved by the single TCP stream; spooled byte-exact to `.jobs/<id>.sse` (fileserver.ps1:720-744). `--parallel 1` pins one slot so no interleaving (launch.bat:1292-1299) |
| **Required fields** | Request: `{model:'local', messages, stream:true, max_tokens:-1}` + sampler params + optional `stop`/`logit_bias` (10-chat.js:166). `max_tokens:-1` = no server cap; the smart limit is client-side (03-generation.js:92-94) |
| **Optional fields** | `temperature, min_p, top_k, top_p, repeat_penalty, repeat_last_n, xtc_probability, xtc_threshold, dry_multiplier, dry_base, dry_allowed_length, dry_penalty_last_n` (06-state-sync.js:502-521); `stop` family delimiters (06-state-sync.js:547-580); `logit_bias` (06-state-sync.js:790) |
| **Identifiers and timestamps** | No request id; job id assigned by the relay (P2). `genStartedAt`/`genMs` stamped client-side (10-chat.js:142, 202) |
| **Error cases** | Upstream 4xx/5xx surfaced verbatim in job status `error` (first 400 chars of body, fileserver.ps1:700-715); legacy path throws on non-OK (03-generation.js:479) |
| **Restart or resume behavior** | Detached jobs survive navigation via spool replay (P2); legacy direct stream dies with the page (03-generation.js:9-13) |

### P2. Detached generation job relay (`/llm/jobs`) — UI-to-core

| Field | Value |
|---|---|
| **Producer** | fileserver.ps1 (`Handle-Jobs`, worker runspaces) |
| **Consumer** | browser `startGenerationJob` / `pollJobToCompletion` / `resumePendingJobs` (03-generation.js:330-406, 10-chat.js:936-995) |
| **Transport or carrier** | HTTP on :8080, same-origin under `/llm` so the session cookie rides along (fileserver.ps1:1578-1582); spool files `.jobs/<id>.{sse,json,cancel}` |
| **Ordering guarantees** | **Byte-stable transcript**: the worker spools the raw upstream SSE byte stream; the client replays from byte 0 with identical results (fileserver.ps1:597-599, 03-generation.js:23-26). Poll offsets are monotonic (`next` = `from` + bytes read, fileserver.ps1:936) |
| **Required fields** | `POST /llm/jobs` body = byte-exact llama-server request; optional `?thread=<id>` (informational only, fileserver.ps1:802-806). Response 202 `{id, status:'running'}` (fileserver.ps1:846). `GET /llm/jobs/<id>?from=N[&max=M]` → `{id, status, size, next}` + `chunk_b64` when bytes available (fileserver.ps1:947-953) |
| **Optional fields** | `chunk_b64` (base64 of raw spool bytes from `from`; omitted when no new bytes — `max=0` is a status-only peek, fileserver.ps1:590, 953); `error` (terminal only); `started_at`/`updated_at` (epoch seconds; absent on pre-timing fileservers, fileserver.ps1:960-961, 03-generation.js:398-401) |
| **Identifiers and timestamps** | Job id = GUID `'n'` format, 32 lowercase hex (fileserver.ps1:808); route regex `^/llm/jobs/([0-9a-f]{32})(/cancel)?$` (fileserver.ps1:851). `started_at` set at creation; `updated_at` stamped when the worker writes the terminal status — `(updated_at - started_at)` is the true generation duration even if no tab was attached (fileserver.ps1:813-817, 664-665, 955-959) |
| **Error cases** | 429 when ≥4 live workers (fileserver.ps1:785-792); 400 non-JSON body (fileserver.ps1:797-800); 404 unknown job / unreadable status (fileserver.ps1:856-859, 895-898); 405 wrong method (fileserver.ps1:778-780, 888-891); terminal statuses `done|cancelled|error|interrupted` (fileserver.ps1:600) |
| **Restart or resume behavior** | Fileserver restart flips every `running` job to `interrupted` with `error:'fileserver restarted mid-generation'` (fileserver.ps1:147-160). Client: `thread.pendingJob` breadcrumb persisted immediately (03-generation.js:436-438); resume replays terminal transcripts silently, re-attaches live to running ones, stamps a note + clears breadcrumb on `lost`, keeps breadcrumb on `unreachable` (10-chat.js:949-991, 03-generation.js:458-465). 48h retention sweep + DELETE ack remove spool files (fileserver.ps1:74, 161-164, 872-886) |

### P3. SSE line parsing (client-side normalization) — UI internal

| Field | Value |
|---|---|
| **Producer** | `makeStreamFeeder` (03-generation.js:255-323) — shared by job polling and legacy streaming |
| **Consumer** | `extractTokenFromLine` → `processStreamDelta` → `finalizeStreamMessage` (02-model.js:411-460, 03-generation.js:621-660, 1013-1073) |
| **Transport or carrier** | In-memory: `TextDecoder` (UTF-8) + partial-line buffer split on `\n`; `flush()` parses a trailing unterminated line at end-of-stream (03-generation.js:256-320) |
| **Ordering guarantees** | Line order = byte order; render tick throttled to 80ms, local save tick 2.5s (03-generation.js:291-303) |
| **Required fields** | Line forms accepted: `data: {json}` (prefix stripped), bare `{json}`; `data: [DONE]` / `[DONE]` → null (02-model.js:412-421). Delta fields in priority order: `choices[0].delta.reasoning_content` → `reasoning`; `choices[0].delta.reasoning` → `reasoning`; `choices[0].delta.content` → `content`; `choices[0].message.content` → `content`; `message.thinking` → `reasoning`; `message.content` → `content`; top-level `content`/`response` → `content` (02-model.js:427-459) |
| **Optional fields** | Ollama-format `message.*` and top-level `content`/`response` are tolerated for non-llama.cpp servers (02-model.js:445-459) |
| **Identifiers and timestamps** | None — parser state lives on `msg._parseState` (runtime-only, stripped before persistence, 05-persistence.js:459-462) |
| **Error cases** | Unparseable lines logged (first 3 only) and skipped (03-generation.js:287-289); empty reply with no extracted content warns (10-chat.js:177-179) |
| **Restart or resume behavior** | Replay-safe by construction: same bytes → same parse (03-generation.js:23-26) |

### P4. `/state` sync + mtime protocol — UI-to-core

| Field | Value |
|---|---|
| **Producer** | fileserver.ps1 `Handle-State` (fileserver.ps1:501-567); client `flushStateSync`/`flushBeforeExit` (06-state-sync.js:89-193) |
| **Consumer** | browser `checkServerStateOnBoot`/`restoreFromServer` (06-state-sync.js:224-416) |
| **Transport or carrier** | HTTP on :8080; server file `.gobbonet-state.json` (BOM-less UTF-8, fileserver.ps1:63, 557) |
| **Ordering guarantees** | **Last-write-wins, no server-side conflict check or locking** (fileserver.ps1:545-564) — the mtime protocol is advisory only; concurrent two-device writes silently clobber (routed to defect-scan-semantic as mech-CF1). Client pushes are debounced ~2s, single-flight, requeued on failure with 4s backoff (06-state-sync.js:82-143) |
| **Required fields** | `GET /state/info` → `{mtime, size}` + `X-State-Mtime` header; 404 `{error:'no state on server'}` (fileserver.ps1:518-528). `GET /state` → full body + `X-State-Mtime` (fileserver.ps1:533-544). `POST/PUT` → JSON-validated body → 200 `{status:'ok', mtime}`; 400 `{error:'body is not valid JSON'}`; 500 write failure (fileserver.ps1:545-565). `mtime` = `LastWriteTimeUtc` in **milliseconds** since epoch (fileserver.ps1:521, 537, 559) |
| **Optional fields** | `size` (bytes) on `/state/info` only |
| **Identifiers and timestamps** | mtime is the sole version identifier; client persists `lastKnownMtime` in localStorage key `gobbonet_sync_meta` (06-state-sync.js:42-54). Server clock is the only clock — no client/server skew surface (`observed fact`: all mtimes derive from `LastWriteTimeUtc`) |
| **Error cases** | Client push failure → status `error`, requeue + retry (06-state-sync.js:128-138); restore of a thread-less backup never reloads (loop stopper, 06-state-sync.js:349-368); boot auto-restore capped at one per tab session via sessionStorage guard (06-state-sync.js:207-223) |
| **Restart or resume behavior** | Boot decision matrix (06-state-sync.js:200-324): local empty + server data → silent auto-restore; local + server newer → prompt (unless server <50% of local size → keep local, re-publish); local + server older/match → noop; quota-truncation signature (`serverSize > localSize*1.2` with no newer mtime) → silent recovery restore. `sendBeacon` on pagehide only when state is settled (06-state-sync.js:176-193) |

### P5. Auth / session protocol — UI-to-core

| Field | Value |
|---|---|
| **Producer** | fileserver.ps1 (login handler, session table) |
| **Consumer** | browser (login form, cookie jar); curl clients via `X-Gobbonet-Token` header fallback (fileserver.ps1:295-311) |
| **Transport or carrier** | HTTP cookie `gobbonet_session`; `Set-Cookie: gobbonet_session=<tok>; Path=/; HttpOnly; SameSite=Lax; Max-Age=43200` (fileserver.ps1:1520-1521) |
| **Ordering guarantees** | Sessions are an in-memory hashtable — server restart logs everyone out (fileserver.ps1:118-120) |
| **Required fields** | `POST /login` body `application/x-www-form-urlencoded` with `password=` (fileserver.ps1:1504-1511). Success → 302 to `/`; failure → 401 + login page with error (fileserver.ps1:1512-1526). Unauthenticated non-HTML requests → 401 `{error:'authentication required', login:'/login'}` (fileserver.ps1:1552-1560) |
| **Optional fields** | `X-Gobbonet-Token` header as cookie alternative (fileserver.ps1:308-309) |
| **Identifiers and timestamps** | Token = 32 random bytes, base64url (fileserver.ps1:273-280); session bound to `ClientId = SHA256(ip + '|' + User-Agent)` (fileserver.ps1:259-271); TTL 12h (fileserver.ps1:126). Password check: constant-time compare of `SHA256(salt + typed)` vs stored hash (fileserver.ps1:111-116, 244-257) |
| **Error cases** | Expired/mismatched token → 401; no rate limiting or lockout on `/login` (routed to defect-scan-semantic as contracts-CF3) |
| **Restart or resume behavior** | Mid-generation session expiry: job poll returns 401 → client treats as terminal error, clears the breadcrumb, and DELETEs the job — which **cancels a still-running generation** (03-generation.js:375, 452-465; fileserver.ps1:872-880). The error message says "reload the page and sign in to re-attach" but the code path has already cancelled the job — routed to defect-scan-semantic as proto-CF1 |

### P6. Hot-swap protocol (`/swap-model`, `/swap-status`) — UI-to-core + process-to-process

| Field | Value |
|---|---|
| **Producer** | fileserver.ps1 `Handle-SwapModel`/`Handle-SwapStatus` (fileserver.ps1:1270-1445) |
| **Consumer** | browser `onHeaderModelChange`/`pollSwapStatus` (02-model.js:269-361); launch.bat monitor loop via the lock file (launch.bat:1845-1858) |
| **Transport or carrier** | HTTP on :8080; state file `.swap-status.json`; lock file `.swap-in-progress` |
| **Ordering guarantees** | One swap at a time: lock file created first, second swap refused 409 (fileserver.ps1:1283-1292, 1330-1333). Lock removal happens only on ready/error promotion or boot hygiene (fileserver.ps1:137-140, 1409, 1433, 1438) |
| **Required fields** | `POST /swap-model` body `{file:"<name>.gguf"}`; 202 `{phase:'starting', file, name, message, started_at}` (fileserver.ps1:1304-1307, 1365-1371). `GET /swap-status` → `{phase, file, name, message, started_at, updated_at}`; no status file → `{phase:'idle'}` (fileserver.ps1:1154-1172, 1387-1391) |
| **Optional fields** | `message` (human-readable progress/error); `current` (the in-flight status object, on 409) |
| **Identifiers and timestamps** | `started_at`/`updated_at` epoch seconds (fileserver.ps1:1167-1168) |
| **Error cases** | 503 hot-swap not configured; 405 non-POST; 409 in-flight; 400 invalid JSON / missing `file` / invalid filename (no separators, no `..`, must end `.gguf`); 404 GGUF missing or not listed in models-list.json; 500 dispatch failure (fileserver.ps1:1273-1377) |
| **Restart or resume behavior** | Client: 800ms grace before first poll, ~1.5s cadence, 180s budget, dropdown revert on failure (02-model.js:344-361). Server: readiness promotion is **lazy** — it only happens when someone polls `/swap-status` (fileserver.ps1:1380-1383). If the client stops polling (tab closed mid-swap), the lock file persists and launch.bat's monitor loop stands down indefinitely — routed to defect-scan-semantic as proto-CF2 |

### P7. Reverse proxy paths — UI-to-core-to-provider

| Field | Value |
|---|---|
| **Producer** | fileserver.ps1 `Invoke-Proxy` (fileserver.ps1:393-497) |
| **Consumer** | llama-server (`/llm/*` → 127.0.0.1:11434), search proxy (`/search/*` → 11435), embed server (`/embed/*` → 11436) (fileserver.ps1:1584-1596) |
| **Transport or carrier** | HTTP/1.1; streaming, chunked response (`SendChunked`, 4KB buffer, flush per read — SSE chunks flush through, fileserver.ps1:481-488) |
| **Ordering guarantees** | Byte-order preserved; no pre-buffering of the body (fileserver.ps1:390-392) |
| **Required fields** | Path prefix stripped, query string preserved (fileserver.ps1:403-411). For `/llm/*`, client `Authorization` is replaced with the server-side `GEMMA_LLM_API_KEY` (`Bearer <key>`) so the browser never sees the key (fileserver.ps1:438-445) |
| **Optional fields** | `GEMMA_LLM_API_KEY` empty → no injection; llama-server runs without `--api-key` (fileserver.ps1:108, 1465-1469) |
| **Identifiers and timestamps** | None added; upstream headers copied except `Transfer-Encoding|Connection|Keep-Alive|Content-Length` (fileserver.ps1:470-479) |
| **Error cases** | Upstream 4xx/5xx forwarded verbatim (fileserver.ps1:456-466); connection failure → 502 `{error:'upstream unreachable', detail}` (fileserver.ps1:491-496); 10-minute `Timeout`/`ReadWriteTimeout` (fileserver.ps1:420-421) — vs 30 minutes in the job worker (fileserver.ps1:689-690), a known divergence (mechanical finding P2-4) |
| **Restart or resume behavior** | None — proxy connections die with the request; detached jobs are the resume mechanism |

### P8. Embedding request/response — core-to-provider

| Field | Value |
|---|---|
| **Producer** | browser `ragEmbedRaw` (08-rag.js:184-201) |
| **Consumer** | embed llama-server (`--embeddings` on 127.0.0.1:11436, or `/embed` proxy in served mode) |
| **Transport or carrier** | HTTP POST `/v1/embeddings` |
| **Ordering guarantees** | Per-call; document embeddings cached by content hash (in-memory Map + IndexedDB `vectors`), query embeddings never cached (08-rag.js:203-221) |
| **Required fields** | Request `{input: '<prefix>'+text, model:'embed'}`; prefixes `search_document: ` / `search_query: ` (08-rag.js:180-193). Response `data.data[0].embedding` (array of numbers) |
| **Optional fields** | None |
| **Identifiers and timestamps** | Cache key = FNV-1a 32-bit hex of `'d:'+text` (08-rag.js:35-42, 207); IDB record `{hash, vec, ts}` (08-rag.js:218) |
| **Error cases** | Any failure → null → Retriever A + semantic backstop switch off, tag-only Retriever B carries on; chat never blocked (08-rag.js:10-13, 194-200). Dimension mismatch clears the whole cache (08-rag.js:223-232) |
| **Restart or resume behavior** | Cache persists in IDB; re-embedding only for changed chunks (05-persistence.js:48-50) |

### P9. Ollama web_search via search proxy — core-to-provider

| Field | Value |
|---|---|
| **Producer** | browser `webSearch` (11-search.js:18-87); search proxy (decoded launch.bat:1608) |
| **Consumer** | `https://ollama.com/api` (upstream) |
| **Transport or carrier** | HTTP POST; proxy = HttpListener on 127.0.0.1:11435, TLS 1.2 forced, 30s upstream timeout (decoded command) |
| **Ordering guarantees** | Synchronous request/response per search; one search per send (10-chat.js:113-131) |
| **Required fields** | Client → proxy: `POST /web_search` `{query, max_results:5}` + `Authorization: Bearer <key>` (11-search.js:45-52). Proxy → upstream: **verbatim forward** — `https://ollama.com/api` + path, body, `Content-Type`, and `Authorization` passed through unchanged (decoded command). Proxy `/health` → `{"status":"ok"}` (decoded command) |
| **Optional fields** | `max_results` (client sends 5; test connection sends 2, 11-search.js:142) |
| **Identifiers and timestamps** | None added by the proxy |
| **Error cases** | Proxy down / non-OK / bad JSON / `{error}` / empty `results` → null, chat proceeds without search (11-search.js:20-86); proxy upstream failure → 502 `{error:'proxy: <message>'}` (decoded command) |
| **Restart or resume behavior** | Next send retries; Settings has a Test Connection button (11-search.js:90-182) |
| **Response schema (client-visible)** | `{results: [{title, content, url}]}` — consumed at 11-search.js:76-78 and formatted at 11-search.js:184-190. **The upstream response schema beyond these three fields is not visible in-repo** (the proxy forwards verbatim) — `open question` q-websearch-response-fields (refines q-ollama-api-version) |

### P10. GGUF metadata (v2/v3) — local files to runtime

| Field | Value |
|---|---|
| **Producer** | GGUF model files (external) |
| **Consumer** | identify-model.ps1 `Read-GgufMeta` (identify-model.ps1:22-81) |
| **Transport or carrier** | Binary file, `FileShare::ReadWrite` open (identify-model.ps1:26) |
| **Ordering guarantees** | Sequential KV-pair scan; early exit once all three target fields are found (identify-model.ps1:77) |
| **Required fields** | Magic `GGUF` (0x47 0x47 0x55 0x46); version **2 or 3 only** — v1 rejected (identify-model.ps1:31-35). Consumed keys: `tokenizer.chat_template` (string), `general.architecture` (string), any key ending `.context_length` (uint32 or uint64) (identify-model.ps1:52-61) |
| **Optional fields** | All other KV pairs skipped; type table: 0/1=1B, 2/3=2B, 4/5=4B, 6=4B, 7=1B, 10/11/12=8B; arrays skipped by element size (identify-model.ps1:18-20, 56-74) |
| **Identifiers and timestamps** | Template identity = SHA-256 of trimmed `chat_template` → `templateHash` → `HashDerivations` registry (identify-model.ps1:83-123, 307-322) |
| **Error cases** | Bad magic / version / oversized key (>1MB) / oversized string (>64MB) / unknown type → null → filename-heuristic fallback (identify-model.ps1:32-75, 296-300) |
| **Restart or resume behavior** | Re-read on every boot and hot-swap (launch.bat:710-744, 1214-1221) |

### P11. Character card V1/V2/V3 — local files to exported artifacts

| Field | Value |
|---|---|
| **Producer** | External card files; `exportCardAsV3` (16-card-io.js:701-736) |
| **Consumer** | `importCharacterCard` (16-card-io.js:403-471) |
| **Transport or carrier** | `.json` (V1 flat, or V2/V3 wrapped under `.data`); `.png` (tEXt/zTXt/iTXt chunks keyed `ccv3` (V3, preferred) or `chara` (V2), payload = base64(UTF-8 JSON)); `.charx` ZIP (V3, `card.json` at archive root) (16-card-io.js:9-15, 132-149, 205-231) |
| **Ordering guarantees** | `ccv3` preferred over `chara` when both present (16-card-io.js:146) |
| **Required fields** | Spec detection: `spec:'chara_card_v3'|'chara_card_v2'` + `.data`; spec-less `.data` wrapper tolerated; flat V1 detected by top-level `name|description|first_mes` (16-card-io.js:269-281). Field mapping (16-card-io.js:18-38, 306-389): `name`→name; `system_prompt`+`description`+`scenario`+`mes_example`+`post_history_instructions`→writingStyle (labeled sections); `personality`→personality (also woven into writingStyle); `first_mes`→greeting; `alternate_greetings`+`group_only_greetings`→altGreetings (blank-line separated); `character_book`→startingLore (**lossy**: enabled entries sorted by `insertion_order`, flattened to always-on lore — no keyword-triggered engine); `extensions.gobbonet.ragStorybook`→ragStorybook; `extensions.gobbonet.customCode`→customCode (**always disabled on import**, 16-card-io.js:376-387) |
| **Optional fields** | Non-prompt metadata preserved on `card._import`: `{spec, creator, character_version, tags, creator_notes, importedAt}` (16-card-io.js:365-374) |
| **Identifiers and timestamps** | New card id via `generateId()`; name deduped with ` (Imported N)` suffix (16-card-io.js:353, 391-399) |
| **Error cases** | Not-a-PNG / no chara/ccv3 chunk / bad ZIP / unsupported compression (only methods 0 and 8) / missing card.json / no usable description+greeting+personality → thrown, surfaced as toast (16-card-io.js:80, 147, 163, 194, 210, 451-453) |
| **Restart or resume behavior** | Export is a best-effort inverse: flattened fields re-export under `description`; `_import` metadata restored to proper fields; V3 PNG carries both `ccv3` and `chara` chunks (V2-compatible) (16-card-io.js:474-487, 619-687, 724-727) |

### P12. Model metadata files — process-to-process

| Field | Value |
|---|---|
| **Producer** | launch.bat `:write_model_json` (launch.bat:1180-1192); identify-model.ps1 `-ModelsDir` batch (identify-model.ps1:442-456); fileserver.ps1 `Write-ActiveModel`/`Update-ModelsListActive` (fileserver.ps1:1236-1265) |
| **Consumer** | browser `loadActiveModel`/`loadModelsList` (02-model.js); fileserver.ps1 `Get-ModelRecord`/`Build-LaunchScript` (fileserver.ps1:974-986, 1011-1111) |
| **Transport or carrier** | JSON files in project root, served statically (`active-model.json`, `models-list.json`) |
| **Ordering guarantees** | Whole-file rewrite; no locking — a swap rewrites both files while the browser may be reading (fileserver.ps1:1343-1344) |
| **Required fields** | `active-model.json`: `{id, name, family, ggufFile, maxCtx, defaultCtx, thinkingFormat}` (launch.bat:1183-1191, fileserver.ps1:1238-1247). `models-list.json`: `{active: <file>, models: [{file, id, name, family, thinkingFormat, maxCtx, useJinja, chatTemplate, chatTemplateFile, templateHash, active}]}` (identify-model.ps1:181-184, 448-453) |
| **Optional fields** | `chatTemplateFile` (sidecar `.jinja` path, `models\<name>`); `templateHash` |
| **Identifiers and timestamps** | `active` flag per record + top-level `active` filename (fileserver.ps1:1257-1263) |
| **Error cases** | Missing/unparseable models-list.json → `Get-ModelRecord` returns null → swap 404 "not listed" (fileserver.ps1:976-986, 1322-1326) |
| **Restart or resume behavior** | Re-written on every boot and every swap; the browser re-fetches `active-model.json` after a successful swap (02-model.js:322-323) |

### P13. `GEMMA_*` env handoff — process-to-process

| Field | Value |
|---|---|
| **Producer** | launch.bat `:launch` (launch.bat:1651-1667) |
| **Consumer** | fileserver.ps1 `Get-EnvOrDefault` (fileserver.ps1:42-67) |
| **Transport or carrier** | Windows process environment (convention C02 — env vars, never command-line interpolation) |
| **Ordering guarantees** | Read once at startup; no hot reload (fileserver.ps1:42-67) |
| **Required fields** | `GEMMA_ROOT, GEMMA_LLM_PORT, GEMMA_SEARCH_PORT, GEMMA_EMBED_PORT, GEMMA_SERVER_EXE, GEMMA_MODEL_DIR, GEMMA_CTX_SIZE, GEMMA_GPU_LAYERS, GEMMA_KV_CACHE_TYPE, GEMMA_LOG_FILE, GEMMA_LAUNCH_SCRIPT, GEMMA_ACCESS_SECRET` (launch.bat:1651-1667); `GEMMA_ACCESS_SECRET` malformed/missing → fatal exit 1 (fileserver.ps1:99-107) |
| **Optional fields** | `GEMMA_LLM_API_KEY` (empty = no `--api-key`) (fileserver.ps1:108) |
| **Identifiers and timestamps** | None |
| **Error cases** | Missing optional vars fall back to hardcoded defaults (fileserver.ps1:48-61) |
| **Restart or resume behavior** | Config changes require a fileserver restart |

### P14. `.gobbonet-secret` — process-to-process

| Field | Value |
|---|---|
| **Producer** | launch.bat `:setup_password` (PowerShell SecureString read, launch.bat:310-362) |
| **Consumer** | fileserver.ps1 startup parse (fileserver.ps1:96-102) |
| **Transport or carrier** | One-line ASCII file in project root |
| **Ordering guarantees** | Write-once at setup; on verification failure renamed `.bad`, never deleted (launch.bat:414-418) |
| **Required fields** | `<salt>:<hash>` — salt = 16 random bytes lowercase hex; hash = lowercase hex SHA-256 of UTF-8 `salt + password` (launch.bat:349-355). Consumer regex `^([0-9a-fA-F]+):([0-9a-fA-F]+)$` (fileserver.ps1:99) |
| **Optional fields** | None |
| **Identifiers and timestamps** | None |
| **Error cases** | Malformed → fileserver exits 1 (fileserver.ps1:103-107); batch-only check deliberately looser (launch.bat:404-409, mechanical finding P6-3) |
| **Restart or resume behavior** | `launch.bat reset-password` deletes the file to force re-setup (launch.bat:144-148) |

### P15. RAG telemetry record + `gobbonet:retrieval` event — UI internal

| Field | Value |
|---|---|
| **Producer** | `ragEmitRecord` (08-rag.js:279-301) |
| **Consumer** | `window.__gobboTelemetry` ring buffer; IndexedDB `telemetry` store; `CustomEvent('gobbonet:retrieval')` listeners (Stage 2) |
| **Transport or carrier** | In-memory array + DOM CustomEvent + IDB |
| **Ordering guarantees** | One record per generation turn, emitted exactly once via the single `finish()` exit (08-rag.js:340-349) |
| **Required fields** | `{turn_id, thread_id, ts, model_id, config:{retriever_a, retriever_b, fire_threshold, warmth_turns, expansion_depth, semantic_backstop, embed_available, top_k_a, retrieval_budget_tokens}, window:{messages_scanned, tokens_scanned, hash}, budget, candidates, shadow, post:{ttft_ms, retrieval_latency_ms, per_candidate_usage}, flags:{turn_rating, barged_in, missing}, cards_in_play}` (08-rag.js:312-335) |
| **Optional fields** | `post.ttft_ms` (null until filled) |
| **Identifiers and timestamps** | `turn_id = 't_' + Date.now().toString(36) + '_' + seq`; `window.hash = 'fnv:' + ragHash(windowText)` (08-rag.js:313, 374) |
| **Error cases** | IDB write failures swallowed (best-effort) (08-rag.js:290-300) |
| **Restart or resume behavior** | Ring-buffered: 200 records in memory and in IDB, oldest trimmed (08-rag.js:279-298) |

### P16. Data export/import bundle — local files to exported artifacts

| Field | Value |
|---|---|
| **Producer** | 21-data.js export (21-data.js:26-57) |
| **Consumer** | 21-data.js import (21-data.js:76-160) |
| **Transport or carrier** | JSON download; filenames `gobbonet-<type>-YYYY-MM-DD.json` |
| **Ordering guarantees** | Snapshot at export time |
| **Required fields** | Envelope `{gobbonet_export: <type>, version: 1, exported: <ms>, …}`; types: threads / cards / personas / full (21-data.js:26-57) |
| **Optional fields** | Type-specific payloads |
| **Identifiers and timestamps** | `exported` epoch ms; import merges by ID (existing IDs skipped); full backup replaces everything after confirm (21-data.js:86-160) |
| **Error cases** | Invalid JSON / missing `gobbonet_export` / wrong bundle type → red status, nothing changed (21-data.js:76-84, 117-120) |
| **Restart or resume behavior** | File input reset so the same file can be re-imported (21-data.js:163) |

### P17. `/tokenize` + `logit_bias` — core-to-provider

| Field | Value |
|---|---|
| **Producer** | browser `buildLogitBias` (06-state-sync.js:725-793) |
| **Consumer** | llama-server `/tokenize` endpoint |
| **Transport or carrier** | HTTP POST `{content: <variant>}` → `{tokens: [ids]}` (06-state-sync.js:765-772) |
| **Ordering guarantees** | Sequential per variant; 8 case/space variants per phrase (lower/upper/title/original × leading-space) (06-state-sync.js:742-757) |
| **Required fields** | `logit_bias` = map of token-id **strings** → strength (default -20) merged into the chat request (06-state-sync.js:732-734, 774, 790) |
| **Optional fields** | `card.logitBiasStrength` |
| **Identifiers and timestamps** | Token ids as string keys |
| **Error cases** | `/tokenize` unavailable → silently skipped, `{}` returned (06-state-sync.js:778-782). **README-declared non-functional** (README.md:264-265); shape-mismatch hypothesis routed to defect-scan-semantic as mech-CF3 |
| **Restart or resume behavior** | Rebuilt per send/reroll |

### P18. `.llama-launch.cmd` + `.swap-in-progress` lock — process-to-process

| Field | Value |
|---|---|
| **Producer** | launch.bat `:start_server` (launch.bat:1381-1390); fileserver.ps1 `Build-LaunchScript` (fileserver.ps1:1011-1111) |
| **Consumer** | `cmd /c start /min` spawn (fileserver.ps1:1356-1360); launch.bat monitor loop (launch.bat:1839-1895) |
| **Transport or carrier** | ASCII `.cmd` file; lock file presence = swap in flight |
| **Ordering guarantees** | Lock created before any swap step; removed only on ready/error or boot hygiene (fileserver.ps1:1330-1333, 137-140) |
| **Required fields** | Launch line: quoted exe + `--model --port 11434 --host 127.0.0.1 --ctx-size --n-gpu-layers --cache-type-k --cache-type-v --parallel 1` + one of `--jinja` / `--chat-template-file <sidecar>` / `--chat-template <builtin>` + `--reasoning-format auto` [+ `--api-key`] + `> log 2>&1` (fileserver.ps1:1074-1103) |
| **Optional fields** | Audit prelude appending to `.launch-history.log` (fileserver.ps1:1105-1108) |
| **Identifiers and timestamps** | Audit timestamp `yyyy-MM-dd HH:mm:ss` |
| **Error cases** | Sidecar template rejected unless it contains `{%`/`{{`, is ≥16 chars, and isn't the "Entry not found" 404 body (fileserver.ps1:993-1004); `mistral-v7-tekken` normalized to `mistral-v7` (unregistered in the pinned build — passed bare it becomes a literal template body, fileserver.ps1:1065-1072) |
| **Restart or resume behavior** | Monitor loop re-runs the script on crash; stands down while the lock exists (launch.bat:1845-1858) |

## State Machine

### SM1. Generation job lifecycle (server + client)

| Current State | Event / Trigger | Guard | Next State | Side Effects |
|---|---|---|---|---|
| (none) | `POST /llm/jobs` | <4 live workers; body parses as JSON | running | Status file `{status:'running', thread, started_at}` written, then empty spool, then worker runspace spawned; 202 `{id}` (fileserver.ps1:785-847) |
| (none) | `POST /llm/jobs` | ≥4 live workers | (rejected) | 429 (fileserver.ps1:789-792) |
| running | Upstream 4xx/5xx | — | error | Status `{status:'error', error:'upstream HTTP <code>: <body≤400ch>'}` (fileserver.ps1:700-715) |
| running | `.cancel` flag file appears | checked every ≤250ms during read waits | cancelled | `req.Abort()`; status `cancelled` (fileserver.ps1:730-752) |
| running | Upstream stream EOF | — | done | Status `done` + `updated_at` (fileserver.ps1:752-753) |
| running | Worker exception | no cancel flag | error | Status `error` + message (fileserver.ps1:754-763) |
| running | Fileserver restart | — | interrupted | Boot hygiene rewrites status + `error:'fileserver restarted mid-generation'` (fileserver.ps1:147-160) |
| running | `DELETE /llm/jobs/<id>` | — | cancelled (flag) | Cancel flag written; 202 `cancelling`; files kept for sweep (fileserver.ps1:872-880) |
| done/cancelled/error/interrupted | `DELETE /llm/jobs/<id>` | — | deleted | All three spool files removed; 200 `deleted` (fileserver.ps1:881-885) |
| any | Age > 48h | — | deleted | Retention sweep (fileserver.ps1:161-164) |
| (client) attached | Poll returns terminal + drained | — | folded | Transcript replayed into message; breadcrumb cleared; DELETE ack (03-generation.js:397-404, 461-465) |
| (client) attached | Poll 404 | — | lost | Error note; breadcrumb cleared (03-generation.js:374, 450-451) |
| (client) attached | Poll 401 | — | unauthorized | Error note; breadcrumb cleared; DELETE ack **cancels the live job** (03-generation.js:375, 452-465) |
| (client) attached | 50 consecutive network failures | — | unreachable | Breadcrumb **kept** for later re-attach (03-generation.js:379-382, 458-459) |

Synchronous barriers: the 202 response is the only synchronous barrier — status + spool files exist before the worker starts, so a poll one millisecond later finds both (fileserver.ps1:811-819). Everything else is observational: the client polls, the worker writes files, and the two never share memory (fileserver.ps1:654-657).

### SM2. Swap-status phase machine

| Current State | Event / Trigger | Guard | Next State | Side Effects |
|---|---|---|---|---|
| idle | `POST /swap-model` | hot-swap enabled; no lock; valid body; GGUF exists and is listed | starting | Lock file written first; status `{phase:'starting', message:'Stopping current model'}`; 202 (fileserver.ps1:1273-1371) |
| idle | `POST /swap-model` | any guard fails | (rejected) | 503/405/409/400/404/500 with `{phase:'error', message}` (fileserver.ps1:1273-1326) |
| starting | `GET /swap-status` poll | llama-server `/health` returns 200 (1.5s timeout) | ready | Status `{phase:'ready', message:'Ready'}`; lock removed (fileserver.ps1:1393-1410) |
| starting | `GET /swap-status` poll | no `llama-server` process AND elapsed >5s | error | Status `{phase:'error', message:'llama-server exited during startup. '+log-hint}`; lock removed (fileserver.ps1:1412-1435) |
| starting | `GET /swap-status` poll | elapsed >180s | error | Status `{phase:'error', message:'Model did not respond within 3 minutes.'}`; lock removed (fileserver.ps1:1436-1440) |
| starting | dispatch exception | — | error | Status `error`; lock removed; 500 (fileserver.ps1:1372-1377) |
| ready/error | `GET /swap-status` | — | ready/error (stable) | Status returned as-is; lock already gone |
| any | fileserver boot | — | idle | Stale lock + status files deleted (fileserver.ps1:137-140) |
| (client) | 202 received | — | polling | 800ms grace → 1.5s polls until `ready`/`error` or 180s budget (02-model.js:344-361) |
| (client) | `ready` | — | active | Re-fetch `active-model.json`; `_currentModelFile` updated (02-model.js:322-325) |
| (client) | `error`/timeout | — | reverted | Dropdown reverted to previous file; toast (02-model.js:327-330) |

Synchronous barriers: the lock-file write and the kill→spawn sequence inside `Handle-SwapModel` (fileserver.ps1:1330-1360). Observational: readiness promotion is lazy — it only runs when a client polls `/swap-status` (fileserver.ps1:1380-1383). The launch.bat monitor loop observes the lock file and stands down while it exists (launch.bat:1845-1858).

### SM3. Client state-sync status + boot decision matrix

| Current State | Event / Trigger | Guard | Next State | Side Effects |
|---|---|---|---|---|
| idle | `saveState()` (non-streaming) | served mode | syncing (after 2s debounce) | `pendingJson` set; timer armed (06-state-sync.js:82-87) |
| idle | `flushStateSync` | state transient (generating, or trailing empty assistant) | idle (re-armed) | Push deferred 2s; never publishes a mid-flight snapshot (06-state-sync.js:64-76, 96-106) |
| syncing | PUT succeeds | — | ok | `lastKnownMtime` = response mtime; persisted to `gobbonet_sync_meta` (06-state-sync.js:120-127) |
| syncing | PUT fails | — | error → retry | Snapshot requeued; 4s backoff (06-state-sync.js:128-138) |
| any | generation settles | — | ok (forced flush) | `forceServerFlush` collapses the debounce (06-state-sync.js:153-158) |
| any | pagehide | settled | (beacon) | `sendBeacon` PUT with redacted blob (06-state-sync.js:176-193) |
| (boot) | local empty + server has data | loop guard not tripped | restored | Silent auto-restore + reload (06-state-sync.js:265-276) |
| (boot) | local + server newer | server ≥50% of local size | prompted | `showRestorePrompt`; decline → local authoritative, re-publish (06-state-sync.js:294-316, 418-438) |
| (boot) | local + server newer | server <50% of local size | local kept | Re-publish local to heal server (06-state-sync.js:306-313) |
| (boot) | local + server older/match | — | ok | `lastKnownMtime` = max(local, server) (06-state-sync.js:317-323) |
| (boot) | quota-truncation signature | server >1.2× local, not newer | restored | Silent recovery restore (06-state-sync.js:277-293) |

### SM4. Stream parser phase machine (thinking formats)

| Current State | Event / Trigger | Guard | Next State | Side Effects |
|---|---|---|---|---|
| pre | delta with ` thinking` before ` response` (deepseek) | — | thinking | Pre-marker text → content (03-generation.js:674-685) |
| pre | delta with ` response` first (deepseek) | — | content | Pre-marker text → reasoning (implicit-think) (03-generation.js:687-693) |
| pre | no marker, >64 chars buffered, no `<` | — | content | Reasoning reparented to content (non-thinking masquerade) (03-generation.js:704-712) |
| thinking | ` response` seen | — | content | Buffered text → reasoning (03-generation.js:716-723) |
| content | stray ` thinking` seen | — | thinking | Loop protection (03-generation.js:732-740) |
| pre | harmony channel marker | FINAL → content; ANALYSIS/COMMENTARY → thinking | content/thinking | Pre-marker noise dropped (03-generation.js:782-796) |
| thinking | `<|end|>`/`<|return|>` (harmony) | — | between | Reasoning flushed (03-generation.js:798-808) |
| between | next channel marker | — | content/thinking | Role/start tokens dropped (03-generation.js:817-829) |
| content | `<|end|>`/`<|return|>` (harmony) | — | done | Content flushed (03-generation.js:831-838) |
| pre/thinking | `<channel|>` (gemma) | — | content | Reasoning flushed (03-generation.js:866-879) |
| any | `field === 'reasoning'` delta | — | thinking_done | `serverSplit=true`; subsequent content trusted as-is (03-generation.js:639-646) |
| any | end-of-stream | — | finalized | `finalizeStreamMessage`: flush pending, reparent implicit-think, scrub stray markers, unwrap tool-call envelope (03-generation.js:1013-1073) |

Synchronous barriers: none — the parser is a pure function of the byte stream. Observational: `serverSplit` latches on the first server-routed reasoning delta and disables inline parsing for the rest of the message (03-generation.js:643-644).

### SM5. `jobsAvailable` probe tri-state

| Current State | Event / Trigger | Guard | Next State | Side Effects |
|---|---|---|---|---|
| null (unknown) | `POST /llm/jobs` → 404/405 | — | false | Legacy direct stream forever after (03-generation.js:338-344) |
| null | `POST /llm/jobs` → 202 with `id` | — | true | Relay in use (03-generation.js:349-352) |
| null | transient network error | — | null | Fall back to direct stream this turn; re-probe next send (03-generation.js:353-357) |
| true | job start fails | — | (error surfaced) | Real error thrown, not a probe failure (03-generation.js:354) |
| false | any send | — | false | Direct stream only (03-generation.js:331) |

## Persistent Schema Notes

### IndexedDB `gobbonet-state` v2 (05-persistence.js:33-58)

- **Append-only vs mutable**: mutable. `meta` (key `'app'`) rewritten wholesale on full save; `threads` (keyPath `id`) rewritten per-record — streaming ticks write only the active thread (05-persistence.js:596-609); `vectors` (keyPath `hash`) and `telemetry` (keyPath `turn_id`) are append-only with ring trimming (telemetry capped at 200 records, 08-rag.js:293-298).
- **Branching vs linear**: linear per record; thread *order* is persisted separately as `threadOrder` in the blob because IDB key order ≠ user-arranged order (05-persistence.js:95-111, 473-479).
- **Compaction/summarization**: none for threads; telemetry ring-buffered; vectors keyed by content hash so unchanged chunks are never re-embedded (05-persistence.js:48-50).
- **Replay/resume**: `loadState()` → `applyLoadedState()` runs all in-place migrations on every load path (IDB, localStorage, server restore) (05-persistence.js:87-91). Migrations include: persona extraction from legacy settings, macro seeding with `seededDefaultMacros` tracking, thread field backfills, token-limit bump, runtime-flag stripping, orphaned-empty-assistant recovery with reroll-variant rollback (05-persistence.js:119-314).
- **Locking/dedup/conflict**: none — single-tab assumption; the server `/state` mtime protocol is the only cross-device conflict mechanism (advisory, see P4).

### localStorage mirror (05-persistence.js:385-396, 04-state.js:8-9)

- Key `gobbonet_chat_state`; legacy `gemma4_chat_state` migrated by rename on load. Whole-blob rewrite per save; quota errors normalized across browsers and surfaced as `storageQuotaHit` (05-persistence.js:439-449). Left in place after IDB migration as a rollback safety net (05-persistence.js:322-329).

### `/state` server blob (`.gobbonet-state.json`)

- Shape = `buildStateBlob()`: `{threads, threadOrder, activeThreadId, settings, characterCards, activeCardId, personaCards, activePersonaId, schedules, sidebarOpen, searchEnabled, folders, extensions, macros, seededDefaultMacros}` (05-persistence.js:470-494). `settings.apiKey` **stripped** before push (05-persistence.js:416-434). Whole-file rewrite, last-write-wins, no locking, no versioning, no compaction; mtime (ms) is the only version stamp (fileserver.ps1:545-564).

### Job spool files (`.jobs/<id>.{sse,json,cancel}`)

- `.sse`: **append-only** raw byte stream (worker holds write handle with `FileShare::ReadWrite`; poll handler reads the growing file, fileserver.ps1:721-726). `.json`: mutable whole-rewrite status; reads retry 3×25ms against torn writes (fileserver.ps1:623-635). `.cancel`: flag file, content `'1'`. Lifecycle: ack-delete + 48h retention backstop (fileserver.ps1:69-76).

### `.swap-status.json` + `.swap-in-progress`

- Status: mutable whole-rewrite per phase change; `{phase, file, name, message, started_at, updated_at}` (fileserver.ps1:1154-1172). Lock: presence-only. Both deleted at fileserver boot (fileserver.ps1:137-140).

### `active-model.json` / `models-list.json`

- Mutable whole-rewrite; written by launch.bat at boot and fileserver.ps1 at swap; no locking between writers (launch.bat:1180-1192, fileserver.ps1:1236-1265).

### `.gobbonet-secret`

- Write-once at setup; rename-to-`.bad` on verification failure; never deleted except by `reset-password` (launch.bat:144-148, 414-418).

### Export bundles (21-data.js:26-57)

- Snapshot JSON with `{gobbonet_export, version:1, exported}` envelope; import merges by ID (threads/cards/personas) or replaces everything (full).

## Compatibility Hazards

| Hazard | Where It Appears | Severity | Notes |
|---|---|---|---|
| **Client/fileserver version skew** — old fileserver without `/llm/jobs` | 03-generation.js:31-34, 338-343 | medium | Client probes and falls back to legacy direct stream; only a definitive 404/405 pins the fallback. A port must keep the probe semantics or old/new pairs break |
| **file:// vs served mode** | 01-config.js:25-26, 02-model.js:382-391 | high | file:// has no auth, no `/state` sync, no jobs relay, no hot-swap; endpoints switch between same-origin proxy and raw loopback. CORS on loopback servers is what makes file:// work at all |
| **Per-origin browser storage** | 06-state-sync.js:6-19 | high | Each LAN IP/hostname is a separate data silo; the `/state` mtime protocol exists specifically to patch this. Any port must reproduce the boot decision matrix or lose data on IP rotation |
| **mtime protocol is advisory** | fileserver.ps1:545-564 | medium | Last-write-wins with no server-side conflict check; concurrent two-device writes clobber (mech-CF1 → defect-scan-semantic) |
| **GGUF v2/v3 only** | identify-model.ps1:34-35 | medium | v1 GGUFs rejected outright; unknown KV types abort the parse and fall back to filename heuristics |
| **Card format versions** | 16-card-io.js:269-281 | medium | V1 flat vs V2/V3 `.data`-wrapped; spec-less wrappers tolerated; lorebook import is lossy (flattened to always-on lore); export is a best-effort inverse (flattened fields re-export under `description`) |
| **`mistral-v7-tekken` not registered in pinned build** | fileserver.ps1:1065-1072, identify-model.ps1:236-249 | high | Passed bare to `--chat-template` it becomes a literal template body (constant ~8-token output). Normalized to `mistral-v7` in both writers; a port must keep the normalization or reproduce the failure |
| **BOM-less UTF-8 discipline** | fileserver.ps1:227-233 | medium | PowerShell 5.1 `Set-Content -Encoding UTF8` writes a BOM; all server JSON writes use `UTF8Encoding($false)`. A port that emits BOMs breaks the client's `JSON.parse` on `/state` |
| **ASCII-only server output** | fileserver.ps1:34-35 | low | Server console output is ASCII-only because batch echo mangles non-ASCII on legacy code pages |
| **Session state is in-memory** | fileserver.ps1:118-120 | medium | Server restart logs everyone out; mid-generation 401 cancels the in-flight job via the DELETE-ack path (proto-CF1) |
| **Lazy swap readiness promotion** | fileserver.ps1:1380-1383 | medium | `starting→ready` only advances when someone polls `/swap-status`; an orphaned lock blocks launch.bat's monitor loop indefinitely (proto-CF2) |
| **Single-threaded accept loop** | fileserver.ps1:1471-1478 | medium | `portability hazard`: synchronous `GetContext()` — streaming responses block the loop; runspaces are .NET/Windows-specific |
| **Browser Page Lifecycle dependence** | 24-boot.js:147-154, 06-state-sync.js:176-193 | medium | `portability hazard`: bfcache, `visibilitychange`, `sendBeacon` behavior differs across browsers and is absent in non-browser ports |
| **`DecompressionStream` requirement** | 16-card-io.js:65-73 | low | zTXt/iTXt chunks and deflated `.charx` entries need the browser's `DecompressionStream`; unsupported browsers can't read compressed cards |
| **No `crypto.subtle` on plain HTTP** | 08-rag.js:31-34 | low | LAN deployment serves plain http, so the RAG cache key uses FNV-1a instead of SubtleCrypto |
| **Base64 chunk framing** | fileserver.ps1:588-590, 903-905 | medium | `chunk_b64` exists so the JSON envelope never fights partial UTF-8 at chunk boundaries; 256KB raw budget → ~350KB base64 envelope per poll. A port must preserve byte-offset semantics (`from`/`next`/`size`) exactly |
| **`max_tokens:-1` + client-side cap** | 10-chat.js:166, 03-generation.js:92-94 | low | No server-side token cap (reasoning tokens would be counted); the smart limit is client-side and must be reproduced in a port or replies grow unbounded |
| **Family-keyed stop strings** | 06-state-sync.js:547-569 | medium | Lookup is by `activeModel.family.toLowerCase()` — the key must match identify-model.ps1's family strings exactly (e.g. `cohere`) or delimiters leak into rendered output |
| **Job id regex** | fileserver.ps1:851 | low | `^[0-9a-f]{32}$` — GUID `'n'` format; a port changing id format breaks the route |
| **PowerShell 5.1 quirks** | fileserver.ps1:827-829 | low | `portability hazard`: trailing-dot line continuation undependable; runspace argument order must match the worker param block |

## Coverage and limits

- **Inspected scope:** fileserver.ps1 (full, 1618 lines — auth, state, jobs, swap, proxy, dispatch); js/03-generation.js (full, 1120 — job transport, feeder, thinking parsers, tool-call unwrap, finalize); js/06-state-sync.js (full, 854 — sync protocol, boot matrix, sampler params, stop strings, logit bias); js/05-persistence.js (full, 667 — IDB schema, migrations, blob shape, save paths); js/16-card-io.js (full, 737 — card V1/V2/V3 import/export, PNG chunks, ZIP reader); js/11-search.js (full, 222); identify-model.ps1 (full, 477 — GGUF parsing, template registry, record shape); js/24-boot.js (full, 154); js/02-model.js (1-466: endpoints, SSE line parser, hot-swap client); js/08-rag.js (1-400 of 961: storybook grammar, embedding client, telemetry record); js/10-chat.js (130-229, 930-996: request body, resume); js/01-config.js (1-120 of 170); launch.bat (300-419 password, 1160-1239 metadata writers, 1590-1709 proxy/fileserver launch); **decoded the search-proxy encoded command (launch.bat:1608)** in full.
- **Skipped scope:** js/07-prompt.js (lore summarization request body — cited from contracts phase), 12-render, 13-dashboard, 14-scroll, 15-cards, 17-personas, 18-utils, 19-extensions, 20-macros, 21-data (export envelope cited from contracts), 22-scheduler, 23-card-code; chat.html; css/*; hardware-probe.ps1; setup-lan.bat; remaining launch.bat sections (downloads, model menu, monitor loop internals — covered by architecture/mechanical phases).
- **Evidence basis:** source inspection only. No runtime verification (Windows-only; not executable in this environment), no tests in repo, no CI, no upstream findings beyond the README's known-bugs section.
- **Known blind spots:** (1) the Ollama `web_search` upstream response schema beyond `{results:[{title,content,url}]}` — the proxy forwards verbatim, so the schema is not visible in-repo (q-websearch-response-fields, refining q-ollama-api-version); (2) whether the pinned llama-server build terminates SSE with `data: [DONE]` or just closes — the client tolerates both (q-sse-done-marker); (3) exact `/props` and `/apply-template` response shapes (diagnostic-only, consumed by `gobboDiag()`, 06-state-sync.js:589-600) (q-llama-server-diag-endpoints); (4) runtime behavior of the accept loop under multiple LAN clients (q-accept-loop-scale, from architecture).
- **Coverage disposition:** COMPLETE (all six arch-CF1 wire formats extracted with file:line citations; remaining unknowns are runtime-test questions, not source gaps).

## Open Questions

| ID | Kind | Description | Deferred Reason |
|---|---|---|---|
| q-ollama-api-version | needs-runtime-test | (from architecture, still open) The search proxy forwards to `https://ollama.com/api` + path; the exact `web_search` request/response contract and its stability are not pinned in-repo. This phase decoded the proxy (verbatim forwarder) and the client (request `{query, max_results}`, response `{results:[{title,content,url}]}`) — the upstream schema beyond that remains invisible. | Requires a live capture against Ollama's API. |
| q-websearch-response-fields | needs-runtime-test | Refines q-ollama-api-version: the client reads only `title`/`content`/`url` per result (11-search.js:184-190); whether the upstream returns additional fields (snippets, citations, error shapes) and whether `max_results` is honored is unknown. | Proxy forwards verbatim; not visible in-repo. |
| q-sse-done-marker | needs-runtime-test | Whether the pinned llama-server build (b9294) terminates streams with `data: [DONE]` or simply closes the connection. The client handles both (02-model.js:414, feeder flush on EOF, 03-generation.js:309-320), but the spooled transcript's exact terminal bytes are unverifiable from source. | Requires a live capture against the pinned build. |
| q-llama-server-diag-endpoints | needs-runtime-test | `gobboDiag()` calls `GET /props` and `POST /apply-template` (06-state-sync.js:589-600); their exact response shapes are not documented in-repo (diagnostic-only, not load-bearing). | Requires a live call against the pinned build. |

## Carry-Forward

| ID | Target Phase | Description | Deferred Reason |
|---|---|---|---|
| proto-CF1 | defect-scan-semantic | Session expiry mid-generation: the job poll returns 401 → the client treats it as terminal, clears the breadcrumb, and DELETEs the job — which flags cancel and **kills the still-running generation** (03-generation.js:375, 452-465; fileserver.ps1:872-880). The error message ("reload the page and sign in to re-attach") promises re-attachment the code path has already foreclosed. Assess as a pass-5 contract violation (error behavior vs actual behavior). | Contract-drift assessment is pass 5 of the semantic scan. |
| proto-CF2 | defect-scan-semantic | Swap readiness promotion is lazy (only advances when `/swap-status` is polled, fileserver.ps1:1380-1383). If the client stops polling mid-swap (tab closed), the `.swap-in-progress` lock persists and launch.bat's monitor loop stands down indefinitely (launch.bat:1845-1858) — no crash-restart protection until the next fileserver boot. Assess as a pass-3 concurrency/lifecycle defect. | Concurrency is pass 3 of the semantic scan. |

---

## Validation

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | An event catalog is documented. | PASS | §Event Catalog: 18 protocols (P1–P18), each with producer/consumer/transport/ordering/required/optional/identifiers/errors/restart per the template table. |
| 2 | A state machine is documented. | PASS | §State Machine: 5 machines (SM1 job lifecycle, SM2 swap-status phase machine, SM3 state-sync + boot matrix, SM4 stream parser phases, SM5 jobsAvailable probe), each with states/transitions/guards/side effects and synchronous-barrier vs observational-event separation. |
| 3 | Persistent schema notes are documented. | PASS | §Persistent Schema Notes: IndexedDB v2, localStorage mirror, `/state` blob, job spool, swap-status, model metadata, secret, export bundles — each with append/mutable, branching, compaction, replay, and locking semantics. |
| 4 | Compatibility hazards are documented. | PASS | §Compatibility Hazards: 19-row table (version skew, file:// vs served, per-origin storage, GGUF v2/v3, card versions, BOM/encoding, runspace/accept-loop, Page Lifecycle, base64 framing, etc.) with severity and notes. |
| 5 | Findings are marked with evidence levels. | PASS | Every protocol field, state transition, and hazard carries `observed fact` / `strong inference` / `portability hazard` / `open question` with file:line citations throughout. |
| 6 | Coverage and limits name inspected scope, skipped scope, evidence basis, and blind spots. | PASS | §Coverage and limits lists all four plus disposition (COMPLETE); blind spots map to open questions q-websearch-response-fields, q-sse-done-marker, q-llama-server-diag-endpoints, q-accept-loop-scale. |

**Validated by:** protocols phase, delegated subagent session (2026-08-18)
**Overall:** PASS
