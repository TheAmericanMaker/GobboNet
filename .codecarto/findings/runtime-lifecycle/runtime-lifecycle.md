# Runtime Lifecycle Findings

Store runtime sequence notes here.

---

## 2026-08-18 — architecture phase (delegated subagent)

### Host boot sequence (launch.bat)

1. **Keep-open guard**: if `GOBBONET_KEEPOPEN` unset, relaunch self under `cmd /k` so the window never silently vanishes (launch.bat:11-15).
2. **Preflight probes**: run (not just find) curl.exe, powershell (echo marker + resolve `System.Net.HttpListener`), certutil, tar; Wine detection via `HKCU\Software\Wine` registry probe (launch.bat:32-77). Missing tools print warnings but do not abort (except PowerShell, which is required for the server stack).
3. **Password**: if `.gobbonet-secret` missing → `:setup_password` (PowerShell SecureString read, salted SHA-256, written via temp .ps1 + `-File`; plaintext never in env) (launch.bat:310-362). Then read-back verification with 5 retries (AV lock tolerance) and format check `^hex:hex$`; on failure the file is renamed `.bad`, never deleted (launch.bat:374-433). `reset-password` arg deletes the file first (launch.bat:144-148).
4. **Engine**: find `llama-server.exe` (root, then recursive under `llama-cpp\`); if absent, offer download of pinned release zip (tag `b9294`, asset `llama-<tag>-bin-win-vulkan-x64.zip`), SHA-256 verified against GitHub API digest, extracted with tar (launch.bat:480-638). Download path is cmd-native (curl+certutil+tar) to avoid AV behavioral flags (launch.bat:536-557).
5. **Model**: `:check_model` — explicit `MODEL_GGUF`, else scan `models\*.gguf`; 0 → `:model_download_menu` (hardware probe → catalog with `[ RECOMMENDED FOR YOUR PC ]` marker → VRAM safety net → per-choice DL_REPO/DL_FILE/CTX_SIZE/KV_CACHE_TYPE overrides) (launch.bat:646-1040); >1 → interactive pick (launch.bat:677-694). Downloads go to `<name>.part`, SHA-256 verified against the HuggingFace LFS pointer, renamed only on match (launch.bat:1040-1128).
6. **Identify**: `:identify_model` runs identify-model.ps1 with `-Emit batch`; the emitted `set` statements are `call`ed into the environment (launch.bat:710-744). Falls back to filename heuristics if the script is missing.
7. **Write metadata**: `active-model.json` (launch.bat:1180-1192) and `models-list.json` (launch.bat:1214-1221).
8. **Start llama-server**: `:start_server` — probe `/health` first (already running → skip); build `.llama-launch.cmd` with `--model --port 11434 --host 127.0.0.1 --ctx-size --n-gpu-layers --cache-type-k/v --parallel 1 [--jinja|--chat-template] --reasoning-format auto` (launch.bat:1381-1390); spawn via `start /min`; wait loop: fast-fail if process died (after 3 polls), 300×2s cap (~10 min) for first shader compile (launch.bat:1392-1440).
9. **GPU verification**: `:verify_gpu` greps the log for `offloaded`/`Vulkan0`/`CUDA0`/`Metal0`; warns + prompts on failure; VRAM-pressure grep (launch.bat:1447-1496).
10. **Embed server** (optional): `:start_embed` — probe `:11436/health`; download nomic-embed-text if missing (SHA-256 pin optional); spawn second llama-server `--embeddings`, CPU-only by default; any failure degrades RAG to tag-only, never blocks (launch.bat:1507-1557).
11. **Search proxy**: `:start_proxy` — probe `:11435/health`; spawn hidden PowerShell HttpListener (encoded command) forwarding to `https://ollama.com/api`; 10×1s wait, failure is non-fatal (launch.bat:1599-1622).
12. **File server**: `:launch` — probe `:8080`; set `GEMMA_*` env (root, ports, server exe, model dir, ctx, gpu layers, kv type, log, launch script, access secret); spawn `fileserver.ps1` hidden; 8×1s wait, failure non-fatal for desktop use (launch.bat:1627-1682).
13. **LAN/mDNS**: `:get_lan_ip` (ipconfig parse), hostname lowercase via PowerShell, `.local` ping check, IP-change detection vs `.last-lan-ip` with warning + bookmark advice (launch.bat:1687-1758).
14. **Open browser** → `http://127.0.0.1:8080`; 8s (15s on IP change) pause; minimize window (P/Invoke ShowWindow) (launch.bat:1826-1834).
15. **Monitor loop**: every 15s `:http_health` on `127.0.0.1:11434/health`; on failure: if `.swap-in-progress` exists → stand down; else taskkill llama-server, restart from `.llama-launch.cmd`, wait up to 90×2s, log tail on failure, keep retrying (launch.bat:1839-1895).

### Browser boot sequence (24-boot.js)

1. Async IIFE: `await loadState()` — IndexedDB `gobbonet-state` open/migrate (v1→v2 adds `vectors`/`telemetry` stores), localStorage mirror + legacy-key migration, then populate `state` (24-boot.js:20-22, 05-persistence.js:20-54, 357-392).
2. `checkServerStateOnBoot()` — `GET /state/info`; if local empty or server newer → auto-restore or prompt; restore may reload the page and rerun boot (06-state-sync.js:224-293).
3. Resume pending generation jobs (breadcrumbs): finished → fold in silently; running → re-attach live; vanished → keep partial + honest note (10-chat.js:817-832).
4. Fetch `default-characters.json` (fails silently on file://) (24-boot.js:49-56).
5. `render()` → `scrollToBottom()` → scroll-pin tracking → card background → sched count (24-boot.js:57-62).
6. Timers: 5s `checkConnection()` (re-renders landing pill), 30s `checkSchedules()` (24-boot.js:68-75).
7. Page-lifecycle wiring: `visibilitychange` (hidden+generating → local flush; visible → `handleAppWake`), `pagehide` (local save + `sendBeacon` to `/state` when settled), `pageshow`/`focus`/`online` → wake-resume with 1s cooldown and `_appBooted` gate (24-boot.js:78-154).

### Generation lifecycle (per turn)

1. `sendMessage` (10-chat.js) → cancel auto-continue if manual → build context via `buildContextMessages` (08-rag.js:614 — the single RAG injection seam: dual retriever + lore + persona + macros) → `POST /llm/jobs` (or legacy direct stream on file:///old fileserver, 03-generation.js:31-34, 471-475).
2. Server: worker runspace makes the upstream llama-server call, spools raw SSE bytes to `.jobs/<id>.sse`; client polls `GET /llm/jobs/<id>?from=N` and feeds bytes through the same parser pipeline (03-generation.js:8-34).
3. Streaming render with smart auto-scroll (14-scroll.js); CoT watchdog auto-stop (10-chat.js:291-298); Stop button sets `.jobs/<id>.cancel` (fileserver.ps1:730).
4. On settle: flush state sync (debounce collapse), lore compression may fire (07-prompt.js:257-289), telemetry record appended (08-rag.js).

### Hot-swap lifecycle

`POST /swap-model` → lock `.swap-in-progress` → `Stop-LlamaServer` → rewrite `.llama-launch.cmd` → update `models-list.json` active flag + `active-model.json` → spawn new server via `cmd /c start /min` → 202. Client polls `/swap-status` ~1.5s; server promotes to `ready` when `/health` returns 200, to `error` on process death (>5s grace) or 180s timeout; lock removed on ready/error (fileserver.ps1:1270-1445, 02-model.js:249-257).

### Shutdown and cleanup

- User closes launcher window / Ctrl+C; child processes die with the console session (no explicit shutdown handler in fileserver.ps1).
- Boot-time hygiene: stale `.swap-in-progress`/`.swap-status.json` removed by both launch.bat (468-475) and fileserver.ps1 (137-140).
- Job spools: deleted on client ack; 48h retention backstop swept lazily on job traffic (fileserver.ps1:74, 160-164, 772-774).
- Sessions: in-memory only; server restart logs everyone out (fileserver.ps1:118-120).

### Background/scheduled work

- launch.bat monitor loop (15s) — the only host-side background task.
- Browser: 5s connection check, 30s scheduler check, auto-continue countdown (20s gap), CoT watchdog, debounced state-sync push, RAG warmth decay (per-turn, in-memory).
- fileserver.ps1: no timers; housekeeping piggybacks on job traffic.

---

## 2026-08-18 — contracts phase (delegated subagent)

Behavioral-contract view of the runtime sequences (user-visible triggers and outcomes; complements the architecture phase's step lists).

### Per-turn generation contract (user-visible sequence)

1. Send blocked while `isGenerating` or input empty (10-chat.js:15-17); manual send cancels an active auto-continue chain (10-chat.js:21-23).
2. Optional web search runs BEFORE context build; results saved on the user message (10-chat.js:113-131).
3. Context build: token budget = tokenLimit×0.9; compression fires when projected > budget − 20% response reserve; archives to 65% target, keeps 22% trailing reserve verbatim (08-rag.js:614-722).
4. Transport: `POST /llm/jobs` (202 + id) then poll `?from=N`; legacy direct SSE on file:///old fileserver (03-generation.js:419-492).
5. Settle: finalize parser state → card-code `reply` hook → outcome notes → `genMs` stamp → save → force server flush → pin-aware scroll (10-chat.js:186-247).
6. Auto-continue: on success, next send scheduled 20s later; on error/abort the chain dies (10-chat.js:254-258, 09-threads.js:389-427).

### Contract-relevant lifecycle facts

- **Scheduler fires only while the tab is open**, not generating, and server connected; one schedule per 30s check; one-time schedules self-delete after firing; daily guarded by `lastFired === today` (22-scheduler.js:151-195).
- **Job resume states** (10-chat.js:814-826): terminal → silent byte-0 replay; running → live re-attach; vanished → partial + note; unreachable → breadcrumb kept for later retry. Wake resumes gated by `_appBooted` + 1s cooldown (24-boot.js:120-145).
- **State sync cadence**: debounced ~2s push; transient-state guard defers mid-stream snapshots; force-flush on generation settle; `sendBeacon` on pagehide only when settled (06-state-sync.js:78-193).
- **Hot-swap client contract**: dropdown disabled during swap; 800ms grace before first poll; ~1.5s poll; 180s client budget; revert dropdown on failure (02-model.js:296-361).
- **Boot always lands on the dashboard**: `state.activeThreadId = null` before first render; active thread preserved in state but not auto-resumed (24-boot.js:31-35).
- **CoT watchdog** and **smart limit** both ship disabled by default (04-state.js:62-64) — README presents them as features without noting the default-off state (doc nuance recorded in behavioral-contracts.md §Doc/Test Conflicts #6).


---

## 2026-08-18 — protocols phase (delegated subagent)

Protocol-level lifecycle detail (closes arch-CF1). Full tables in `findings/protocols/protocols-and-state.md`.

- **Job lifecycle (server)**: status file → empty spool → worker runspace, in that order, so a poll 1ms after the 202 finds both files (fileserver.ps1:811-819). Worker: 30-min timeouts, cancel-flag check every ≤250ms during read waits, terminal status write with `updated_at` (fileserver.ps1:678-766). Boot hygiene flips orphans to `interrupted` and sweeps >48h files (fileserver.ps1:147-164).
- **Job lifecycle (client)**: `thread.pendingJob` breadcrumb persisted immediately at job start (03-generation.js:436-438); resume pass at boot and on app-wake: terminal → silent byte-0 replay; running → live re-attach; `lost` → note + clear; `unreachable` → breadcrumb kept (10-chat.js:936-995). Poll cadence: 120ms idle, +40ms backoff to 450ms cap, wake-aware sleeps (03-generation.js:366-406).
- **Swap lifecycle**: lock file created before any swap step; kill → port-release poll (5s deadline + 1.5s grace) → launch-script rewrite → models-list/active-model rewrite → detached spawn (fileserver.ps1:1124-1149, 1330-1360). Readiness promotion is lazy (poll-driven); client polls 800ms grace + 1.5s cadence + 180s budget (02-model.js:344-361).
- **State-sync lifecycle**: 2s debounced push, single-flight, transient-state guard (never publishes mid-stream/empty-placeholder snapshots), force-flush on generation settle, `sendBeacon` on pagehide only when settled (06-state-sync.js:78-193). Boot decision matrix: auto-restore / prompt / quota-recovery / noop, with a one-per-tab-session loop guard (06-state-sync.js:200-324).
- **Session lifecycle**: in-memory session table — fileserver restart logs everyone out (fileserver.ps1:118-120). Mid-generation 401 → client clears breadcrumb and DELETEs the job, cancelling the live generation (03-generation.js:375, 452-465) — routed to defect-scan-semantic as proto-CF1.
- **Stream parser lifecycle**: per-message `_parseState` (pre/thinking/content/between/done), `serverSplit` latch on first server-routed reasoning delta, `finalizeStreamMessage` at end-of-stream (flush pending, reparent implicit-think, scrub markers, unwrap tool-call envelope) (03-generation.js:621-660, 1013-1073). Runtime-only fields stripped before persistence (05-persistence.js:451-465).


## 2026-08-18 — porting phase (delegated subagent)

Porting-oriented view of the runtime lifecycle (synthesis; full bundle in `findings/porting/reverse-engineering-bundle.md`).

- **Lifecycle behaviors a port must reproduce (core):** (1) the generation lifecycle — send → context build (RAG injection seam) → `POST /llm/jobs` (or legacy direct stream) → SSE parse → render, with byte-stable detached replay and breadcrumb-based resume (SM1); (2) the hot-swap lifecycle — lock file → kill → launch-script rewrite → metadata rewrite → spawn → poll-driven readiness (SM2), with the lazy-promotion defect (3.2) fixed by a server-side timer; (3) the state-sync lifecycle — 2s debounced push, transient-state guard, force-flush on settle, sendBeacon on pagehide, boot decision matrix (SM3); (4) the session lifecycle — in-memory sessions, 12h TTL, restart logs everyone out (P5).
- **Lifecycle behaviors that are source-specific (incidental):** the batch keep-open guard, console window minimization, AV-avoidance download staging, and the 15s monitor loop's taskkill/tasklist mechanics — the port's supervisor replaces the mechanics but keeps the supervision contract (health poll, restart, stand-down during swap).
- **Lifecycle defects to design around:** crash-restart and hot-swap kill the embed server by bare image name and never restart it (P1-1, fix before porting — role-scoped targeting, convention C04); health probes must verify responder identity (P1-2, convention C03); mid-generation 401 must not cancel the live job (5.1, convention C06); orphaned swap locks must not stand the monitor loop down indefinitely (3.2).
- **Boot sequence to preserve:** browser boot = loadState (IDB open/migrate) → server-state conflict check → resume pending jobs → seed characters → render → timers (5s health, 30s scheduler) → page-lifecycle handlers. The order matters: the conflict check runs before first render, and job resume runs before the user can send.
