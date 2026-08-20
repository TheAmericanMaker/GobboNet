# Decisions

<!--
  Project-level skeleton. codecarto_init seeds this to `.codecarto/DECISIONS.md` (one level up
  from templates/); entries accumulate as phases complete.

  This file is an append-only numbered log of cross-cutting decisions made during the project
  that diverge from spec text, prompt direction, or the obvious-default. Each entry is a
  one-liner with a back-reference to the closeout where the decision was made and the rationale
  lives.

  This file is **append-only and orchestrator-maintained**. Completion appends each phase
  handoff's `decisions` array as rows under `## Completion log` (added at first use); the
  orchestrator may re-file entries into the category sections below. Numbering is shared across
  the whole file.
-->

Append-only log of cross-cutting decisions that diverge from spec text, prompt direction, or
obvious-default. Each entry is a one-liner with a back-reference to the closeout where the
decision was made and the rationale lives.

This file is **append-only and orchestrator-maintained**. Completion appends each phase handoff's
`decisions` array as numbered rows under `## Completion log`; the orchestrator may re-file entries
into the category sections at the phase boundary.

## Format

```
D<NNN> | <ONE-LINER> | <SOURCE-CLOSEOUT> | <RATIONALE-POINTER>
```

- `D<NNN>` — sequential within category (see Categories below). Use leading zeros to width 3.
- `<ONE-LINER>` — the decision in one sentence. Should answer "what did we decide and why is it
  not obvious?"
- `<SOURCE-CLOSEOUT>` — closeout filename (e.g., `2026-05-02-architecture`).
- `<RATIONALE-POINTER>` — short pointer to where the full rationale lives. Usually the closeout's
  "Decisions Beyond Prompt" section.

## Categories

Numbering is sequential within each category, not within the file. Future sessions add at the
end of the appropriate category.

- **D000–D099** — Type system, discriminators, cross-cutting type discipline
- **D100–D199** — Toolchain, lint, project-level config
- **D200–D299** — Module-internal patterns
- **D300–D399** — Cross-module primitives lifted into a shared module
- **D400–D499** — Native code, OS-platform-specific, sandboxing
- **D500–D599** — Pending spec deltas (proposed but not yet applied)
- **D600–D699** — Reserved for future categories — extend the table here when you open a new range

Categories are project-specific. Edit this list when the project's shape demands a new range.

---

## D000–D099: Type system and discriminator

<!-- Append entries here as they accumulate. Example:

D001 | Outcome<T,E> is a brand newtype keyed by a unique Symbol, NOT a value-union; only OutcomeSink can construct one. | 2026-05-02-protocol | Spike List #11 requires unconstructable-outside-the-sink.

-->

## D100–D199: Toolchain and lint

## D200–D299: Module-internal patterns

## D300–D399: Cross-module primitives lifted

## D400–D499: Native / platform-specific

## D500–D599: Pending spec deltas

---

## How decisions get added

Completion appends every phase handoff's `decisions` array as `D<NNN>` rows under
`## Completion log` — nothing gets stranded in closeout prose. The orchestrator may re-file an
entry into the category sections above at the phase boundary. Phase executors never edit this
file directly; they record decisions in the handoff.

If a decision is later overturned, do **not** delete the entry. Append a new `D<NNN>` superseding
it (with `Supersedes D<old-NNN>` in the one-liner) and update the old entry's one-liner to begin
`SUPERSEDED by D<new-NNN>:`. The history is the value.

## Completion log

