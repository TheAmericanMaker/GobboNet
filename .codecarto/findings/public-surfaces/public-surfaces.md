# Public Surfaces Findings

Store binary commands, exports, external APIs, user-facing screens, and integration surfaces here.

---

## 2026-08-18 — architecture phase (delegated subagent)

### 1. Binaries and CLI commands

| Surface | Invocation | Notes |
|---|---|---|
| `launch.bat` | `launch.bat` or `launch.bat reset-password` | The only user-facing command. `reset-password` deletes `.gobbonet-secret` and forces re-setup (launch.bat:144-148). Keep-open guard relaunches itself under `cmd /k` (launch.bat:11-15). |
| `setup-lan.bat` | run once as Administrator | Adds/repairs three `netsh advfirewall` rules (Gemma4-LLM :11434, Gemma4-Search :11435, Gemma4-Web :8080, all `remoteip=LocalSubnet`) and enables mDNS UDP 5353 on Private+Public profiles (setup-lan.bat:47-100). |
| `hardware-probe.ps1` | `-OutputPath <path> -ModelsDir <dir>` (invoked by launch.bat) | Writes `hardware.json` (schema 2). Exit 0 = usable file written (cpu_only is success), 1 = could not write anywhere (hardware-probe.ps1:129-132). |
| `identify-model.ps1` | `-GgufPath <p> -Emit json\|batch -ModelsDir <d> -Active <f> -OutFile <f>` | GGUF v2/v3 metadata reader; emits `set` statements for batch consumption or JSON (identify-model.ps1:7-14). |
| `fileserver.ps1` | spawned hidden by launch.bat with `GEMMA_*` env | Not user-facing; refuses to start without a valid `GEMMA_ACCESS_SECRET` (fileserver.ps1:103-107). |

### 2. HTTP surfaces (fileserver.ps1, `http://+:8080/`)

Auth model: everything except `/login`, `/logout`, `OPTIONS`, `/favicon.ico` requires a valid session cookie (fileserver.ps1:1492-1561). Login POSTs `password=` form-encoded; success sets `gobbonet_session` (HttpOnly, SameSite=Lax, 12h Max-Age) and 302s to `/` (fileserver.ps1:1512-1523). Non-HTML clients get JSON 401 `{error:'authentication required', login:'/login'}` (fileserver.ps1:1552-1560).

| Route | Method | Behavior |
|---|---|---|
| `/` | GET | Serves chat.html (Resolve-StaticPath default, fileserver.ps1:365). |
| `/login` | GET/POST | Login page / credential check (fileserver.ps1:1497-1531). |
| `/logout` | GET | Destroys session, clears cookie, 302 → /login (fileserver.ps1:1532-1538). |
| `/favicon.ico` | GET | Unauthenticated; 404 if absent (fileserver.ps1:1539-1551). |
| `/health-fileserver` | GET | `{status:'ok', pid, hotswap}` (fileserver.ps1:1566-1568). |
| `/state`, `/state/*` | GET/POST/PUT | Server-side state backup. `GET /state/info` → `{mtime,size}` + `X-State-Mtime` header; `GET /state` → full body; POST/PUT validates JSON then writes `.gobbonet-state.json` (fileserver.ps1:501-567). |
| `/swap-model` | POST | Body `{"file":"<name>.gguf"}`; 202 on dispatch, 409 if swap in flight, 400 invalid filename (no separators/`..`, must end `.gguf`), 404 unknown GGUF or not in models-list.json, 503 if hot-swap not configured (fileserver.ps1:1270-1378). |
| `/swap-status` | GET | `{phase: idle\|starting\|ready\|error, file, name, message, started_at}`; promotes starting→ready on llama-server `/health`, errors on process death >5s or 180s timeout (fileserver.ps1:1384-1445). |
| `/llm/jobs`, `/llm/jobs/*` | POST/GET | Detached generation relay. POST body = exact llama-server chat/completions request → `{id}` immediately; GET `/llm/jobs/<id>?from=N[&max=M]` → `{status,size,next,chunk_b64,error}`; DELETE acks and removes spool; cancel via `.jobs/<id>.cancel` flag (fileserver.ps1:569-613, 768-791). Max 4 concurrent jobs → 429 (fileserver.ps1:789-791). |
| `/llm/*` | any | Reverse proxy → `127.0.0.1:11434` (llama-server), streaming, no pre-buffer (fileserver.ps1:1584-1586, 389-392). |
| `/search/*` | any | Reverse proxy → `127.0.0.1:11435` (search proxy) (fileserver.ps1:1587-1589). |
| `/embed/*` | any | Reverse proxy → `127.0.0.1:11436` (embed server); 502 if down, client degrades to tag-only RAG (fileserver.ps1:1590-1596). |
| anything else | GET | Static file from project root; traversal and dotfile paths refused (fileserver.ps1:1597-1608, 363-385). |

