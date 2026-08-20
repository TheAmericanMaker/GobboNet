# Configuration Model Findings

Store configuration inheritance and env behavior notes here.

---

## 2026-08-18 — architecture phase (delegated subagent)

### Configuration layers (inheritance order)

1. **launch.bat header variables** (the user-editable layer, launch.bat:112-290):
   - Server: `SERVER_PORT=11434`, `CTX_SIZE=16384`, `GPU_LAYERS=99`, `KV_CACHE_TYPE=q8_0`.
   - Model: `MODEL_GGUF` (empty = auto-detect), `MODEL_ID/DISPLAY/FAMILY/MAX_CTX/THINK_FMT` (defaults `custom`), `MODEL_USE_JINJA=1`, `MODEL_CHAT_TEMPLATE`, `MODEL_CHAT_TEMPLATE_FILE`.
   - Engine pin: `LLAMA_PIN_TAG=b9294`, `LLAMA_PIN_SHA256` (empty = unpinned until first download self-pins).
   - Embed: `EMBED_ENABLE=1`, `EMBED_PORT=11436`, `EMBED_CTX=2048`, `EMBED_GPU_LAYERS=0` (CPU by default), `EMBED_MODEL_GGUF`, `EMBED_MODEL_URL`, `EMBED_PIN_SHA256`.
   - Paths: `LLAMA_DIR`, `MODEL_DIR`, `SERVER_EXE`, `LOG_FILE`, `LAUNCH_SCRIPT`, `SWAP_LOCK`, `SWAP_STATUS`, `SECRET_FILE`.
2. **Per-model overrides in the download menu**: choosing a model sets `CTX_SIZE` and `KV_CACHE_TYPE` per model (e.g. choice 1 → CTX_SIZE=32768, KV_CACHE_TYPE=f16; launch.bat:909-930). These override the header defaults for that session. `portability hazard`/`open question`: the override only applies when the model is chosen via the menu; a hand-placed GGUF keeps header defaults — the two paths can silently diverge.
3. **identify-model.ps1 output** (runtime-derived): GGUF chat-template ground truth overrides `MODEL_ID/DISPLAY/FAMILY/MAX_CTX/THINK_FMT/USE_JINJA/CHAT_TEMPLATE` via emitted `set` statements (launch.bat:710-744). Template precedence: `MODEL_CHAT_TEMPLATE_FILE` (project .jinja, requires --jinja) > `MODEL_CHAT_TEMPLATE` (built-in name, --jinja off) > embedded template via --jinja (launch.bat:1312-1379). Guard rewrites `mistral-v7-tekken` → `mistral-v7` (launch.bat:1335-1339).
4. **`GEMMA_*` environment handoff** (launch.bat → fileserver.ps1, launch.bat:1651-1667): `GEMMA_ROOT`, `GEMMA_LLM_PORT`, `GEMMA_SEARCH_PORT`, `GEMMA_EMBED_PORT`, `GEMMA_SERVER_EXE`, `GEMMA_MODEL_DIR`, `GEMMA_CTX_SIZE`, `GEMMA_GPU_LAYERS`, `GEMMA_KV_CACHE_TYPE`, `GEMMA_LOG_FILE`, `GEMMA_LAUNCH_SCRIPT`, `GEMMA_ACCESS_SECRET`. fileserver.ps1 reads each with `Get-EnvOrDefault` and hardcoded defaults (fileserver.ps1:42-67). Env is used deliberately to avoid batch quoting/escaping issues (launch.bat:1644-1645).
5. **Browser-side settings** (user-editable at runtime, persisted in state.settings, 04-state.js:57-81): `modelName`, `reminderFrequency`, `tokenLimit`, `apiKey` (Ollama search key), `cotTimeoutEnabled/Minutes`, `smartLimitEnabled/Tokens`, `avatarScale`, RAG knobs (`retrievalEnabled`, `retrieverA/B`, `fireThreshold`, `warmthTurns`, `expansionDepth`, `semanticBackstop`, `topKA`, `retrievalBudgetTokens`, `retrievalWindowMsgs`).
6. **Per-card configuration** (04-state.js:3-56): sampler fields (temperature, minP, topK, topP, repeatPenalty, repeatLastN, xtcProbability/Threshold, dryMultiplier), `bannedPhrases`, `logitBiasStrength`, `customCode`/`customCodeEnabled`, lore fields, alt greetings, colors/avatar/background.

### Environment variables (complete matrix)

| Variable | Set by | Read by | Default |
|---|---|---|---|
| `GOBBONET_KEEPOPEN` | launch.bat (self) | launch.bat | unset |
| `GOBBONET_SECRET_OUT` | launch.bat | temp pw script | — |
| `GN_PWCHECK` | launch.bat | pw verification | — |
| `GN_URL` / `GN_OUT` | launch.bat helpers | PowerShell fallbacks | — |
| `GEMMA_*` (12 vars above) | launch.bat | fileserver.ps1 | per fileserver.ps1:48-67 |
| `COMPUTERNAME` | Windows | launch.bat (hostname) | — |

