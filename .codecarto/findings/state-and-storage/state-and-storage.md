# State and Storage Findings

Store durable state notes here.

---

## 2026-08-18 — architecture phase (delegated subagent)

### Browser-side state (per-origin)

**IndexedDB `gobbonet-state` (v2)** — the primary store (05-persistence.js:20-54):

| Store | Key | Contents |
|---|---|---|
| `meta` | out-of-line, key `'app'` | Non-thread state: settings, character cards, personas, folders, macros, scalars. Rewritten wholesale on full save. |
| `threads` | keyPath `'id'` | One record per conversation thread — the volume store; per-record writes during streaming. |
| `vectors` | keyPath `'hash'` | RAG document-embedding cache (content-hash keyed); local-only, never synced. |
| `telemetry` | keyPath `'turn_id'` | RAG telemetry records (config snapshot per turn). |

**localStorage** — mirror + legacy migration:
- `gobbonet_chat_state` (current key), `gemma4_chat_state` (legacy; migrated once on load, 05-persistence.js:357-392).
- Extensions (custom CSS/JS) are persisted inside state.extensions (19-extensions.js:1-8).
- Rationale for the dual-store design: localStorage caps ~5 MB/origin; IndexedDB is disk-backed and async (05-persistence.js:8-19).

**In-memory only (session-scoped):**
- `state` global object (04-state.js:183-201); `isGenerating`, `abortController`, `serverConnected`, `scrollPinnedToBottom` (04-state.js:203-215).
- RAG warmth map `_ragWarmth` (threadId → entityId → remainingTurns) — deliberately not synced (08-rag.js:268-270).
- `_currentModelFile`, `_loreLastOutcome`, `_lastWakeResumeAt`, `_pendingAttachments`.

**Origin-silo hazard** (`portability hazard`): each LAN IP/hostname is a separate browser origin with its own storage. The `.local` hostname bookmark + `/state` server sync exist specifically to patch this (06-state-sync.js:1-25, launch.bat:1725-1742).

### Server-side state (project root, written by launch.bat / fileserver.ps1)

| File | Writer | Purpose |
|---|---|---|
| `.gobbonet-secret` | launch.bat (PowerShell) | `salt:hash` (salted SHA-256, lowercase hex, one line, no trailing newline). Never committed (.gitignore:2). |
| `.gobbonet-state.json` | fileserver.ps1 `/state` POST/PUT | Rolling server-side backup of the full client state blob; JSON-validated before write (fileserver.ps1:545-564). |
| `.swap-status.json` | fileserver.ps1 | Hot-swap phase machine: `{phase, file, name, message, started_at}`. |
| `.swap-in-progress` | fileserver.ps1 | Lock file; monitor loop stands down while present; removed on ready/error/boot (fileserver.ps1:23-27, 137-140). |
| `.llama-launch.cmd` | launch.bat / fileserver.ps1 | The llama-server command line; rewritten on hot-swap; "whichever did it last wins" (launch.bat:246-252). |
| `.embed-launch.cmd` | launch.bat | Embed server launcher (mirror of the above). |
| `.jobs/<id>.sse/.json/.cancel` | fileserver.ps1 | Detached generation spool: raw SSE bytes, status JSON, cancel flag. 48h retention backstop; deleted on client ack (fileserver.ps1:69-76, 610-612). |
| `.last-lan-ip` | launch.bat | Previous LAN IP for change detection (launch.bat:1743-1749). |
| `active-model.json` | launch.bat / fileserver.ps1 | Active model metadata for the UI (`{id, name, family, ggufFile, maxCtx, thinkingFormat}` shape, launch.bat:1182-1192). |
| `models-list.json` | identify-model.ps1 / fileserver.ps1 | Model catalog for the hot-swap dropdown; `active` flag updated on swap (fileserver.ps1:1251-1264). |
| `hardware.json` | hardware-probe.ps1 | Detected GPU/CPU/RAM/disk + recommended tier (schema 2). |
| `llama-server.log`, `embed-server.log` | llama-server (redirected) | Diagnostics; GPU verification greps these (launch.bat:1447-1496). |
| `models/` | downloads / user | GGUF files (gitignored). |
| `llama-cpp/` | download | Engine binaries (gitignored). |

### Session/auth state

- Session tokens: in-memory hashtable `$Script:Sessions` (token → expiry + client fingerprint); 12h TTL; restart logs everyone out (fileserver.ps1:118-127).
- Client fingerprint: SHA-256 of source IP + User-Agent — coarse anti-replay binding for the plaintext-LAN cookie (fileserver.ps1:259-271).

### Data lifecycle operations