### 3. Upstream APIs consumed by the frontend

| Endpoint | Used by | Notes |
|---|---|---|
| `LLAMA_URL + /v1/chat/completions` (POST, SSE) | 03-generation.js:473 (legacy direct stream), 03-generation.js:1087 (lore summarization) | OpenAI-compatible; `LLAMA_URL` = origin+`/llm` when served, `http://127.0.0.1:11434` on file:// (01-config.js:25-26). |
| `LLAMA_URL + /health` | 11-search.js:199 | `{status:'ok'}` when model loaded. |
| `EMBED_URL + /v1/embeddings` (POST `{input, model:'embed'}`) | 08-rag.js:189-193 | `EMBED_URL` = origin+`/embed` or `http://127.0.0.1:11436` (02-model.js:391). |
| `SEARCH_PROXY_URL + /health`, `/web_search` (POST `{query, max_results:5}`, `Authorization: Bearer *** | 11-search.js:30,45-52 | `SEARCH_PROXY_URL` = origin+`/search` or `http://127.0.0.1:11435` (02-model.js:382). |
| `https://ollama.com/api` + path | search proxy (encoded in launch.bat:1608) | Proxy forwards method/body/Authorization verbatim; CORS `*` on responses. |

### 4. File formats and persistent artifacts

- **GGUF v2/v3** metadata: magic `GGUF`, version 2-3, KV pairs; reads `tokenizer.chat_template`, `general.architecture`, `*.context_length` (identify-model.ps1:18-61).
- **Character cards**: `.json` (V1 flat / V2-V3 under `.data`), `.png` (tEXt/zTXt/iTXt chunk keyed `ccv3` or `chara`, base64 UTF-8), `.charx` (ZIP with card.json + assets) (16-card-io.js:1-15).
- **`default-characters.json`**: array of card objects (icon/name/desc/writingStyle/personality/startingLore/colors/sampler fields) (default-characters.json:1-68).
- **`active-model.json`**: written by launch.bat (`{id, name, family, ggufFile, maxCtx, thinkingFormat}` shape, launch.bat:1182-1192); read by 02-model.js.
- **`models-list.json`**: written by identify-model.ps1; hot-swap dropdown source; `active` flag updated on swap (fileserver.ps1:1251-1264).
- **`hardware.json`**: schema 2 — gpu/ram/disk/cpu objects, `recommended_tier`, `usable_budget_gb`, `budget_source` (hardware-probe.ps1:82-127).
- **`.gobbonet-secret`**: one line `<hex-salt>:<hex-sha256>`, ASCII, no trailing newline (launch.bat:355, 433).
- **`.gobbonet-state.json`**: full client state blob (server-side backup).
- **`.swap-status.json`**: `{phase, file, name, message, started_at}`.
- **`.jobs/<id>.{sse,json,cancel}`**: raw SSE spool, status JSON, cancel flag; 48h retention backstop (fileserver.ps1:69-76).
- **Export/import bundles**: JSON downloads for threads/cards/personas/full backup; import merges by ID, full backup replaces (21-data.js:1-8, chat.html:775).

### 5. User-facing screens and workflows

- **Login page** (self-contained HTML, fileserver.ps1:318-358).
- **Chat screen**: sidebar (thread list, search, folders/tags/pins), chat header (model selector, status dot, lore chip, privacy badge), messages area, input area (attach, search toggle, send/stop), follow-to-bottom button, drag-drop overlay (chat.html:26-121).
- **Landing dashboard** (13-dashboard.js): connection pill, scheduled tasks, active cards.
- **Modals**: settings (chat.html:126), characters (225), scheduler (611), extensions (661), data manager (753), lore inspector (819), about (835).
- **Workflows**: first-run password setup; model download menu with hardware recommendation; hot-swap via header dropdown; character card import/export; data export/import/purge; scheduled prompts; web search toggle.

### 6. Integration surfaces (external)

- **llama.cpp** (pinned release `b9294`, Vulkan Windows x64 build) — the inference engine; API contract is OpenAI-compatible.
- **HuggingFace** (bartowski GGUF repos + nomic-embed-text) — one-time model downloads with SHA-256 verification.
- **Ollama** (`ollama.com/api`) — opt-in web search; requires user API key stored in browser settings.
- **Windows OS**: netsh firewall, mDNS/dnscache, System32 tools (curl, certutil, tar), tasklist/taskkill, WMI/registry/dxdiag/nvidia-smi for hardware probing.

---

## 2026-08-18 — contracts phase (delegated subagent)

Contract-level additions to the public-surface inventory (behavioral view; wire formats remain protocols-phase territory, arch-CF1).

### 1. User-visible behaviors per surface (contracts phase)

- **Web UI** owns 24 feature contracts (send/stream, stop, reroll, edit, delete/copy, threads, folders/tags/pins, branching, greetings, lore compression, token counter, CoT view, CoT watchdog, smart limit, banned words, system-prompt carousel, sampler presets, built-in/custom macros, auto-continue, characters, card import/export, RAG lorebook, card code, personas, hot-swap, web search, attachments, file save, data export/import/purge, extensions, scheduler, dashboard, connection status, state sync, job resume, avatar/colors). Full tables in findings/contracts/behavioral-contracts.md §Feature Contracts.
- **CLI/launcher** owns 6 contracts: first-run setup, password reset, model download menu, monitor loop, LAN setup/phone URL, shutdown.
- **HTTP API** owns 6 contracts: login/logout/session, /state(+info), /llm/jobs, /swap-model(+status), reverse proxies, static serving.
- **Storage/export formats** owns 4 contracts: export bundles, import semantics, character-card carriers, state blob + redaction.

### 2. Contract-relevant route details not in the architecture inventory

- `POST /llm/jobs` accepts an optional `?thread=<id>` query param recorded in the job status file (fileserver.ps1:802-806).
- `GET /llm/jobs/<id>?from=N&max=M`: `max` is clamped to 262144 bytes; `max=0` is a status-only peek; `from > size` clamps to size (fileserver.ps1:900-925).
- `DELETE /llm/jobs/<id>` on a still-running job returns 202 and flags cancel instead of deleting (fileserver.ps1:872-880).
- `GET /state` and `GET /state/info` both set `X-State-Mtime` (ms epoch) (fileserver.ps1:522, 538).
- `POST /login` has **no rate limiting or lockout** (observed absence, fileserver.ps1:1497-1531) — routed to defect-scan-semantic as contracts-CF3.
- Static serving has no size cap and no extension allowlist (mechanical P2-1; mech-CF2b) — contract-level confirmation.

### 3. Upstream API contract notes (client-side shapes)

- Chat request body: `{model:'local', messages, stream:true, max_tokens:-1, temperature, min_p, top_k, top_p, repeat_penalty, repeat_last_n, xtc_probability, xtc_threshold, dry_multiplier, dry_base, dry_allowed_length, dry_penalty_last_n, stop?, logit_bias?}` (10-chat.js:166, 06-state-sync.js:502-524, 576-580).
- `logit_bias` shape: map of token-id **strings** → strength (06-state-sync.js:774) — the shape-mismatch hypothesis for the README-declared broken feature is routed to defect-scan-semantic (mech-CF3).
- Embed request: `{input: '<prefix>'+text, model:'embed'}` with `search_document:`/`search_query:` prefixes (08-rag.js:180-193).
- Search request: `{query, max_results:5}` + `Authorization: Bearer *** (11-search.js:45-52).
- Lore summarization request: `{model:'local', messages:[system,user], stream:true, max_tokens:700, temperature:0.3}` (07-prompt.js:364-391).


---

## 2026-08-18 — protocols phase (delegated subagent)

Wire-format detail extracted for the surfaces cataloged above (closes arch-CF1). Full protocol tables in `findings/protocols/protocols-and-state.md`.

### `/llm/jobs` relay (fileserver.ps1:569-967)

- `POST /llm/jobs` — body = byte-exact llama-server chat request; optional `?thread=<id>` (informational only). 202 `{id, status:'running'}`; 429 at ≥4 live workers; 400 non-JSON body. Job id = GUID `'n'` (32 hex), route regex `^/llm/jobs/([0-9a-f]{32})(/cancel)?$` (fileserver.ps1:808, 851).
- `GET /llm/jobs/<id>?from=N[&max=M]` → `{id, status, size, next}` + `chunk_b64` (base64 of raw spool bytes from `from`; omitted when none). `max` clamped 0–262144 (256KB raw → ~350KB base64 envelope); `max=0` = status-only peek. `from > size` clamps to size (fileserver.ps1:900-962).
- `POST /llm/jobs/<id>/cancel` → flag file `'1'`; worker notices within ~250ms (ReadAsync + 250ms waits), aborts upstream, status `cancelled` (fileserver.ps1:730-752, 861-869).
- `DELETE /llm/jobs/<id>` → ack: live job gets cancel-flag + 202 `cancelling`; terminal job's three files removed, 200 `deleted` (fileserver.ps1:872-886).
- Terminal statuses: `done | cancelled | error | interrupted` (fileserver.ps1:600). Fileserver restart flips `running` → `interrupted` + `error:'fileserver restarted mid-generation'` (fileserver.ps1:147-160). 48h retention backstop (fileserver.ps1:74, 161-164).
- Spool: `.jobs/<id>.sse` append-only raw bytes (writer `FileShare::ReadWrite`), `.json` whole-rewrite status (reads retry 3×25ms), `.cancel` flag (fileserver.ps1:614-635, 721-726).

### `/state` schema + mtime protocol (fileserver.ps1:501-567)

- `GET /state/info` → `{mtime, size}` + `X-State-Mtime` header; 404 `{error:'no state on server'}`. `GET /state` → full body + header. `POST/PUT` → JSON-validated → 200 `{status:'ok', mtime}`; 400/500 on bad JSON/write failure. `mtime` = `LastWriteTimeUtc` in **milliseconds** (fileserver.ps1:521, 537, 559).
- Blob shape = `buildStateBlob()` (05-persistence.js:470-494); `settings.apiKey` stripped before push (05-persistence.js:416-434). Last-write-wins, no locking (mech-CF1 → defect-scan-semantic).

### Swap protocol (fileserver.ps1:1270-1445)

- `POST /swap-model` `{file:"<name>.gguf"}` → 202 `{phase:'starting', file, name, message, started_at}`; guards: 503 not configured, 409 in-flight (lock file), 400 invalid JSON/filename (no separators, no `..`, `.gguf` suffix), 404 GGUF missing/not listed.
- `GET /swap-status` → `{phase, file, name, message, started_at, updated_at}`; `{phase:'idle'}` when no status file. Promotion `starting→ready` on llama-server `/health` 200 (1.5s timeout); `→error` on process death >5s (with log-tail hint) or 180s timeout. Promotion is lazy — only advances when polled (fileserver.ps1:1380-1383).

### Auth/session (fileserver.ps1:78-127, 259-316, 1497-1561)

- `POST /login` form-encoded `password=`; constant-time `SHA256(salt+typed)` vs stored; success → `Set-Cookie: gobbonet_session=<tok>; Path=/; HttpOnly; SameSite=Lax; Max-Age=43200` + 302 `/`. Token = 32 random bytes base64url; bound to `SHA256(ip+'|'+User-Agent)`; 12h TTL; in-memory table (restart logs everyone out). `X-Gobbonet-Token` header fallback for curl.

### GGUF metadata consumed (identify-model.ps1:18-81)

- Magic `GGUF`, version 2–3 only. Keys: `tokenizer.chat_template`, `general.architecture`, `*.context_length` (uint32/uint64). Template identity = SHA-256 of trimmed template → `HashDerivations` registry (identify-model.ps1:83-123). Record shape: `{file, id, name, family, thinkingFormat, maxCtx, useJinja, chatTemplate, chatTemplateFile, templateHash}` (identify-model.ps1:181-184).

### Character card V1/V2/V3 (16-card-io.js:1-39, 269-389, 619-687)

- Carriers: `.json` (V1 flat / V2-V3 under `.data`), `.png` (tEXt/zTXt/iTXt `ccv3` preferred, `chara` fallback; base64(UTF-8 JSON)), `.charx` ZIP (`card.json` at root; methods 0/8 only).
- Mapping: `system_prompt+description+scenario+mes_example+post_history_instructions`→writingStyle; `personality`→personality (+woven into writingStyle); `first_mes`→greeting; `alternate_greetings+group_only_greetings`→altGreetings; `character_book`→startingLore (lossy flatten); `extensions.gobbonet.{ragStorybook,customCode}` round-trip (customCode always disabled on import).
- Export: V3 PNG with both `ccv3` + `chara` chunks; flattened fields re-export under `description`; `_import` metadata restored.

### Ollama web_search (decoded launch.bat:1608; 11-search.js:18-87)

- Proxy: HttpListener 127.0.0.1:11435, TLS 1.2, 30s timeout; `/health` → `{"status":"ok"}`; everything else forwarded **verbatim** to `https://ollama.com/api` + path with body + `Authorization` unchanged; upstream failure → 502 `{error:'proxy: <msg>'}`.
- Client: `POST /web_search` `{query, max_results:5}` + `Authorization: Bearer <key>`; response `{results:[{title, content, url}]}`. Upstream schema beyond those three fields: open question q-websearch-response-fields.


## 2026-08-18 — porting phase (delegated subagent)

Porting-oriented view of the public surfaces (synthesis of architecture/contracts/protocols; full bundle in `findings/porting/reverse-engineering-bundle.md`). Concept names per the porting SKILL — the target must not mirror the source layout.

- **Surfaces a port must reproduce (core):** the fileserver HTTP surface on :8080 — auth (`POST /login`, `GET /logout`, session cookie + fingerprint), `/state` + `/state/info` (mtime protocol), `/llm/jobs*` (detached generation relay, base64 chunk framing), `/swap-model` + `/swap-status` (phase machine), the three reverse proxies (`/llm/*`→11434, `/search/*`→11435, `/embed/*`→11436), and static serving (with the traversal/dotfile guards — plus the allowlist/size-cap fixes from defects P2-1/4.4). The browser UI surface (chat screen, dashboard, login page, seven modals) is the product itself.
- **Surfaces a port may reshape:** the CLI surface (`launch.bat [reset-password]`, `setup-lan.bat`) is incidental — the port's own supervisor replaces it; the supervision contract (15s health poll, restart from launch script, stand-down during swap) is what survives. `hardware-probe.ps1`/`identify-model.ps1` are tooling, not user surfaces.
- **Upstream APIs consumed (must stay compatible):** llama-server OpenAI-compatible `/v1/chat/completions` (SSE), `/health`, `/tokenize`, `/v1/embeddings`; Ollama `web_search` via the verbatim-forwarding proxy. The client's SSE parser tolerates both `data: [DONE]` and connection-close termination (q-sse-done-marker).
- **File formats (load-bearing):** GGUF v2/v3 metadata (three consumed keys); character cards V1/V2/V3 in `.json`/`.png` (tEXt `ccv3`/`chara`)/`.charx`; `active-model.json`/`models-list.json`; `.gobbonet-secret` (`salt:hash`); export bundles `{gobbonet_export, version:1, exported}`.
- **Defect-driven surface changes:** login needs rate limiting (4.2, fix before porting); `/state` and `/llm/jobs` need body-size caps (4.3, port differently); static serving needs an extension allowlist (4.4, port differently); the 401-mid-generation path must not cancel the live job (5.1, fix before porting).
