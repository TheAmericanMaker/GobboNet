Read .codecarto/GUIDE.md and continue the CodeCartographer workflow for the phase `architecture`.
Work on this phase only. The analyzed source code is the repository outside .codecarto/.

Required reads before analysis:
- .codecarto/GUIDE.md
- .codecarto/workflow/status.yaml
- .codecarto/templates/phase-handoff.yaml
- .codecarto/findings/architecture/architecture-map.md if it already exists (continue instead of duplicating work)
- .codecarto/findings/architecture/SKILL.md
- .codecarto/templates/architecture-map.md
- .codecarto/CONVENTIONS.md (cross-cutting patterns the orchestrator has promoted)
- .codecarto/DECISIONS.md (numbered project decisions; new entries are appended in your closeout)

Orchestrator duties (perform BEFORE executing this phase; see GUIDE.md §Roles):
- This phase declares secondary outputs. Each should end the phase either written or explicitly accounted for (in Coverage and limits, or a routed handoff entry) — never dropped silently:
  - .codecarto/findings/public-surfaces/public-surfaces.md (missing)
  - .codecarto/findings/runtime-lifecycle/runtime-lifecycle.md (missing)
  - .codecarto/findings/state-and-storage/state-and-storage.md (missing)
  - .codecarto/findings/build-and-deploy/build-and-deploy.md (missing)
  - .codecarto/findings/config-model/config-model.md (missing)

Rules:
- Do not modify source files outside .codecarto/.
- Follow the active pipeline and validation protocol.
- Update findings under .codecarto/findings/ for this phase.
- For long phases, checkpoint resumable progress at .codecarto/scratch/checkpoints/architecture.md; Pi writes this automatically after phase compaction.
- Include a Coverage and limits section that names inspected scope, skipped scope, evidence basis, and blind spots; route material gaps through PARTIAL validation and open_questions/carry_forward.
- Use carry_forward only for a real downstream phase in the active pipeline. Put optional spikes, amendments, deltas, maintainer rulings, and opinionated reruns in the handoff's post_pipeline list.
- Give every open_question a stable id (e.g. q-loadconfig-ambiguity). If you omit it, the framework auto-assigns one. When a later phase resolves a question, list its id in open_question_closures to remove it from all phases.
- On completion, write a phase handoff to .codecarto/scratch/handoffs/architecture.yaml (see GUIDE.md). Do NOT directly edit workflow/status.yaml, append THREAD_LOG.md, or create a second closeout.

Handoff requirements (from the active pipeline):
- Run validation per workflow/VALIDATE.md. Append validation block to primary output.
- Write the phase handoff to scratch/handoffs/<phase>.yaml with owner notes, open questions, and carry-forward routings; completion applies it to workflow/status.yaml.
- Provide closeout_summary and optional closeout_content in the handoff; completion writes the closeout and THREAD_LOG.md entry.

Primary output target: .codecarto/findings/architecture/architecture-map.md