- **Export**: JSON downloads for threads / cards / personas / full backup (21-data.js, chat.html:757-769).
- **Import**: threads/cards/personas merge by ID; full backup replaces everything (chat.html:775).
- **Purge**: per-category or full factory reset (chat.html:798-810).
- **Migrations observed**: localStorage legacy key rename (05-persistence.js:357-392); extensions legacy single-field → array shape (04-state.js:96-134); default-macro seeding with `seededDefaultMacros` tracking (04-state.js:197-200); IndexedDB v1→v2 store additions (05-persistence.js:45-53).
- **Sync protocol**: debounced (~2s) push to `/state`; flush on generation settle; `sendBeacon` on pagehide when settled; boot conflict check via `/state/info` (mtime+size) (06-state-sync.js:78-293).

---

## 2026-08-18 — contracts phase (delegated subagent)

Behavioral-contract view of durable state (what each feature persists, and the invariants that protect it).

### Per-feature persisted state (contracts phase)

| Feature | Persisted state | Location |
|---|---|---|
| Send/stream | user+assistant messages, `genStartedAt`/`genMs`, `pendingJob` breadcrumb, `msg.jobId` | IDB `threads` + `/state` |
| Reroll/edit | `msg.variants[]`, `msg.activeVariant`, per-variant `continuation` (user edits), `genMs`, `smartCapped` | IDB `threads` |
| Branching | new thread with `forkSource:{threadId, at}` | IDB `threads` |
| Lore compression | `thread.lore` (running summary only); `m.archived` flags | IDB `threads` |
| RAG | `vectors` (embedding cache by content hash), `telemetry` (per-turn records) — local-only, never synced | IDB `vectors`/`telemetry` |
| Card code | `card.customCode/customCodeEnabled`; `state._cardCodeStore[cardId]` scratch | IDB `meta` |
| Scheduler | `state.schedules` incl. `lastFired` | IDB `meta` + `/state` |
| Extensions | `state.extensions` (array shape, migrated from legacy single-field) | IDB `meta` + `/state` |
| Macros | `state.macros` + `seededDefaultMacros` tracking | IDB `meta` + `/state` |
| Search | `msg.searchData`; `settings.apiKey` (redacted from `/state`) | IDB + `/state` (minus key) |
| Sync bookkeeping | `gobbonet_sync_meta` (lastKnownMtime) | localStorage (separate key, survives restores) |
| Hot-swap | `.swap-status.json`, `.swap-in-progress`, `.llama-launch.cmd`, `active-model.json`, `models-list.json` active flag | project root |
| Jobs | `.jobs/<id>.{sse,json,cancel}` | project root (transient) |

### Contract-level invariants

