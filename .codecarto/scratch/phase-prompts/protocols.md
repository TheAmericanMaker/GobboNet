Read .codecarto/GUIDE.md and continue the CodeCartographer workflow for the phase `protocols`.
Work on this phase only. The analyzed source code is the repository outside .codecarto/.

Required reads before analysis:
- .codecarto/GUIDE.md
- .codecarto/workflow/status.yaml
- .codecarto/templates/phase-handoff.yaml
- .codecarto/findings/protocols/protocols-and-state.md if it already exists (continue instead of duplicating work)
- .codecarto/findings/protocols/SKILL.md
- .codecarto/templates/protocols-and-state.md
- .codecarto/findings/architecture/architecture-map.md
- .codecarto/findings/defect-scan-mechanical/mechanical-defects.md
- .codecarto/CONVENTIONS.md (cross-cutting patterns the orchestrator has promoted)
- .codecarto/DECISIONS.md (numbered project decisions; new entries are appended in your closeout)

Items routed to `protocols` for closure (carry_forward from earlier phases):
- arch-CF1 (defer-to-phase) Wire formats: SSE spool byte format + /llm/jobs chunk framing (chunk_b64, from/max offsets), /state JSON schema + mtime protocol, swap-status phase machine, GGUF metadata fields consumed, character-card V1/V2/V3 field mapping, Ollama web_search schema.
Close each item by editing your phase output to address it, then record the closure in your phase handoff so the framework can remove the carry_forward entry atomically.

Orchestrator duties (perform BEFORE executing this phase; see GUIDE.md §Roles):
- Re-triage these open questions' kind labels — a label is a claim needing its own evidence; re-test whether each is now answerable by reading before accepting it:
  - q-installer-packaging (needs-maintainer-decision, from architecture) GobboNetSetup.exe / launch.exe / launchLAN.exe are referenced by README but absent from the repo; installer internals (file layout, Start Menu registration, uninstaller behavior) are unknown.
  - q-refactor-plan (needs-maintainer-decision, from architecture) Every js/css split header says 'see REFACTOR-PLAN.md before reordering' but the file is not in the repo.
  - q-font-shipping (needs-maintainer-decision, from architecture) fonts/atkinson-hyperlegible.woff2 is referenced by css/01-tokens.css but the fonts/ directory is absent from the repo; whether the installer ships it is unknown.
  - q-accept-loop-scale (needs-runtime-test, from architecture) fileserver.ps1's synchronous GetContext() accept loop handles one request at a time; behavior under multiple concurrent LAN clients is unmeasured.
  - q-ollama-api-version (needs-runtime-test, from architecture) The search proxy forwards to https://ollama.com/api + path; the exact web_search request/response contract and its stability are not pinned in-repo.
  - q-logit-bias-root-cause (needs-runtime-test, from defect-scan-mechanical) README declares logit bias (banned words) non-functional (README.md:264-265). The client path is fully wired (06-state-sync.js:725-793 builds a logit_bias map via /tokenize; 10-chat.js:161-166 merges it into the request body), so the breakage is either upstream (llama-server ignoring/not supporting logit_bias on the pinned build), a request-shape mismatch, or a tokenizer mismatch. Source alone cannot determine which.
  - q-tekken-patch-completeness (needs-runtime-test, from defect-scan-mechanical) README declares the Tekken-tokenizer patch 'may not be thorough enough' (README.md:267-268). The patch (built-in C++ templates for mistral-v3-tekken/mistral-v7, normalization of the unrecognized mistral-v7-tekken name) is present in identify-model.ps1:250-258, launch.bat:1335-1339, and fileserver.ps1:1050-1072, with the known delta documented (trailing space after [INST]/[SYSTEM_PROMPT], identify-model.ps1:246-249). Whether remaining misbehavior exists is unverifiable from source.
- This phase declares secondary outputs. Each should end the phase either written or explicitly accounted for (in Coverage and limits, or a routed handoff entry) — never dropped silently:
  - .codecarto/findings/public-surfaces/public-surfaces.md (exists)
  - .codecarto/findings/runtime-lifecycle/runtime-lifecycle.md (exists)
  - .codecarto/findings/state-and-storage/state-and-storage.md (exists)
  - .codecarto/findings/config-model/config-model.md (exists)
- Contradiction sweep: compare this phase's required reads against completed phases' owner_notes; a measured fact that contradicts a summarized claim is a gap to route through the handoff, not a nuance to smooth over.

Rules:
- Do not modify source files outside .codecarto/.
- Follow the active pipeline and validation protocol.
- Update findings under .codecarto/findings/ for this phase.
- For long phases, checkpoint resumable progress at .codecarto/scratch/checkpoints/protocols.md; Pi writes this automatically after phase compaction.
- Include a Coverage and limits section that names inspected scope, skipped scope, evidence basis, and blind spots; route material gaps through PARTIAL validation and open_questions/carry_forward.
- Use carry_forward only for a real downstream phase in the active pipeline. Put optional spikes, amendments, deltas, maintainer rulings, and opinionated reruns in the handoff's post_pipeline list.
- Give every open_question a stable id (e.g. q-loadconfig-ambiguity). If you omit it, the framework auto-assigns one. When a later phase resolves a question, list its id in open_question_closures to remove it from all phases.
- On completion, write a phase handoff to .codecarto/scratch/handoffs/protocols.yaml (see GUIDE.md). Do NOT directly edit workflow/status.yaml, append THREAD_LOG.md, or create a second closeout.

Handoff requirements (from the active pipeline):
- Run validation per workflow/VALIDATE.md. Append validation block to primary output.
- Write the phase handoff to scratch/handoffs/<phase>.yaml with owner notes, open questions, and carry-forward routings; completion applies it to workflow/status.yaml.
- Provide closeout_summary and optional closeout_content in the handoff; completion writes the closeout and THREAD_LOG.md entry.

Primary output target: .codecarto/findings/protocols/protocols-and-state.md
