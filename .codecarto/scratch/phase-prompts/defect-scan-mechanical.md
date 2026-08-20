Read .codecarto/GUIDE.md and continue the CodeCartographer workflow for the phase `defect-scan-mechanical`.
Work on this phase only. The analyzed source code is the repository outside .codecarto/.

Required reads before analysis:
- .codecarto/GUIDE.md
- .codecarto/workflow/status.yaml
- .codecarto/templates/phase-handoff.yaml
- .codecarto/findings/defect-scan-mechanical/mechanical-defects.md if it already exists (continue instead of duplicating work)
- .codecarto/findings/defect-scan-mechanical/SKILL.md
- .codecarto/templates/mechanical-defects.md
- .codecarto/findings/architecture/architecture-map.md
- .codecarto/CONVENTIONS.md (cross-cutting patterns the orchestrator has promoted)
- .codecarto/DECISIONS.md (numbered project decisions; new entries are appended in your closeout)

Items routed to `defect-scan-mechanical` for closure (carry_forward from earlier phases):
- arch-CF3 (defer-to-phase) Config hazards: LLAMA_PIN_SHA256 and EMBED_PIN_SHA256 ship empty (downloads unpinned until first run); the batch-only password-file check is deliberately looser than the PowerShell consumer; per-model CTX_SIZE/KV_CACHE_TYPE overrides in the download menu can silently diverge from header defaults.
- arch-CF4 (defer-to-phase) README-declared known bugs need location/severity/evidence treatment: logit bias broken (banned words non-functional) and Tekken-tokenizer models misbehaving with a possibly-incomplete patch.
Close each item by editing your phase output to address it, then record the closure in your phase handoff so the framework can remove the carry_forward entry atomically.

Orchestrator duties (perform BEFORE executing this phase; see GUIDE.md §Roles):
- Re-triage these open questions' kind labels — a label is a claim needing its own evidence; re-test whether each is now answerable by reading before accepting it:
  - q-installer-packaging (needs-maintainer-decision, from architecture) GobboNetSetup.exe / launch.exe / launchLAN.exe are referenced by README but absent from the repo; installer internals (file layout, Start Menu registration, uninstaller behavior) are unknown.
  - q-refactor-plan (needs-maintainer-decision, from architecture) Every js/css split header says 'see REFACTOR-PLAN.md before reordering' but the file is not in the repo.
  - q-font-shipping (needs-maintainer-decision, from architecture) fonts/atkinson-hyperlegible.woff2 is referenced by css/01-tokens.css but the fonts/ directory is absent from the repo; whether the installer ships it is unknown.
  - q-accept-loop-scale (needs-runtime-test, from architecture) fileserver.ps1's synchronous GetContext() accept loop handles one request at a time; behavior under multiple concurrent LAN clients is unmeasured.
  - q-ollama-api-version (needs-runtime-test, from architecture) The search proxy forwards to https://ollama.com/api + path; the exact web_search request/response contract and its stability are not pinned in-repo.
- Contradiction sweep: compare this phase's required reads against completed phases' owner_notes; a measured fact that contradicts a summarized claim is a gap to route through the handoff, not a nuance to smooth over.

Rules:
- Do not modify source files outside .codecarto/.
- Follow the active pipeline and validation protocol.
- Update findings under .codecarto/findings/ for this phase.
- For long phases, checkpoint resumable progress at .codecarto/scratch/checkpoints/defect-scan-mechanical.md; Pi writes this automatically after phase compaction.
- Include a Coverage and limits section that names inspected scope, skipped scope, evidence basis, and blind spots; route material gaps through PARTIAL validation and open_questions/carry_forward.
- Use carry_forward only for a real downstream phase in the active pipeline. Put optional spikes, amendments, deltas, maintainer rulings, and opinionated reruns in the handoff's post_pipeline list.
- Give every open_question a stable id (e.g. q-loadconfig-ambiguity). If you omit it, the framework auto-assigns one. When a later phase resolves a question, list its id in open_question_closures to remove it from all phases.
- On completion, write a phase handoff to .codecarto/scratch/handoffs/defect-scan-mechanical.yaml (see GUIDE.md). Do NOT directly edit workflow/status.yaml, append THREAD_LOG.md, or create a second closeout.

Handoff requirements (from the active pipeline):
- Run validation per workflow/VALIDATE.md. Append validation block to primary output.
- Write the phase handoff to scratch/handoffs/<phase>.yaml with owner notes, open questions, and carry-forward routings; completion applies it to workflow/status.yaml.
- Provide closeout_summary and optional closeout_content in the handoff; completion writes the closeout and THREAD_LOG.md entry.

Primary output target: .codecarto/findings/defect-scan-mechanical/mechanical-defects.md