Appended by completion from each phase handoff's `decisions` array. The orchestrator may re-file entries into the category sections above; numbering is shared with them.
D001 | Architecture phase treated the repo (not the installer binaries) as the system boundary; installer packaging recorded as open question q-installer-packaging rather than guessed. | 2026-08-18-architecture | closeouts/2026-08-18-architecture.md §Decisions Beyond Prompt (architecture)
D002 | Evidence levels used are the four SKILL.md levels (observed fact / strong inference / portability hazard / open question) with file:line citations, per the phase skill rather than the template's older fact/inference/open-question trio. | 2026-08-18-architecture | closeouts/2026-08-18-architecture.md §Decisions Beyond Prompt (architecture)
D003 | Mechanical scan treated the README's own known-bugs section as observed-fact evidence for the existence of the logit-bias and Tekken defects, with root cause and patch completeness recorded as open questions rather than guessed. | 2026-08-18-defect-scan-mechanical | closeouts/2026-08-18-defect-scan-mechanical.md §Decisions Beyond Prompt (defect-scan-mechanical)
D004 | No critical or high severities were assigned: every finding is a silent degradation, latent risk, or config hazard; nothing found breaks normal operation outright. Severity was deliberately not inflated. | 2026-08-18-defect-scan-mechanical | closeouts/2026-08-18-defect-scan-mechanical.md §Decisions Beyond Prompt (defect-scan-mechanical)
D005 | Contracts phase treated the README feature list (README.md:286-357) as the primary contract source and the code as the arbiter of defaults/error behavior, per the phase SKILL.md's source-priority order; doc/code conflicts are recorded explicitly rather than silently resolved. | 2026-08-18-contracts | closeouts/2026-08-18-contracts.md §Decisions Beyond Prompt (contracts)
D006 | The search-privacy claim (README.md:342) vs the passthrough implementation is recorded as a doc/code conflict in the contracts output and left for defect-scan-semantic (arch-CF5) to assess; the contracts phase does not rule on security posture. | 2026-08-18-contracts | closeouts/2026-08-18-contracts.md §Decisions Beyond Prompt (contracts)
D007 | The Ollama web_search upstream response schema beyond {results:[{title,content,url}]} is recorded as an open question (q-websearch-response-fields) rather than guessed; the proxy is a verbatim forwarder so the schema is genuinely not visible in-repo. | 2026-08-18-protocols | closeouts/2026-08-18-protocols.md §Decisions Beyond Prompt (protocols)
D008 | The mid-generation 401 path (client clears breadcrumb + DELETEs the job, cancelling the live generation) is recorded as a protocol fact and routed to defect-scan-semantic as proto-CF1 rather than ruled on here; the protocols phase documents behavior, it does not rule on defects. | 2026-08-18-protocols | closeouts/2026-08-18-protocols.md §Decisions Beyond Prompt (protocols)
D009 | The two security-posture items (plain-HTTP LAN transport; unsandboxed per-card JS and extensions) are assessed as documented design choices with residual risk rather than accidental bugs, because the source itself discloses the tradeoffs and ships deliberate mitigations (12h TTL, fingerprint binding, imported-code opt-in, wrapped hooks); they are tagged 'port differently' so a port re-makes the choice consciously. | 2026-08-18-defect-scan-semantic | closeouts/2026-08-18-defect-scan-semantic.md §Decisions Beyond Prompt (defect-scan-semantic)
D010 | The logit_bias shape mismatch (map of token-id strings vs llama-server's OpenAI-compatible array-of-{id,bias}) is recorded as a strong-inference root cause for the README-declared broken banned-words feature (P1-3), not an observed fact; definitive confirmation stays with q-logit-bias-root-cause (needs-runtime-test). | 2026-08-18-defect-scan-semantic | closeouts/2026-08-18-defect-scan-semantic.md §Decisions Beyond Prompt (defect-scan-semantic)
D011 | No critical or high severities were assigned in the semantic scan: every finding is a silent degradation, edge-case failure, defense-in-depth gap, or documented design choice; severity was deliberately not inflated (extends D004 to the semantic pass). | 2026-08-18-defect-scan-semantic | closeouts/2026-08-18-defect-scan-semantic.md §Decisions Beyond Prompt (defect-scan-semantic)
D012 | The bundle follows the contracts file's actual 55 contract sections rather than the owner_notes' claimed 40; the discrepancy is surfaced in the bundle's Coverage and limits and here for the orchestrator to reconcile. | 2026-08-18-porting | closeouts/2026-08-18-porting.md §Decisions Beyond Prompt (porting)
D013 | Defect dispositions are carried forward verbatim from the two defect reports (fix before porting / port differently / leave behind); the porting phase re-groups them by disposition but does not re-adjudicate severities or actions. | 2026-08-18-porting | closeouts/2026-08-18-porting.md §Decisions Beyond Prompt (porting)
D014 | The two security-posture items (plain-HTTP transport, unsandboxed card code/extensions) remain 'port differently' per D009: the bundle instructs the reimplementation to re-make those choices consciously rather than silently inheriting or silently dropping them. | 2026-08-18-porting | closeouts/2026-08-18-porting.md §Decisions Beyond Prompt (porting)
D015 | Language-agnostic spec variant selected by the user via the Strategic Alignment Hook; no target stack, project identity, or scope cuts are pre-locked (closes porting-CF1). | 2026-08-18-reimplementation-spec | closeouts/2026-08-18-reimplementation-spec.md §Decisions Beyond Prompt (reimplementation-spec)
D016 | The spec's defect accounting carries the two defect reports' dispositions verbatim (fix before porting / port differently / leave behind) and does not re-adjudicate severities or actions (extends the porting phase's decision). | 2026-08-18-reimplementation-spec | closeouts/2026-08-18-reimplementation-spec.md §Decisions Beyond Prompt (reimplementation-spec)
D017 | The two security-posture items (plain-HTTP transport, unsandboxed card code/extensions) are instructed as conscious re-decisions for the port (per D009), not silently inherited or silently dropped. | 2026-08-18-reimplementation-spec | closeouts/2026-08-18-reimplementation-spec.md §Decisions Beyond Prompt (reimplementation-spec)
