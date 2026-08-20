# Build and Deploy Findings

Store build pipeline and packaging notes here.

---

## 2026-08-18 — architecture phase (delegated subagent)

### Build model

- **No compile/build step.** The frontend is plain HTML/CSS/JS served as static files; the server side is interpreted PowerShell and batch. The only "build" artifact is the numbered file split: every js/*.js and css/*.css header records that it was "Moved verbatim from chat.html" (or style.css) by a refactor-split.py, with 23-card-code.js, 14-card-code.css, 15-lore-view.css hand-written after the split (`observed fact`: file headers).
- **Missing build inputs** (`open question`): `REFACTOR-PLAN.md` (referenced by every split header as the load-order contract) and `refactor-split.py` are not in the repo. `fonts/atkinson-hyperlegible.woff2` (referenced by css/01-tokens.css:30) is also absent; the CSS documents a graceful monospace fallback.
- **Build stamp**: `CHAT_HTML_BUILD = '2026-05-16-nemo-strict-template-fix'` logged at boot for cache-busting diagnosis (01-config.js:14-15).

### Distribution

- **Primary**: GitHub Releases `GobboNetSetup.exe` (~660 KB, unsigned, per-user install, no admin; Start Menu + desktop shortcuts + uninstaller that preserves downloaded models) (README.md:48-52). Installer sources are not in the repo (`open question`).
- **Alternative**: manual ZIP of the repo; folder structure is load-bearing — flattening css/js breaks the app (README.md:60-82).
- **Runtime downloads (one-time, integrity-verified)**:
  - llama.cpp engine: pinned release tag `b9294`, asset `llama-b9294-bin-win-vulkan-x64.zip` (~300 MB); SHA-256 verified against the digest GitHub's API reports; `LLAMA_PIN_SHA256` is empty by default and self-pins after first download (launch.bat:232-244, 558-576).
  - Chat models: HuggingFace bartowski GGUF repos; downloaded to `<name>.part`, SHA-256 verified against the HF LFS pointer, renamed on match (launch.bat:1040-1128).
  - Embedding model: `nomic-embed-text-v1.5.Q8_0.gguf` (~146 MB) from HF; `EMBED_PIN_SHA256` empty by default, self-pins (launch.bat:278-288, 1522-1548).
- **AV-avoidance design**: engine/model downloads are cmd-native (curl + certutil + tar) specifically because the previous PowerShell-staging pattern tripped behavioral antivirus (launch.bat:536-557, 1080-1088).

### Platform constraints

- Windows 10/11 only, as written (README.md:37). Wine is detected and warned about but not blocked (launch.bat:57-77).
- Depends on System32 tools shipping since Windows 10 1803+: curl.exe, certutil.exe, tar.exe, plus PowerShell with .NET HttpListener (launch.bat:20-55).
- GPU: Vulkan build of llama.cpp (AMD/Intel/some NVIDIA); CUDA build noted as faster for NVIDIA (launch.bat:1468-1469).

### CI/CD

- **None visible in the repo** (`observed fact`: no .github/workflows or equivalent). Releases are produced out-of-band.

### Versioning

- Git history shows versioned releases (v1.5, v1.5.1) with README updates; no version manifest in-repo beyond the build stamp and the pinned llama.cpp tag.

### Porting-relevant packaging notes

- The "build" a port must reproduce is: static file serving + env-configured server + supervisor + one-time verified downloads. There is no dependency manifest (no package.json, no lockfile) — the only pinned external dependency is the llama.cpp release tag.
- `.gitignore` excludes: secrets (`.gobbonet-secret`, `*.secret`, `*.key`), models/engine (`models/`, `llama.cpp/`, `*.gguf`, `*.exe`, `*.dll`, `*.zip`), logs, and runtime state (`.gobbonet-state.json`, `.swap-status.json`, `.last-lan-ip`, `active-model.json`, `.llama-launch.cmd`, `.embed-launch.cmd`) (`.gitignore`:1-29).


## 2026-08-18 — porting phase (delegated subagent)

Porting-oriented view of build and deploy (synthesis; full bundle in `findings/porting/reverse-engineering-bundle.md`).

- **What the "build" is:** there is no build step — plain files served statically; the only pinned external dependency is the llama.cpp release tag `b9294` (SHA-256 verified against the GitHub API digest). A port's packaging must reproduce: static file serving + env-configured server + supervisor + one-time verified downloads.
- **Download discipline to keep:** `.part` staging with rename only after hash match; bad files renamed `.bad`, never deleted; engine and embed downloads must be **pinned at release time** (P6-1, fix before porting — the source ships empty `LLAMA_PIN_SHA256`/`EMBED_PIN_SHA256`); model downloads verified against HF LFS pointers.
- **Deploy surfaces:** GitHub Releases `GobboNetSetup.exe` (unsigned, per-user, no admin) or manual ZIP; installer sources are absent from the repo (q-installer-packaging). LAN deployment = one-time `setup-lan.bat` (firewall scoped to LocalSubnet for 11434/11435/8080 + mDNS UDP 5353) + `.local` bookmark advice.
- **Porting-relevant packaging decisions:** the port replaces launch.bat/fileserver.ps1/setup-lan.bat wholesale (P6-5, port differently); the AV-avoidance download patterns are Windows-specific and die with the batch launcher; the supervision contract (health poll, restart, stand-down during swap) survives.
- **No CI/CD in repo** (`observed fact`); releases are produced out-of-band. `.gitignore` excludes secrets, models, engine binaries, logs, and runtime state.
