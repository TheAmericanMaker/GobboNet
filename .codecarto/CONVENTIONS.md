# Conventions

<!--
  Project-level skeleton. Copy this to `.codecarto/CONVENTIONS.md` (one level up from templates/)
  the first time the orchestrator promotes a convention. Then add entries as they accumulate.

  This file holds cross-cutting patterns that have been promoted to project-wide invariants.
  Every new session reads this file and either honors these conventions or documents why it
  diverges.

  This file is **orchestrator-maintained**. Phase executors propose additions in their session
  closeout; the orchestrator promotes them at the phase boundary. In an inline run the same chat
  does both — the rule is about *when* (between phases, deliberately), not about which thread.
-->

Cross-cutting patterns promoted to project-wide invariants. Every session reads this file at start
and either honors these conventions or documents why it diverges.

This file is **orchestrator-maintained**. Phase executors propose additions in their closeout's
"Proposed Conventions" section; the orchestrator promotes them here at the phase boundary — in an
inline run, the same chat changing hats between phases.

## How conventions get added

A new entry lands here when ONE of the following holds:

1. **Three independent sessions** reach for the same pattern (the "lift if it generalizes" rule
   applied to conventions themselves), OR
2. **One session** explicitly promotes a pattern in its closeout report and the orchestrator
   confirms it generalizes, OR
3. **The spec or framework feedback corpus** identifies a project-wide invariant that future
   implementing sessions need to know about.

The orchestrator owns this file. Implementing sessions propose; orchestrator promotes.

## Entry shape

Each convention is a numbered section (`## C<NN>. <Title>`) with three required parts:

- **Body** — the rule itself, in prose. May include a code block for shape contracts.
- **Why:** — the reason the rule exists. Often a past incident or a defect class the rule
  prevents. Future maintainers judging edge cases need to know *why* to judge whether the rule
  applies.
- **How to apply:** — when and where the rule kicks in. Should answer "is this case in scope?"

Optional:
- **Current implementers:** — files/modules that already follow the rule. Useful as worked examples.
- **Source:** — the closeout entry where the orchestrator promoted this convention.

---

## C01. Numbered load-order contract

The `js/` and `css/` files are loaded in strict numeric order into one shared global namespace. Any reordering, renaming, or introduction of a module system must preserve the load-order contract declared in every split header.

**Why:** Every split file's header states "Load order is a contract — see REFACTOR-PLAN.md before reordering." The files reference each other's globals freely with no module system; 24-boot.js is the boot entry point and 13-components.css must load last among generated stylesheets.

**How to apply:** Any change to chat.html's script/style tags, any file rename, or any refactor toward modules must first verify the numeric order and the global-namespace assumptions.

**Current implementers:** chat.html:881-900 (load order); all js/*.js and css/*.css headers.

**Source:** 2026-08-18-architecture closeout, proposed convention `numbered-load-order-contract`.

---

## C02. GEMMA_* env-var handoff

Cross-process configuration between launch.bat and fileserver.ps1 passes exclusively through `GEMMA_*` environment variables, never through command-line interpolation.

**Why:** Batch quoting/escaping is fragile; the env-var channel is the established, documented seam (fileserver.ps1:29-32 lists the full set; launch.bat:1644-1667 sets them).

**How to apply:** Any new config value needed by fileserver.ps1 (or the search proxy) must be added as a `GEMMA_*` env var set by launch.bat and read via `Get-EnvOrDefault`, not as a positional argument.

**Current implementers:** launch.bat:1644-1667; fileserver.ps1:42-67.

**Source:** 2026-08-18-architecture closeout, proposed convention `env-var-handoff`.

---

## C03. Health probes must verify identity

Any "is my service already running" probe must verify the responder's identity — expected status code and body shape — not merely that something answered. Substring matches like `ok` are not identity checks.

**Why:** Finding P1-2: the launcher's health/probe checks accept any HTTP response or any body containing "ok", so a foreign service on the port (Ollama, documented as a common port-grabber) is misdetected as a healthy llama-server and the launcher proceeds against the wrong backend. Same pattern at the fileserver port probe (P6-4).

**How to apply:** Every health check, port probe, and "already running" branch must pin the expected responder (status code, content-type, body marker) before treating the port as owned.

**Current implementers:** None — this is the defect the convention prevents.

**Source:** 2026-08-18-defect-scan-mechanical closeout, proposed convention `health-probe-must-verify-identity`.

---

## C04. Process kills must scope by role

Killing or restarting a process by bare image name must account for every role that image plays. A shared binary (llama-server.exe serving both chat and embeddings) needs role-scoped targeting or coordinated respawn.

**Why:** Finding P1-1: both the crash-restart path and every hot-swap kill all processes named `llama-server.exe` — including the embedding server — and neither path restarts it, silently degrading RAG semantic search to tag-only until the next full launch.

**How to apply:** Any taskkill/Get-Process by image name must enumerate the roles that binary serves in this system and either target by role (window title, port, command line) or respawn every role it kills.

**Current implementers:** None — this is the defect the convention prevents.

**Source:** 2026-08-18-defect-scan-mechanical closeout, proposed convention `process-kill-must-scope-by-role`.

---

## C05. Server-side write conflict checks

Any multi-writer shared state endpoint must enforce a server-side conflict check (compare-and-swap on a version stamp) rather than relying on client-side advisory protocols. Last-write-wins without a server-side guard silently destroys concurrent edits.

**Why:** Finding 3.1: `/state` POST/PUT writes unconditionally (fileserver.ps1:545-564) while the client mtime protocol (06-state-sync.js) is advisory only; the boot decision matrix can only detect the clobber after the fact.

**How to apply:** Any endpoint that accepts whole-document writes from multiple clients must read the stored version stamp and reject or merge on mismatch — never write unconditionally.

**Current implementers:** None — this is the defect the convention prevents.

**Source:** 2026-08-18-defect-scan-semantic closeout, proposed convention `server-side-write-conflict-check`.

---

## C06. Error messages must match the recovery path

An error message that promises a recovery action must be backed by a code path that can actually perform it. If the code forecloses the promised recovery, change the message or change the path.

**Why:** Finding 5.1: the 401 mid-generation message promises "reload the page and sign in to re-attach" but the same code path DELETEs the job, cancelling the live generation (03-generation.js:452-465, fileserver.ps1:872-880).

**How to apply:** When writing an error message that names a recovery step, trace the code path that runs after the message is shown and confirm the step is still possible. If it isn't, the message must say what actually happens.

**Current implementers:** None — this is the defect the convention prevents.

**Source:** 2026-08-18-defect-scan-semantic closeout, proposed convention `error-message-must-match-recovery-path`.

---

## Pending proposals

Staged by completion from each phase handoff's `proposed_conventions`. The orchestrator promotes an entry into a numbered convention above (or removes it with a note) at the phase boundary — see GUIDE.md §Roles.

<!-- 2026-08-18: architecture proposals promoted to C01/C02; defect-scan-mechanical to C03/C04; defect-scan-semantic to C05/C06. porting proposal `porting-bundle-is-the-compression-boundary` removed: it restates GUIDE.md §Synthesis compression boundary (framework guidance), not a project-level invariant. -->