### Secrets handling

- Password: plaintext exists only inside the PowerShell setup process and the instant a login request is checked; stored as salted SHA-256; passed to fileserver.ps1 as `GEMMA_ACCESS_SECRET` (launch.bat:121-141, fileserver.ps1:90-116).
- Ollama API key: stored in browser state (localStorage/IndexedDB), sent as `Authorization: *** to the search proxy, forwarded verbatim to ollama.com (11-search.js:45-52).
- No other credentials in the repo; `.gitignore` excludes secret files.

### Config-related hazards (routed to defect-scan-mechanical as arch-CF3)

- `LLAMA_PIN_SHA256` / `EMBED_PIN_SHA256` ship empty → first download is unpinned (self-pins after).
- Batch-only password-file check is deliberately looser than the PowerShell consumer (launch.bat:404-409).
- Per-model CTX_SIZE/KV_CACHE_TYPE overrides can diverge from header defaults depending on install path.
- `MODEL_CHAT_TEMPLATE` set to an unrecognized name makes llama-server treat the literal text as the template body (documented footgun, launch.bat:213-219).

---

## 2026-08-18 — contracts phase (delegated subagent)

Behavioral-contract view of configuration (what each knob does to user-visible behavior, and the precedence rules).

### Contract-relevant config semantics

- **`tokenLimit` (browser) vs `CTX_SIZE` (server) are separate knobs.** tokenLimit budgets the prompt: 90% is the physical ceiling, minus a 20% response reserve as the compression trigger; CTX_SIZE is the physical server context (08-rag.js:616-659, launch.bat:116). The CONFIG hint text documents the split (chat.html:170-172).
- **`reminderFrequency` is vestigial.** The CONFIG UI still exposes "Reminder every N msgs" (chat.html:165-166) and `saveSettings` persists it (15-cards.js:35), but no code path reads it since personality became a persistent block (08-rag.js:912, 13-dashboard.js:711). Routed to defect-scan-semantic as contracts-CF1.
- **`cotTimeoutEnabled` and `smartLimitEnabled` ship OFF** (04-state.js:62-64) — README features 298-299 are opt-in, not on by default.
- **`apiKey` is redacted from `/state` sync** but lives in plaintext in browser storage and is logged in prefix form to the console (11-search.js:26) — the latter folds into arch-CF5/mech-CF2c.
- **Per-model download-menu overrides (`CTX_SIZE`/`KV_CACHE_TYPE`) are session-only**: not persisted into `models-list.json`, so hot-swaps and later launches use the header defaults (mechanical P6-2; identify-model.ps1:181-184 record shape has no ctx/kv fields).
- **`loadActiveModel` token-limit quirk (P1-5)**: whenever `tokenLimit` equals the default 24576 it is overwritten with the model's `defaultCtx` and saved — a deliberate 24576 cannot be distinguished from "never customized" (02-model.js:42-47).
- **Sampler presets** (precise/balanced/creative) mutate editor sliders without saving; the user must still hit Save (06-state-sync.js:795-820).
- **Smart-limit clamp**: 25-8192 enforced on save, not just in the input (15-cards.js:41).
- **RAG knobs** (`retrievalEnabled`, `retrieverA/B`, `fireThreshold`, `warmthTurns`, `expansionDepth`, `semanticBackstop`, `topKA`, `retrievalBudgetTokens`, `retrievalWindowMsgs`) ride into every telemetry record's `config` block so any turn is reproducible (04-state.js:67-70).

### Precedence chain (behavioral view)

1. launch.bat header vars (user-editable, launch.bat:112-290)
2. download-menu per-model overrides (session-only)
3. identify-model.ps1 GGUF ground truth (overrides model metadata; template precedence: sidecar .jinja > built-in name > embedded --jinja; `mistral-v7-tekken` → `mistral-v7` guard)
4. `GEMMA_*` env handoff to fileserver.ps1 (convention C02)
5. browser `DEFAULT_SETTINGS` + per-card fields (persisted in browser state; UI-editable at runtime)

### Config validation (contract view)

- Password file: `^hex:hex$` verified at boot; batch check deliberately looser than the PowerShell consumer (P6-3); fileserver refuses to start without a valid `GEMMA_ACCESS_SECRET` (fileserver.ps1:99-107).
- `/state` bodies JSON-validated before write (fileserver.ps1:549-555); `/swap-model` filenames sanity-checked (no separators, no `..`, must end `.gguf`) (fileserver.ps1:1309-1314).
- Unrecognized `MODEL_CHAT_TEMPLATE` names become literal template bodies (documented footgun, launch.bat:213-219).
- Empty `LLAMA_PIN_SHA256`/`EMBED_PIN_SHA256` = unpinned first download, self-pins after (P6-1).


---

## 2026-08-18 — protocols phase (delegated subagent)

Config-propagation-as-protocol detail (closes arch-CF1). Full tables in `findings/protocols/protocols-and-state.md`.

- **`GEMMA_*` env handoff** (convention C02): the complete set is `GEMMA_ROOT, GEMMA_LLM_PORT, GEMMA_SEARCH_PORT, GEMMA_EMBED_PORT, GEMMA_SERVER_EXE, GEMMA_MODEL_DIR, GEMMA_CTX_SIZE, GEMMA_GPU_LAYERS, GEMMA_KV_CACHE_TYPE, GEMMA_LOG_FILE, GEMMA_LAUNCH_SCRIPT, GEMMA_ACCESS_SECRET` (launch.bat:1651-1667) plus optional `GEMMA_LLM_API_KEY` (fileserver.ps1:108). Read once at startup via `Get-EnvOrDefault` with hardcoded defaults (fileserver.ps1:42-67) — **no hot reload; config changes require a fileserver restart**.
- **`GEMMA_ACCESS_SECRET` validation**: consumer regex `^([0-9a-fA-F]+):([0-9a-fA-F]+)$`; missing/malformed → fatal exit 1 (fileserver.ps1:96-107). The batch-side check is deliberately looser (launch.bat:404-409, mechanical P6-3).
- **Hot-swap config propagation**: `Build-LaunchScript` rebuilds the llama-server command from the models-list.json record + boot-time `GEMMA_CTX_SIZE`/`GEMMA_GPU_LAYERS`/`GEMMA_KV_CACHE_TYPE` (fileserver.ps1:1011-1111). Per-model menu overrides (CTX_SIZE/KV_CACHE_TYPE) are **not persisted** in the record — swaps and later launches use the header defaults (mechanical P6-2). Template precedence: usable sidecar `.jinja` (forces `--jinja`) > built-in `chatTemplate` name > embedded template via `--jinja`; `mistral-v7-tekken` normalized to `mistral-v7` (fileserver.ps1:1033-1072).
- **Client-side config propagation**: `active-model.json` fetched at boot and re-fetched after a successful swap (02-model.js:322-323); `loadActiveModel` overwrites `tokenLimit` when it equals the default 24576 (mechanical P1-5). Sampler params flow card → request body via `getCardSamplerParams` (06-state-sync.js:502-521); stop strings keyed by `activeModel.family.toLowerCase()` (06-state-sync.js:576-580).
- **Search config**: `state.settings.apiKey` stays in localStorage only — stripped from every `/state` push (05-persistence.js:416-434); the proxy forwards the browser's `Authorization` header verbatim to Ollama (decoded launch.bat:1608).
- **Ports**: 11434 (llama-server), 11435 (search proxy), 11436 (embed server), 8080 (fileserver, hardcoded — no env override, mechanical P6-4).


## 2026-08-18 — porting phase (delegated subagent)

Porting-oriented view of the configuration model (synthesis; full bundle in `findings/porting/reverse-engineering-bundle.md`).

- **Config channels a port must preserve (core):** (1) the `GEMMA_*` env handoff (convention C02) — the complete set is `GEMMA_ROOT, GEMMA_LLM_PORT, GEMMA_SEARCH_PORT, GEMMA_EMBED_PORT, GEMMA_SERVER_EXE, GEMMA_MODEL_DIR, GEMMA_CTX_SIZE, GEMMA_GPU_LAYERS, GEMMA_KV_CACHE_TYPE, GEMMA_LOG_FILE, GEMMA_LAUNCH_SCRIPT, GEMMA_ACCESS_SECRET` + optional `GEMMA_LLM_API_KEY`; read once at startup, no hot reload; (2) the browser-side settings in state (`DEFAULT_SETTINGS` + per-card fields), persisted in IndexedDB/localStorage; (3) the `.gobbonet-secret` password file (`salt:hash`, consumer regex `^([0-9a-fA-F]+):([0-9a-fA-F]+)$`, fatal exit 1 on malformed).
- **Precedence chain:** launch.bat header variables → per-model download-menu overrides (session-only — P6-2) → identify-model.ps1 GGUF ground truth → `GEMMA_*` env → browser settings. The browser `tokenLimit` (prompt budget: 90% used, 10% + response reserve held) and the server `CTX_SIZE` (physical context) are **separate knobs** — a port must keep them separate.
- **Defect-driven config changes:** persist per-model CTX_SIZE/KV_CACHE_TYPE in the model record (P6-2, fix before porting); make the listen port configurable (P6-4, port differently); fix `loadActiveModel`'s silent overwrite of a deliberate 24576 tokenLimit (P1-5, port differently); drop the vestigial `reminderFrequency` control (5.3, port differently).
- **Template precedence (load-bearing):** usable sidecar `.jinja` (forces `--jinja`) > built-in `chatTemplate` name > embedded template; `mistral-v7-tekken` normalized to `mistral-v7`; sidecar sanity checks (must contain `{%`/`{{`, ≥16 chars, not the 404 body).
- **Secret handling invariants:** password hash only (never plaintext in env/disk); Ollama API key stays in browser state, redacted from `/state` sync, forwarded verbatim by the search proxy; optional llama-server `--api-key` injected server-side so the browser never sees it.