- **State blob shape** is single-sourced in `buildStateBlob()` (05-persistence.js:470-490): threads (cleaned of runtime fields `_reasoningDone`/`_parseState`/`_smartLimitAt`), `threadOrder` (array order is the list's source of truth), activeThreadId, settings, characterCards, activeCardId, personaCards, activePersonaId, schedules, sidebarOpen, searchEnabled, folders, extensions, macros.
- **Redaction invariant**: `/state` pushes use `redactedSyncJson` which deletes `settings.apiKey`; a blob-build failure pushes `'{}'`, never garbage (05-persistence.js:416-434).
- **Transient-state invariant**: a snapshot is never published to `/state` while a generation is streaming or the active thread ends in an empty assistant placeholder (06-state-sync.js:56-76).
- **Variant mirroring invariant**: top-level `msg.*` fields always mirror the active variant; parked continuations are NOT in `thread.messages` and don't count toward context (10-chat.js:483-496).
- **Import semantics**: threads/cards/personas merge by ID; full backup replaces everything; personas patched with defaults; legacy `settings.userName` migrated into a persona on full import (21-data.js:86-160).
- **Export envelope**: `{gobbonet_export: type, version: 1, exported: <ms>, …}` (21-data.js:26-57).
- **Card carriers**: `.json` (V1 flat / V2-V3 under `.data`), `.png` (`ccv3` preferred, `chara` fallback), `.charx` ZIP; export writes both `ccv3` and `chara` (16-card-io.js:9-15, 724-727).
- **Job spool lifecycle**: status file written before the empty spool before the worker starts (poll-after-202 always finds both); terminal statuses `done|cancelled|error|interrupted`; DELETE acks and removes; 48h retention backstop (fileserver.ps1:69-76, 811-819).


---

## 2026-08-18 — protocols phase (delegated subagent)

Persistence-semantics detail (closes arch-CF1). Full tables in `findings/protocols/protocols-and-state.md`.

- **IndexedDB `gobbonet-state` v2** (05-persistence.js:33-58): stores `meta` (key `'app'`, wholesale rewrite), `threads` (keyPath `id`, per-record writes; streaming ticks write only the active thread), `vectors` (keyPath `hash`, content-hash cache), `telemetry` (keyPath `turn_id`, ring-buffered at 200). Thread *order* persisted separately as `threadOrder` because IDB key order ≠ user-arranged order (05-persistence.js:95-111, 473-479).
- **Migrations** (05-persistence.js:87-318): all run in `applyLoadedState` on every load path (IDB/localStorage/server restore): persona extraction from legacy settings, macro seeding with `seededDefaultMacros`, thread field backfills, token-limit bump (<8192 → 24576), runtime-flag stripping, orphaned-empty-assistant recovery with reroll-variant rollback.
- **localStorage mirror**: key `gobbonet_chat_state` (legacy `gemma4_chat_state` renamed on load); whole-blob rewrite; quota errors normalized (`QuotaExceededError`/Firefox code/22/1014) → `storageQuotaHit` → server backup becomes source of truth (05-persistence.js:385-396, 439-449).
- **`/state` server blob**: shape = `buildStateBlob()` (05-persistence.js:470-494); `settings.apiKey` stripped (05-persistence.js:416-434); whole-file rewrite, last-write-wins, no locking/versioning/compaction; mtime (ms) is the only version stamp (fileserver.ps1:545-564).
- **Job spool** (`.jobs/<id>.{sse,json,cancel}`): `.sse` append-only raw bytes (writer `FileShare::ReadWrite`); `.json` mutable whole-rewrite with 3×25ms torn-read retry; `.cancel` flag file. Ack-delete + 48h retention backstop (fileserver.ps1:614-635, 721-726, 872-886).
- **Swap state**: `.swap-status.json` mutable whole-rewrite `{phase, file, name, message, started_at, updated_at}`; `.swap-in-progress` presence-only lock; both deleted at fileserver boot (fileserver.ps1:1154-1172, 137-140).
- **Model metadata**: `active-model.json` `{id, name, family, ggufFile, maxCtx, defaultCtx, thinkingFormat}`; `models-list.json` `{active, models:[{file, id, name, family, thinkingFormat, maxCtx, useJinja, chatTemplate, chatTemplateFile, templateHash, active}]}` — whole-rewrite, no locking between launch.bat and fileserver.ps1 writers (launch.bat:1180-1192, identify-model.ps1:181-184, fileserver.ps1:1236-1265).
- **`.gobbonet-secret`**: write-once `<salt>:<hash>` (16-byte salt, SHA-256 of `salt+password`, lowercase hex); verification failure renames to `.bad`, never deletes (launch.bat:349-355, 414-418).
- **Export bundles**: `{gobbonet_export, version:1, exported}` envelope; import merges by ID (threads/cards/personas), full replaces everything (21-data.js:26-57, 86-160).


## 2026-08-18 — porting phase (delegated subagent)

Porting-oriented view of state and storage (synthesis; full bundle in `findings/porting/reverse-engineering-bundle.md`).

- **Storage schemas a port must preserve (core):** IndexedDB `gobbonet-state` v2 (stores `meta`/`threads`/`vectors`/`telemetry`; `threadOrder` persisted separately because IDB key order ≠ user order); the localStorage mirror (`gobbonet_chat_state`, legacy `gemma4_chat_state` rename); the `/state` server blob (shape = `buildStateBlob()`, `settings.apiKey` stripped, mtime-in-ms as the only version stamp); the job spool (`.sse` append-only, `.json` mutable with torn-read retry, `.cancel` flag); swap state (`.swap-status.json` + `.swap-in-progress` lock); model metadata (`active-model.json`/`models-list.json`); `.gobbonet-secret`; export bundles.
- **Migration discipline:** all migrations run in `applyLoadedState` on every load path (IDB, localStorage, server restore) — a port must keep a single migration entry point or restore breaks. Migrations include persona extraction, macro seeding, thread backfills, token-limit bump, runtime-flag stripping, orphaned-empty-assistant recovery.
- **The silo problem:** per-origin browser storage means each LAN IP/hostname is a separate data silo; the `/state` sync + boot decision matrix (SM3) is the patch. A port that changes the storage substrate must still reproduce the decision matrix (auto-restore / prompt / quota-recovery / noop) or lose data on IP rotation.
- **Defect-driven storage changes:** `/state` needs a server-side compare-and-swap on a version stamp (3.1, port differently — convention C05); body-size caps on `/state` and `/llm/jobs` writes (4.3, port differently); BOM-less UTF-8 for all server JSON (compatibility hazard — PowerShell 5.1 writes BOMs, which break the client's `JSON.parse`).
- **Redaction invariant:** `settings.apiKey` is stripped from every `/state` push — a port that drops this leaks the Ollama key to the LAN backup file.
