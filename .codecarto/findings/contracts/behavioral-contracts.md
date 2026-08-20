# Behavioral Contracts — GobboNet

<!--
  Output for the `contracts` phase (pipeline: workflow/pipeline-full-with-deep-audit.yaml).
  Evidence levels used throughout (per findings/contracts/SKILL.md):
  `observed fact` | `strong inference` | `portability hazard` | `open question`.
  Every contract cites file:line. Source priority: README feature list (README.md:286-357)
  first, then chat.html UI, then js/*, fileserver.ps1, launch.bat.
-->

## Surfaces Covered

| Surface type | What it is | Primary owner |
|---|---|---|
| Web UI | chat.html + js/01-24 (browser chat app: chat, threads, characters, RAG, macros, scheduler, data manager, extensions) | UI/rendering + persistence layer (browser) |
| CLI / launcher | launch.bat (first-run setup, downloads, model menu, supervision), setup-lan.bat (one-time admin) | product shell (Windows cmd) |
| HTTP API | fileserver.ps1 on `http://+:8080/` (auth, /state, /llm/jobs, /swap-model, /swap-status, reverse proxies, static) | integration adapter / protocol layer (PowerShell) |
| Storage / export formats | IndexedDB/localStorage state, /state server backup, export/import JSON bundles, character-card V1/V2/V3 files, `.gobbonet-secret` | persistence layer (browser) + fileserver.ps1 |

This section **closes arch-CF2** (user-visible behavior contracts for the README feature list — triggers, defaults, outputs, side effects, error behavior): every feature named in README.md:286-357 has a contract below, grouped by surface.

---

## Feature Contracts

### Surface: Web UI

#### Send message / streaming reply

| Field | Value |
|---|---|
| **Feature** | Type in the input box, press Enter (or click Send); the reply streams in word-by-word. |
| **Trigger or input** | Non-empty trimmed input (or staged attachments) while `isGenerating` is false (10-chat.js:15-17). |
| **Defaults** | Request body: `{model:'local', messages, stream:true, max_tokens:-1}` + per-card sampler params + family stop strings + logit_bias (10-chat.js:166). Sampler defaults: temperature 0.7, min_p 0.05, top_k 40, top_p 0.95, repeat_penalty 1.1, repeat_last_n 64, XTC/DRY off (04-state.js:41-49). |
| **Observable output** | Assistant message appended and rendered incrementally; reasoning shown separately for thinking models; token counter updates; thread floats to top of sidebar (10-chat.js:88-104, 09-threads.js:218-224). |
| **Side effects** | Optional web search runs first and its results are saved onto the user message (10-chat.js:113-131); auto-names the thread from the first user message (10-chat.js:74-78); `{{current_DAT}}` resolved at send time (10-chat.js:60); card-code `send` hook may rewrite the text (10-chat.js:83-86). |
| **Persisted state** | User + assistant messages, `genStartedAt`/`genMs` timing, `pendingJob` breadcrumb; saved to IndexedDB/localStorage and (debounced) to `/state` (10-chat.js:88-97, 03-generation.js:436-438). |
| **Error behavior** | Mid-stream failure appends `*(interrupted — …)*` after any partial text; empty reply with error renders a diagnostic block (03-generation.js:501-537). |
| **Retry or recovery behavior** | Detached job survives navigation; on reload the reply is replayed byte-exactly or re-attached live (10-chat.js:808-826). |
| **Owner (layer/package)** | UI layer — js/10-chat.js, js/03-generation.js, js/08-rag.js (context build). |
| **Evidence level** | observed fact |

#### Stop button

| Field | Value |
|---|---|
| **Feature** | Cut off a reply mid-sentence. |
| **Trigger or input** | Stop button while generating (10-chat.js:261). |
| **Defaults** | n/a |
| **Observable output** | Generation halts; partial text kept with `*(generation stopped)*` appended (03-generation.js:509-516). |
| **Side effects** | Detached job: `POST /llm/jobs/<id>/cancel` (flag file; worker aborts within ~250ms, llama-server frees the slot) (10-chat.js:272-276, fileserver.ps1:730-738); legacy stream: `AbortController.abort()` (10-chat.js:278). Kills any active auto-continue chain (10-chat.js:268). |
| **Persisted state** | Partial reply + stop note saved. |
| **Error behavior** | Cancel request is fire-and-forget; failure leaves the job running (retention sweep collects it). |
| **Retry or recovery behavior** | Reroll regenerates; job resume re-attaches if the cancel didn't land. |
| **Owner (layer/package)** | UI layer — js/10-chat.js; server — fileserver.ps1 job worker. |
| **Evidence level** | observed fact |

#### Reroll (regenerate last reply)

| Field | Value |
|---|---|
| **Feature** | Regenerate the last assistant reply with one click; every prior generation is kept as a flippable variant. |
| **Trigger or input** | Reroll button on the last assistant message; blocked while generating or when a pending job exists (10-chat.js:630-637). |
| **Defaults** | First reroll promotes the existing reply to variant 0; new empty variant becomes active (10-chat.js:644-670). |
| **Observable output** | New reply streams into the same message; ◀ N/M ▶ navigator appears; flipping variants is local and free (no regeneration) (10-chat.js:446-512). |
| **Side effects** | Same request pipeline as send (context rebuild, logit bias, stop strings) via `regenerateFromThread({rerollIntoLastMessage:true})` (10-chat.js:688). |
| **Persisted state** | `msg.variants[]` + `msg.activeVariant`; per-variant `genMs`/`smartCapped` (10-chat.js:532-535). |
| **Error behavior** | Errors/aborts land in the active variant with the same notes as send. |
| **Retry or recovery behavior** | Reroll again; flip back to any earlier variant. |
| **Owner (layer/package)** | UI layer — js/10-chat.js (variants), js/03-generation.js (transport). |
| **Evidence level** | observed fact |

#### Edit message (user and assistant)

| Field | Value |
|---|---|
| **Feature** | Rewrite any message. User edits truncate and regenerate everything below; assistant edits save in place. |
| **Trigger or input** | Edit button → textarea → Save (10-chat.js:335-435). |
| **Defaults** | Empty edit is ignored (10-chat.js:351). |
| **Observable output** | User edit: prior wording parked as variant 0 with its downstream subtree as `continuation`; new wording becomes a fresh variant; thread truncated to the edited message and regenerated (10-chat.js:357-421). Assistant edit: content replaced in place, mirrored into the active variant (10-chat.js:422-434). |
| **Side effects** | Flipping a user variant swaps the whole downstream branch (restores parked continuation) — no tokens spent (10-chat.js:587-628). |
| **Persisted state** | Variants + continuations; parked continuations are NOT in `thread.messages` and don't count toward context (10-chat.js:483-484). |
| **Error behavior** | n/a (local operation). |
| **Retry or recovery behavior** | Flip back to the prior wording via ◀ ▶; its AI replies are restored, not lost. |
| **Owner (layer/package)** | UI layer — js/10-chat.js. |
| **Evidence level** | observed fact |

#### Delete / copy message; copy code block

| Field | Value |
|---|---|
| **Feature** | Delete any message (no undo); copy any message; one-tap copy on code blocks. |
| **Trigger or input** | Per-message action buttons (10-chat.js:437-444; 18-utils.js:178). |
| **Defaults** | n/a |
| **Observable output** | Message removed from thread and re-rendered; clipboard copy. |
| **Side effects** | Context meter refreshes after delete (10-chat.js:443). |
| **Persisted state** | Deletion saved immediately. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | None — delete is permanent (README.md:294 documents no undo). |
| **Owner (layer/package)** | UI layer — js/10-chat.js, js/18-utils.js. |
| **Evidence level** | observed fact |

#### Threads: create, rename, delete, switch, search

| Field | Value |
|---|---|
| **Feature** | Every conversation is a saved thread in the sidebar; rename, delete, switch, and full-text search. |
| **Trigger or input** | +NEW_THREAD; right-click/long-press menu; sidebar search box filters by name/content/tags (12-render.js:348). |
| **Defaults** | New thread: name "New Thread", empty messages, `lore:''`, `pinned:false`, `folderId:null`, `tags:[]`, `forkSource:null` (09-threads.js:166-182); auto-named from first user message (10-chat.js:74-78). |
| **Observable output** | Thread list re-renders; active thread switches; deleting the active thread selects the first remaining (09-threads.js:240-243). |
| **Side effects** | Switching threads cancels an active auto-continue chain (09-threads.js:252-254); deleting a thread cancels its pending job server-side (09-threads.js:235-239); activity bumps a thread to the top of its section (09-threads.js:218-224). |
| **Persisted state** | `state.threads` array order is the list's source of truth (09-threads.js:207-211). |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | Deleted threads are gone (no trash); server backup may still hold a copy until the next sync. |
| **Owner (layer/package)** | UI layer — js/09-threads.js, js/12-render.js. |
| **Evidence level** | observed fact |

#### Folders, tags, pins

| Field | Value |
|---|---|
| **Feature** | Sort threads into collapsible folders, label with colored tags, pin favorites to the top. |
| **Trigger or input** | +FOLDER; thread context menu (move to folder, add tags, pin) (12-render.js:61-192). |
| **Defaults** | Tag color derived from a hash of the tag name over an 8-color palette (12-render.js:29-34). |
| **Observable output** | Pinned/folder/unfiled sections each render a filtered view of the one ordered array (09-threads.js:213-217). |
| **Side effects** | n/a |
| **Persisted state** | `state.folders`, per-thread `folderId`/`tags`/`pinned`. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/12-render.js. |
| **Evidence level** | observed fact |

#### Branching (fork) conversations

| Field | Value |
|---|---|
| **Feature** | Fork a chat at any message into a new thread; the original stays untouched. |
| **Trigger or input** | Branch button on a message (09-threads.js:32-112). |
| **Defaults** | Fork name `⑂ <base name>`; shares history up to the branch point; user-msg fork pre-fills the input with that message's text; AI-msg fork leaves input empty (09-threads.js:13-46). |
| **Observable output** | New thread at top of list, active; sibling branches navigable via branch buttons (09-threads.js:90-91, 142-157). |
| **Side effects** | Deep-copies shared history including variants and continuations (09-threads.js:60-72); mobile sidebar auto-closes (09-threads.js:93-96). |
| **Persisted state** | New thread with `forkSource:{threadId, at}` (09-threads.js:78-88). |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/09-threads.js. |
| **Evidence level** | observed fact |

#### Greeting and alternate greetings

| Field | Value |
|---|---|
| **Feature** | A card's opening message is stamped verbatim into each new thread; alternate greetings become flippable variants. |
| **Trigger or input** | Thread creation with a card that has `greeting` and/or `altGreetings` (07-prompt.js:136-183). |
| **Defaults** | `altGreetingsEnabled:false`; alts are blank-line separated in one textarea (04-state.js:36-37, 07-prompt.js:98-101). |
| **Observable output** | First assistant message injected (never model-generated); ◀ ▶ navigator when >1 opening. |
| **Side effects** | `{{char}}`/`{{user}}`/macros resolved at injection time (07-prompt.js:161). |
| **Persisted state** | Injected message stored in the thread. |
| **Error behavior** | No greeting → thread stays empty, welcome screen renders (07-prompt.js:149). |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/07-prompt.js. |
| **Evidence level** | observed fact |

#### Memory + summarization (lore compression)

| Field | Value |
|---|---|
| **Feature** | Older parts of a long chat are automatically summarized into a running lore so the AI keeps remembering. |
| **Trigger or input** | Context build when `projected > effectiveBudget` (budget = tokenLimit×0.9; effectiveBudget = budget − 20% response reserve) and >1 live message (08-rag.js:614-722). |
| **Defaults** | Target landing 65% of budget; trailing reserve 22% kept verbatim; summary prompt targets <180 words, fielded (SETTING/CHARACTERS/OPEN/EVENTS), max_tokens 700, temperature 0.3; `LORE_MAX_CHARS` 2400 head-trim (07-prompt.js:278, 310-330, 388-390; 08-rag.js:624-633). |
| **Observable output** | "compressing older messages into lore..." indicator; archived messages dimmed with a divider; persistent banner when compression fired during a turn (07-prompt.js:361, 04-state.js:216-221). |
| **Side effects** | Archived messages marked `.archived` (kept for UI, not sent to the model); summary folded into `thread.lore`; lore inspector modal shows the outcome and last-pass reason (07-prompt.js:287, 08-rag.js:754-763). |
| **Persisted state** | `thread.lore` (running summary only — authored lore stays on the card, 09-threads.js:172-175). |
| **Error behavior** | Bad HTTP / empty parse / thrown error all keep the previous lore and record the reason in `_loreLastOutcome` (07-prompt.js:393-398, 467-481, 500-505). |
| **Retry or recovery behavior** | Next turn retries; failure never blocks chat. |
| **Owner (layer/package)** | UI layer — js/08-rag.js (trigger), js/07-prompt.js (summarizer). |
| **Evidence level** | observed fact |

#### Token counter / context meter

| Field | Value |
|---|---|
| **Feature** | See how much of the AI's "memory" is in use. |
| **Trigger or input** | Rendered continuously; mirrors `buildContextMessages` accounting exactly (13-dashboard.js:695-724). |
| **Defaults** | Estimator: ~700 words ≈ 1000 tokens, +4 per message (07-prompt.js:241-255). |
| **Observable output** | Live/archived message counts and token usage vs budget. |
| **Side effects** | n/a |
| **Persisted state** | n/a |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/13-dashboard.js, js/07-prompt.js. |
| **Evidence level** | observed fact |

#### Chain-of-thought (reasoning) view

| Field | Value |
|---|---|
| **Feature** | On models that support it, watch the AI's step-by-step thinking. |
| **Trigger or input** | Model family's `thinkingFormat` (none/deepseek/harmony/gemma) selects the parser (02-model.js:72-78, 03-generation.js:540+). |
| **Defaults** | Format derived from GGUF filename/registry; `--reasoning-format auto` server-side (launch.bat:1381-1390). |
| **Observable output** | Reasoning rendered separately from the reply; reasoning excluded from history sent back to the model (08-rag.js:920-923). |
| **Side effects** | Reasoning tokens counted in the context meter (07-prompt.js:250). |
| **Persisted state** | `msg.reasoning` per message/variant. |
| **Error behavior** | Parser mis-filing (whole reply as reasoning) is recovered in the lore path (07-prompt.js:430-454). |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/03-generation.js (parsers), js/02-model.js (registry). |
| **Evidence level** | observed fact |

#### CoT watchdog (auto-stop on stuck reasoning)

| Field | Value |
|---|---|
| **Feature** | If reasoning hangs, generation is auto-stopped after a configurable runtime. |
| **Trigger or input** | Generation start when `cotTimeoutEnabled` (10-chat.js:289-305). |
| **Defaults** | **Disabled by default** (`cotTimeoutEnabled:false`); minutes default 2, clamped ≥1 (04-state.js:62-63, 10-chat.js:292). |
| **Observable output** | Stop with `*(auto-stopped — runtime exceeded N min limit…)*` note (03-generation.js:511-513). |
| **Side effects** | Routed through `stopGeneration` so both transports honor it (10-chat.js:298-302). |
| **Persisted state** | n/a (runtime timer). |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | Reroll; raise the timer in CONFIG. |
| **Owner (layer/package)** | UI layer — js/10-chat.js. |
| **Evidence level** | observed fact |

#### Smart response limit

| Field | Value |
|---|---|
| **Feature** | Cap reply length: rough token estimate, cut at sentence end, ✂ marker. |
| **Trigger or input** | Streaming feeder when `smartLimitEnabled` (03-generation.js:84-105, 165-190). |
| **Defaults** | **Disabled by default**; 300 tokens, clamped 25-8192 on save (04-state.js:64-65, 15-cards.js:41). |
| **Observable output** | Reply trimmed at a sentence boundary (grace ~15% of cap, else trim back to last finished sentence); ✂ badge. |
| **Side effects** | The cut is a self-abort that does NOT halt an auto-continue chain (10-chat.js:173-175). |
| **Persisted state** | `msg.smartCapped` per variant. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/03-generation.js. |
| **Evidence level** | observed fact |

#### Banned words (logit bias)

| Field | Value |
|---|---|
| **Feature** | Discourage specific words (one per line on the card). |
| **Trigger or input** | Card `bannedPhrases` non-empty at send/reroll (06-state-sync.js:725-731). |
| **Defaults** | `logitBiasStrength:-20`; 8 case/space variants per phrase tokenized via `/tokenize` (04-state.js:55, 06-state-sync.js:711-757). |
| **Observable output** | `logit_bias` map merged into the request body (10-chat.js:161-166). |
| **Side effects** | n/a |
| **Persisted state** | Card fields. |
| **Error behavior** | `/tokenize` unavailable → silently skipped (06-state-sync.js:778-782). |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/06-state-sync.js, js/10-chat.js. |
| **Evidence level** | observed fact — **but the feature is README-declared non-functional** (README.md:264-265); see Doc/Test Conflicts. |

#### System prompt editing + carousel

| Field | Value |
|---|---|
| **Feature** | Edit the card's system prompt; save several prompts and swap between them. |
| **Trigger or input** | Card editor fields; carousel enabled per card (07-prompt.js:9-75). |
| **Defaults** | Carousel off; lines newline-separated; modes: sequential (index advances, persisted) or random (avoids repeating last pick) (07-prompt.js:50-75). |
| **Observable output** | Chosen line injected as `[Narrative direction for this response]` system message just before the final user turn (08-rag.js:912-914). |
| **Side effects** | Sequential mode mutates and saves `card.carouselIndex` (07-prompt.js:61). |
| **Persisted state** | `card.carouselEnabled/carouselPrompts/carouselMode/carouselIndex`. |
| **Error behavior** | Off/empty → null, no injection. |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/07-prompt.js, js/08-rag.js. |
| **Evidence level** | observed fact |

#### Response controls (sampler presets)

| Field | Value |
|---|---|
| **Feature** | Fine-tune temperature, top-k, etc.; three one-click presets. |
| **Trigger or input** | Card editor sliders; preset buttons (06-state-sync.js:795-820). |
| **Defaults** | precise = factory defaults; balanced = looser; creative = XTC+DRY engaged, top_k/top_p disabled (06-state-sync.js:813-820). |
| **Observable output** | Sliders update; presets do NOT save until the user saves the card (06-state-sync.js:800-801). |
| **Side effects** | Params mapped to llama-server API names (`min_p`, `top_k`, `repeat_penalty`, `xtc_probability`, `dry_multiplier`…) (06-state-sync.js:502-524). |
| **Persisted state** | Per-card sampler fields. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/06-state-sync.js, js/15-cards.js. |
| **Evidence level** | observed fact |

#### Built-in macros ({{char}}, {{user}}, {{current_DAT}}, {{continue}}, {{fast_forward}})

| Field | Value |
|---|---|
| **Feature** | Placeholders auto-fill character/user names; `{{current_DAT}}` gives the current date/time; `{{continue}}`/`{{fast_forward}}` nudge the story. |
| **Trigger or input** | Any user message or card text; resolved by `translateTemplates` (17-personas.js:216-226). |
| **Defaults** | `{{continue}}` → "Please continue the scene as all characters involved."; `{{fast_forward}}` → "Please fast-forward to a new scene…" (04-state.js:172-181). |
| **Observable output** | Resolved text in context; `{{current_DAT}}` resolved at send time so history stays accurate (10-chat.js:58-60). |
| **Side effects** | n/a |
| **Persisted state** | Stored message keeps the short macro form for clean rendering (09-threads.js:314-318). |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/17-personas.js, js/10-chat.js. |
| **Evidence level** | observed fact |

#### Auto-continue chain ({{auto_continue_N}})

| Field | Value |
|---|---|
| **Feature** | Keeps a story/task running on its own: N total posts, 20s gap. |
| **Trigger or input** | `{{auto_continue_N}}` in a manual user message (09-threads.js:342-351). |
| **Defaults** | Delay 20s; safety cap 50 posts; first occurrence wins; count <1 → 1 (09-threads.js:323-324, 337-350). |
| **Observable output** | Indicator "AUTO-CONTINUE · posted/total · next in Ns"; each follow-up sends `{{auto_continue}}` which expands to `AUTO_CONTINUE_TEXT` for the model only (09-threads.js:321, 425, 434-461). |
| **Side effects** | Chain is runtime-only: dies on reload, thread switch/delete, manual send, Stop, or generation error (09-threads.js:309-312, 254-257). |
| **Persisted state** | None (deliberate). |
| **Error behavior** | Generation error/abort kills the chain (10-chat.js:254-258). |
| **Retry or recovery behavior** | Re-issue the macro. |
| **Owner (layer/package)** | UI layer — js/09-threads.js, js/10-chat.js. |
| **Evidence level** | observed fact |

#### Custom macros

| Field | Value |
|---|---|
| **Feature** | Create your own `{{trigger}}` shortcuts. |
| **Trigger or input** | Extensions modal → macro editor (20-macros.js:31-87). |
| **Defaults** | Seeded with `continue`/`fast_forward`; `seededDefaultMacros` tracks which were seeded so user deletions stick (04-state.js:172-200). |
| **Observable output** | Macro list with preview; expansion applied wherever templates are translated. |
| **Side effects** | Validation: trigger must be `[a-zA-Z0-9_]+`, non-empty, not a reserved name (`char`, `user`, `current_dat`, `auto_continue`), expansion non-empty; duplicates rejected; rename = delete + add (20-macros.js:58-67, 04-state.js:160). |
| **Persisted state** | `state.macros`. |
| **Error behavior** | `alert()` on invalid input; delete requires confirm. |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/20-macros.js. |
| **Evidence level** | observed fact |

#### Characters: create, edit, copy, delete, activate

| Field | Value |
|---|---|
| **Feature** | Build your own characters (name, description, personality, style, settings); copy/edit/delete; switch active character. |
| **Trigger or input** | Characters modal (15-cards.js:70-118). |
| **Defaults** | `DEFAULT_CARD` "Assistant" (04-state.js:12-56); default characters seeded from `default-characters.json` at boot (24-boot.js:49-56). |
| **Observable output** | Card grid with active highlight; activating a card swaps its custom code in/out (15-cards.js:108-118). |
| **Side effects** | Card background/colors applied to the chat (15-cards.js:117). |
| **Persisted state** | `state.characterCards`, `state.activeCardId`. |
| **Error behavior** | Last remaining card cannot be deleted (15-cards.js:102). |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/15-cards.js. |
| **Evidence level** | observed fact |

#### Character card import (V1/V2/V3)

| Field | Value |
|---|---|
| **Feature** | Import standard `.json` / `.png` / `.charx` cards from other AI chat apps. |
| **Trigger or input** | File picker in the character editor (16-card-io.js:1-15). |
| **Defaults** | Field mapping: `system_prompt+description+scenario+mes_example+post_history_instr` → writingStyle; `personality` → personality (also woven into writingStyle); `first_mes` → greeting; `alternate_greetings+group_only_greetings` → altGreetings; `character_book` → startingLore (**lossy: flattened to always-on lore** — no keyword-triggered lorebook engine) (16-card-io.js:18-38). |
| **Observable output** | New card in the grid; PNG image becomes the avatar. |
| **Side effects** | Non-prompt metadata (creator, tags, version, notes) preserved on `card._import` (16-card-io.js:35-38); imported custom code is **always disabled** until the user opts in (23-card-code.js:301-313). |
| **Persisted state** | New card in `state.characterCards`. |
| **Error behavior** | Not-a-PNG / no chara/ccv3 chunk / bad ZIP / unsupported compression → thrown error surfaced to the user (16-card-io.js:80, 147, 163, 194). |
| **Retry or recovery behavior** | Re-import; README warns some cards need tweaking after import (README.md:314). |
| **Owner (layer/package)** | UI layer — js/16-card-io.js. |
| **Evidence level** | observed fact |

#### Character card export (V3 PNG)

| Field | Value |
|---|---|
| **Feature** | Export a card as a V3 PNG (V2-compatible), lorebook riding along. |
| **Trigger or input** | Export button in the editor (16-card-io.js:701-736). |
| **Defaults** | Reads live form values so unsaved edits are included; filename slugified from the name (16-card-io.js:705-730). |
| **Observable output** | PNG download with `ccv3` (V3 JSON) + `chara` (V2 JSON) tEXt chunks. |
| **Side effects** | `ragStorybook` included in the snapshot (16-card-io.js:717). |
| **Persisted state** | n/a (download). |
| **Error behavior** | Toast with the error message (16-card-io.js:732-735). |
| **Retry or recovery behavior** | Re-export. |
| **Owner (layer/package)** | UI layer — js/16-card-io.js. |
| **Evidence level** | observed fact |

#### RAG lorebook (dual retriever)

| Field | Value |
|---|---|
| **Feature** | A card's storybook is retrieved on demand: semantic matching (Retriever A, embed server) + weighted-tag matching (Retriever B), merged and ranked into context. |
| **Trigger or input** | Every context build when the card has a `ragStorybook` (08-rag.js:7-29). |
| **Defaults** | `retrievalEnabled:true`, `retrieverA:true`, `retrieverB:true`, `fireThreshold:1.0`, `warmthTurns:3`, `expansionDepth:1`, `semanticBackstop:true`, `topKA:5`, `retrievalBudgetTokens:6000`, `retrievalWindowMsgs:4` (04-state.js:71-80). |
| **Observable output** | Retrieved entities/subtrees injected as system messages; live parse readout in the editor (07-prompt.js:189-203). |
| **Side effects** | Document embeddings cached by content hash (in-memory + IndexedDB `vectors`); per-turn telemetry record appended (08-rag.js:203-221, 05-persistence.js:45-53). |
| **Persisted state** | `vectors` + `telemetry` IDB stores (local-only, never synced). |
| **Error behavior** | **Degrade-safe**: embed server down → Retriever A and semantic backstop switch off, tag-only Retriever B carries on; chat is never blocked (08-rag.js:10-13, 02-model.js:388-391). |
| **Retry or recovery behavior** | Embeddings re-attempted per turn; dimension mismatch clears the cache (08-rag.js:223-232). |
| **Owner (layer/package)** | UI layer — js/08-rag.js; embed server (llama-server `--embeddings`). |
| **Evidence level** | observed fact |

#### Per-card custom code

| Field | Value |
|---|---|
| **Feature** | Attach a small JavaScript to one character; runs only while that card is active, torn down on switch. |
| **Trigger or input** | Card editor opt-in (`customCodeEnabled`); evaluated once per activation (23-card-code.js:76-121). |
| **Defaults** | Off; imported cards always arrive disabled (23-card-code.js:30-33, 301-313). |
| **Observable output** | Hooks: `activate`, `deactivate`, `send` (may rewrite outgoing text), `reply` (may rewrite the finished reply), `context`; API: `gobbo.on`, `gobbo.store` (persistent per-card scratch), `gobbo.save`, `gobbo.thread`, `gobbo.every(n, fn)` (23-card-code.js:48, 86-121). |
| **Side effects** | **Not sandboxed** — runs with the page's full access, by design and documented (23-card-code.js:22-28, README.md:320). |
| **Persisted state** | `card.customCode/customCodeEnabled`; `state._cardCodeStore[cardId]`. |
| **Error behavior** | Every hook call wrapped; a throwing hook is disabled rather than retried; a broken card still chats normally (23-card-code.js:26-28). |
| **Retry or recovery behavior** | Switch away and back re-evaluates. |
| **Owner (layer/package)** | UI layer — js/23-card-code.js. |
| **Evidence level** | observed fact |

#### User personas

| Field | Value |
|---|---|
| **Feature** | Create profiles for yourself so the AI knows who it's talking to; switch per conversation. |
| **Trigger or input** | Persona editor in the Characters modal (17-personas.js:14-152). |
| **Defaults** | `DEFAULT_PERSONA` "Anonymous", `injectionFrequency:5` (04-state.js:145-153). |
| **Observable output** | Name/avatar/colors always apply; description injected as `[Persona: name]` on user message 1 and every Nth after; `0` = never share the description (04-state.js:142-144, 08-rag.js:679-697). |
| **Side effects** | Persona block lands last, immediately before the final user message (08-rag.js:679-682). |
| **Persisted state** | `state.personaCards`, `state.activePersonaId`. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/17-personas.js, js/08-rag.js. |
| **Evidence level** | observed fact |

#### Model selector + hot-swap

| Field | Value |
|---|---|
| **Feature** | Choose the active model from a header dropdown; switching swaps the running GGUF without restarting anything. |
| **Trigger or input** | Dropdown change (02-model.js:269-336). |
| **Defaults** | Dropdown populated from `models-list.json`; current file tracked in `_currentModelFile`; re-selecting the active model is a no-op (02-model.js:220-228, 277). |
| **Observable output** | Toast "Swapping to X…" → "Active: X"; dropdown disabled during swap; on success the UI re-fetches `active-model.json` (token limits, thinking format, hint update) (02-model.js:299-326). |
| **Side effects** | Server kills llama-server, rewrites `.llama-launch.cmd`, updates `models-list.json` active flag + `active-model.json`, spawns the new server (fileserver.ps1:1330-1371). **Known defect P1-1: the kill also takes down the embedding server, which is never restarted — RAG degrades to tag-only until the next full launch.** |
| **Persisted state** | Server-side metadata files; client `_currentModelFile`. |
| **Error behavior** | 409 swap in flight; 400 invalid filename; 404 GGUF missing/not listed; 503 hot-swap not configured; client reverts the dropdown and toasts the error; 180s client poll timeout (02-model.js:307-361, fileserver.ps1:1273-1326). |
| **Retry or recovery behavior** | Re-select; failed swap leaves the previous model's launch script intact for the monitor loop. |
| **Owner (layer/package)** | UI layer — js/02-model.js; server — fileserver.ps1 Handle-SwapModel/Handle-SwapStatus. |
| **Evidence level** | observed fact |

#### Web search (optional)

| Field | Value |
|---|---|
| **Feature** | Search toggle makes the AI look things up online (needs a free Ollama key). |
| **Trigger or input** | Toggle on + API key set; runs before context build on every manual send (10-chat.js:113-131). |
| **Defaults** | Off (`searchEnabled:false`); key empty (04-state.js:61, 193). |
| **Observable output** | Indicator "searching…" → "found N results — saved to message"; results formatted as a `[Web Search Results]` block saved on the user message and included in context/lore (11-search.js:184-190, 10-chat.js:120-124). |
| **Side effects** | Proxy health check first; request `{query, max_results:5}` with `Authorization: Bearer <key>` to the search proxy, which forwards to `https://ollama.com/api` (11-search.js:29-52). |
| **Persisted state** | `msg.searchData`; `state.settings.apiKey` (redacted from `/state` sync, 05-persistence.js:416-434). |
| **Error behavior** | No key → "search ON but no API key set"; proxy down / non-OK / bad JSON / no results → null with console detail; chat proceeds without search (11-search.js:20-86). |
| **Retry or recovery behavior** | Next send retries; Settings has a Test Connection button (11-search.js:90-182). |
| **Owner (layer/package)** | UI layer — js/11-search.js; search proxy (launch.bat:1608). |
| **Evidence level** | observed fact |

#### File attachments (drag-and-drop)

| Field | Value |
|---|---|
| **Feature** | Drag a file into the chat to attach it. |
| **Trigger or input** | Drop/click-to-attach (18-utils.js:303-320). |
| **Defaults** | Text files are embedded into the model context (`attachmentText`); images attach as reference-only chips (name recorded, not read) (18-utils.js:304-320). |
| **Observable output** | Pending-attachments tray; chips on the sent message. |
| **Side effects** | Attachments consumed once at send, then cleared (10-chat.js:64-66). |
| **Persisted state** | `msg.attachments`/`msg.attachmentText` per message/variant. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/18-utils.js, js/10-chat.js. |
| **Evidence level** | observed fact |

#### Save AI output as a file

| Field | Value |
|---|---|
| **Feature** | AI outputs ` ```file:filename ` blocks; the user gets a Save button to download them. |
| **Trigger or input** | Model emits a `file:`-tagged code block (18-utils.js:178, 530-547). |
| **Defaults** | Default card prompt instructs the model to use ` ```file:example.json ` (04-state.js:16). |
| **Observable output** | File block with Copy + Save buttons; Save downloads the content as the given filename. |
| **Side effects** | n/a |
| **Persisted state** | n/a (download). |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/18-utils.js. |
| **Evidence level** | observed fact — README claims only .txt/.json are supported (README.md:345) but the code does not restrict the extension; see Doc/Test Conflicts. |

#### Data export / import / purge

| Field | Value |
|---|---|
| **Feature** | Back up everything to a file, restore it later, or wipe it completely. |
| **Trigger or input** | Data manager modal (21-data.js:26-203). |
| **Defaults** | Export types: threads / cards / personas / full; bundles tagged `gobbonet_export: <type>`, `version: 1`, `exported: <ts>`; filenames `gobbonet-<type>-YYYY-MM-DD.json` (21-data.js:26-57). |
| **Observable output** | JSON download; import status line ("✓ Imported N…, M skipped (already exist)"). |
| **Side effects** | Threads/cards/personas imports **merge by ID** (existing IDs skipped); full backup **replaces everything** after a confirm; personas patched with defaults; legacy `userName` settings migrated into a persona (21-data.js:86-160). |
| **Persisted state** | Imported data saved; full import re-applies extensions (21-data.js:157). |
| **Error behavior** | Invalid JSON / missing `gobbonet_export` / wrong bundle type → red status message, nothing changed (21-data.js:76-84, 117-120). |
| **Retry or recovery behavior** | Re-import; file input reset so the same file can be re-imported (21-data.js:163). |
| **Owner (layer/package)** | UI layer — js/21-data.js. |
| **Evidence level** | observed fact |

#### Purge

| Field | Value |
|---|---|
| **Feature** | Delete all threads / reset cards / reset personas / full factory reset. |
| **Trigger or input** | Data manager purge buttons, each behind a confirm (21-data.js:168-203). |
| **Defaults** | Full purge resets settings, cards, personas, schedules, folders, extensions, search to defaults and closes the modal (21-data.js:184-201). |
| **Observable output** | Clean state re-rendered. |
| **Side effects** | Extensions re-applied (now empty) (21-data.js:198). |
| **Persisted state** | Reset state saved. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | None — "Cannot be undone" (21-data.js:170). |
| **Owner (layer/package)** | UI layer — js/21-data.js. |
| **Evidence level** | observed fact |

#### Extensions (internal "mod" controls)

| Field | Value |
|---|---|
| **Feature** | Inject custom stylesheets and scripts (URL or inline) to change how the app looks and works. |
| **Trigger or input** | Extensions modal; applied on boot, on save, on full import/purge (19-extensions.js:19-82, 24-boot.js:43). |
| **Defaults** | `{enabled:false, styles:[], scripts:[]}`; entries `{id, name, url, raw}`; legacy single-field format migrated on load (04-state.js:88-134). |
| **Observable output** | `<link>`/`<style>`/`<script>` elements injected with class `gobbonet-ext`; green dot in the sidebar when active; live CSS preview without saving (19-extensions.js:109-123, 92-99). |
| **Side effects** | **Not sandboxed** — scripts run with full page access (19-extensions.js:226, README.md:349); URL scripts load with `defer`; load failures only log (19-extensions.js:66). |
| **Persisted state** | `state.extensions`. |
| **Error behavior** | n/a (best-effort injection). |
| **Retry or recovery behavior** | Clear-all resets to disabled/empty (19-extensions.js:143-149). |
| **Owner (layer/package)** | UI layer — js/19-extensions.js. |
| **Evidence level** | observed fact |

#### Scheduler

| Field | Value |
|---|---|
| **Feature** | Set prompts to send themselves at specific times. |
| **Trigger or input** | Scheduler modal; checked every 30s (22-scheduler.js:11-148, 24-boot.js:75). |
| **Defaults** | Record `{id, time (HH:MM), prompt, threadId, recurring: 'once'|'daily', useSearch, lastFired}` (22-scheduler.js:94-102). |
| **Observable output** | At the due minute: switches to the target thread, injects the prompt as a user message (marked `scheduled:true`), auto-names if first message, sends to the AI (optionally with search) (22-scheduler.js:158-193). |
| **Side effects** | **Runs only while the chat tab is open** and not generating and server connected (22-scheduler.js:26, 151-152); one schedule per check cycle; one-time schedules are deleted after firing; daily guarded by `lastFired === today` (22-scheduler.js:160, 188-195). |
| **Persisted state** | `state.schedules`. |
| **Error behavior** | Missing time/prompt/thread → save silently ignored (22-scheduler.js:91). |
| **Retry or recovery behavior** | Missed minutes are skipped (no catch-up). |
| **Owner (layer/package)** | UI layer — js/22-scheduler.js. |
| **Evidence level** | observed fact |

#### Landing page / dashboard

| Field | Value |
|---|---|
| **Feature** | A home dashboard you start from each time. |
| **Trigger or input** | Every boot: `state.activeThreadId = null` before render (24-boot.js:31-35). |
| **Defaults** | Shows connection pill, scheduled tasks, active cards (13-dashboard.js:17-34). |
| **Observable output** | Dashboard with status; threads reachable from the sidebar. |
| **Side effects** | n/a |
| **Persisted state** | Active thread preserved in state for quick return but not auto-resumed (24-boot.js:33-34). |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/13-dashboard.js, js/24-boot.js. |
| **Evidence level** | observed fact |

#### Connection status indicator

| Field | Value |
|---|---|
| **Feature** | Header status dot shows whether the AI is reachable. |
| **Trigger or input** | Every 5s + on app wake (24-boot.js:68-73, 11-search.js:195-221). |
| **Defaults** | `GET /health`; `{status:'ok'}` = model loaded. |
| **Observable output** | "Connected" / "Loading model..." / "Error: HTTP n" / "No connection". |
| **Side effects** | `serverConnected` gates the scheduler (22-scheduler.js:152). |
| **Persisted state** | n/a |
| **Error behavior** | Fetch failure → "No connection". |
| **Retry or recovery behavior** | Next 5s tick. |
| **Owner (layer/package)** | UI layer — js/11-search.js. |
| **Evidence level** | observed fact |

#### Cross-device state sync and restore

| Field | Value |
|---|---|
| **Feature** | Chats mirror to the server so a phone (or a rotated LAN IP) can restore them. |
| **Trigger or input** | Every save schedules a debounced (~2s) `PUT /state`; boot runs `GET /state/info` (06-state-sync.js:78-143, 224-293). |
| **Defaults** | Local copy is authoritative; sync is best-effort; `apiKey` redacted from the pushed blob (06-state-sync.js:18-20, 05-persistence.js:416-434). |
| **Observable output** | Boot decision matrix: local empty + server data → silent auto-restore (once per tab session); server newer → prompt; server older → no-op; quota-truncation signature (server >1.2× local, not newer) → silent recovery (06-state-sync.js:200-293). |
| **Side effects** | Mid-stream snapshots are never published (transient-state guard); generation settle forces an immediate flush; pagehide sends a `sendBeacon` when settled (06-state-sync.js:56-76, 153-193). |
| **Persisted state** | `.gobbonet-state.json` server-side; `gobbonet_sync_meta` (lastKnownMtime) client-side. |
| **Error behavior** | Push failure requeues with 4s backoff; boot check failure logs and continues (06-state-sync.js:128-142, 238-244). |
| **Retry or recovery behavior** | Retry loop; restore may reload the page and rerun boot (06-state-sync.js:20-23). |
| **Owner (layer/package)** | UI layer — js/06-state-sync.js; server — fileserver.ps1 Handle-State. |
| **Evidence level** | observed fact |

#### Generation job resume (after navigation)

| Field | Value |
|---|---|
| **Feature** | Replies keep generating when you navigate away; on return they're folded in or re-attached. |
| **Trigger or input** | Boot and app-wake (`visibilitychange`/`pageshow`/`focus`/`online`) scan `thread.pendingJob` breadcrumbs (10-chat.js:936-995, 24-boot.js:129-145). |
| **Defaults** | Terminal job → silent background replay from byte 0 (byte-stable, deterministic); running → live re-attach with full generating UI; vanished (server restarted + swept) → keep partial text + honest note; unreachable → keep breadcrumb for a later retry (10-chat.js:814-826, 953-975). |
| **Observable output** | Toast "Reply finished while you were away…" / "Still generating… — re-attached". |
| **Side effects** | One resume pass at a time; wake resumes gated on `_appBooted` + 1s cooldown (10-chat.js:929-934, 24-boot.js:120-125). |
| **Persisted state** | `thread.pendingJob`, `msg.jobId`, `msg.genStartedAt`. |
| **Error behavior** | Server unreachable → breadcrumb kept, retried later (10-chat.js:953-958). |
| **Retry or recovery behavior** | Reload re-attaches; spool is the source of truth. |
| **Owner (layer/package)** | UI layer — js/10-chat.js, js/03-generation.js; server — fileserver.ps1 jobs. |
| **Evidence level** | observed fact |

#### Avatar, background, and text-color customization

| Field | Value |
|---|---|
| **Feature** | Per-card avatar (URL/upload), background, text/dialog colors; global avatar scale. |
| **Trigger or input** | Card editor; CONFIG avatar-scale slider (15-cards.js:50-63, 17-personas.js:161-191). |
| **Defaults** | `avatarScale:1` (0.7-1.6 slider); empty avatar renders the name's first letter (04-state.js:66, 07-prompt.js:206-213). |
| **Observable output** | Live preview; applied to chat, cards, dashboard. |
| **Side effects** | Cancel reverts unsaved previews (15-cards.js:28-31). |
| **Persisted state** | Card fields; `settings.avatarScale`. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/15-cards.js, js/17-personas.js. |
| **Evidence level** | observed fact |

### Surface: CLI / launcher

#### First-run setup (password, engine, model, embed)

| Field | Value |
|---|---|
| **Feature** | `launch.bat` walks a new user through password, engine download, model pick, and the retrieval-model download, then opens the browser. |
| **Trigger or input** | Double-click launch.bat / launch.exe (README.md:86-143). |
| **Defaults** | Password min 6 chars, confirm, salted SHA-256 → `.gobbonet-secret` (launch.bat:310-362); engine pinned tag `b9294`, SHA-256 verified vs GitHub API digest (launch.bat:232-244, 558-576); model menu with `[ RECOMMENDED FOR YOUR PC ]` from a hardware probe (launch.bat:749-807); embed model nomic-embed-text, CPU-only (launch.bat:278-288). |
| **Observable output** | Green-text console walkthrough; browser opens to `http://127.0.0.1:8080` (launch.bat:1826). |
| **Side effects** | Writes `active-model.json`, `models-list.json`, `hardware.json`, `.llama-launch.cmd`, `.embed-launch.cmd`; downloads to `.part` files renamed only after hash match (launch.bat:1040-1128). |
| **Persisted state** | `.gobbonet-secret`, model/engine files, metadata JSONs. |
| **Error behavior** | Password read-back verified (5 retries, AV-lock tolerant); bad file renamed `.bad`, never deleted (launch.bat:374-433); missing PowerShell → fatal (launch.bat:32-77). |
| **Retry or recovery behavior** | Re-run picks up where it left off (README.md:232); manual download links printed. |
| **Owner (layer/package)** | product shell — launch.bat. |
| **Evidence level** | observed fact |

#### Password reset

| Field | Value |
|---|---|
| **Feature** | `launch.bat reset-password` (or deleting `.gobbonet-secret`) forces a new password. |
| **Trigger or input** | CLI argument (launch.bat:144-148). |
| **Defaults** | n/a |
| **Observable output** | Setup prompt runs again. |
| **Side effects** | Deletes the secret file; README advises a reboot afterward (README.md:224-229). |
| **Persisted state** | New `.gobbonet-secret`. |
| **Error behavior** | If no password gets set, launcher refuses to start (launch.bat:150-155). |
| **Retry or recovery behavior** | Re-run. |
| **Owner (layer/package)** | product shell — launch.bat. |
| **Evidence level** | observed fact |

#### Model download menu

| Field | Value |
|---|---|
| **Feature** | Pick a model from a tiered menu sized to your hardware. |
| **Trigger or input** | No `.gguf` in `models/` at boot (launch.bat:646-1040). |
| **Defaults** | Tiers SMALL/MEDIUM/LARGE/MANUAL; recommended option pre-selected; VRAM over-budget warns and asks (README.md:106-133). |
| **Observable output** | Menu with sizes; download progress; hash verification. |
| **Side effects** | Per-choice `CTX_SIZE`/`KV_CACHE_TYPE` overrides apply **for that session only** — not persisted, so later launches/hot-swaps use header defaults (mechanical finding P6-2). |
| **Persisted state** | Downloaded GGUF; `models-list.json`. |
| **Error behavior** | Hash mismatch → download refused (launch.bat:1094-1127). |
| **Retry or recovery behavior** | Re-run; `.part` resume. |
| **Owner (layer/package)** | product shell — launch.bat + hardware-probe.ps1. |
| **Evidence level** | observed fact |

#### Monitor loop (crash supervision)

| Field | Value |
|---|---|
| **Feature** | The launcher window quietly watches the AI and restarts it if it hiccups. |
| **Trigger or input** | Every 15s: `/health` probe (launch.bat:1839-1895). |
| **Defaults** | Restart from `.llama-launch.cmd`; up to 90×2s wait; log tail printed on failure; keeps retrying. |
| **Observable output** | Console messages; window restores itself to report, then re-minimizes. |
| **Side effects** | Stands down while `.swap-in-progress` exists (launch.bat:1845-1858); **kills all `llama-server.exe` processes including the embedding server and never restarts it (P1-1)**; health probe accepts any response containing "ok" (P1-2). |
| **Persisted state** | n/a |
| **Error behavior** | 3-minute restart cap, then retry every 15s. |
| **Retry or recovery behavior** | Infinite retry loop. |
| **Owner (layer/package)** | product shell — launch.bat. |
| **Evidence level** | observed fact |

#### LAN setup and phone URL

| Field | Value |
|---|---|
| **Feature** | One-time `setup-lan.bat` (admin) opens the firewall + mDNS; the launcher prints the phone URL. |
| **Trigger or input** | Run LAN Setup once (README.md:149-163). |
| **Defaults** | Firewall rules scoped to `LocalSubnet` for ports 11434/11435/8080 + mDNS UDP 5353 (setup-lan.bat:47-100). |
| **Observable output** | `On your phone: http://<hostname>.local:8080` plus the numeric IP. |
| **Side effects** | IP-change detection vs `.last-lan-ip` warns and advises the `.local` bookmark (launch.bat:1725-1758). |
| **Persisted state** | `.last-lan-ip`. |
| **Error behavior** | First non-loopback IPv4 wins — VPN/virtual adapters can yield the wrong URL (P1-6). |
| **Retry or recovery behavior** | Re-run setup-lan.bat. |
| **Owner (layer/package)** | product shell — launch.bat, setup-lan.bat. |
| **Evidence level** | observed fact |

#### Shutdown

| Field | Value |
|---|---|
| **Feature** | Close the launcher window (or Ctrl+C) to stop everything. |
| **Trigger or input** | Window close (README.md:202-206). |
| **Defaults** | n/a |
| **Observable output** | Child processes die with the console session. |
| **Side effects** | fileserver.ps1 has no shutdown handler; job spools swept by 48h retention or client ack (fileserver.ps1:74, 610-612). |
| **Persisted state** | State already saved by the browser. |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | Next boot: stale swap lock/status removed; orphaned jobs flipped to `interrupted` (fileserver.ps1:137-160). |
| **Owner (layer/package)** | product shell — launch.bat. |
| **Evidence level** | observed fact |

### Surface: HTTP API

#### Authentication: login / logout / session

| Field | Value |
|---|---|
| **Feature** | Password-gated server; one shared password for the whole LAN surface. |
| **Trigger or input** | `POST /login` (form-encoded `password=`); `GET /logout` (fileserver.ps1:1497-1538). |
| **Defaults** | Session cookie `gobbonet_session`: HttpOnly, SameSite=Lax, Path=/, Max-Age 12h, **no Secure flag** (plain HTTP); token = 32 random bytes base64url; sessions in-memory only (fileserver.ps1:273-280, 1512-1523). |
| **Observable output** | Success → 302 to `/`; failure → 401 login page with "Wrong password."; logout → 302 to `/login` with cookie cleared. |
| **Side effects** | Every authenticated request re-validates token + client fingerprint SHA-256(IP|User-Agent) (fileserver.ps1:259-316). |
| **Persisted state** | None (in-memory hashtable; restart logs everyone out). |
| **Error behavior** | Non-HTML clients get JSON 401 `{error:'authentication required', login:'/login'}` (fileserver.ps1:1552-1560). |
| **Retry or recovery behavior** | Re-login. |
| **Owner (layer/package)** | integration adapter — fileserver.ps1. |
| **Evidence level** | observed fact |

#### /state and /state/info

| Field | Value |
|---|---|
| **Feature** | Server-side rolling backup of the client state blob. |
| **Trigger or input** | `GET /state/info` (mtime+size), `GET /state` (full body + `X-State-Mtime`), `POST/PUT /state` (JSON body) (fileserver.ps1:501-567). |
| **Defaults** | No state file → 404 `{error:'no state on server'}`. |
| **Observable output** | PUT returns `{status:'ok', mtime}`. |
| **Side effects** | Body validated as JSON before write; written BOM-less UTF-8 (fileserver.ps1:549-557). |
| **Persisted state** | `.gobbonet-state.json`. |
| **Error behavior** | Invalid JSON → 400; write failure → 500; other methods → 405. |
| **Retry or recovery behavior** | Client requeues failed pushes (06-state-sync.js:128-142). |
| **Owner (layer/package)** | integration adapter — fileserver.ps1 Handle-State. |
| **Evidence level** | observed fact |

#### /llm/jobs (detached generation relay)

| Field | Value |
|---|---|
| **Feature** | The server makes the llama-server call itself and spools raw SSE bytes, so replies survive navigation. |
| **Trigger or input** | `POST /llm/jobs` (body = exact chat/completions request, optional `?thread=`); `GET /llm/jobs/<id>?from=N[&max=M]`; `POST /llm/jobs/<id>/cancel`; `DELETE /llm/jobs/<id>` (fileserver.ps1:569-613, 768-967). |
| **Defaults** | Max 4 concurrent workers → 429 beyond; poll chunk budget 256KB raw (base64 in JSON); `max=0` = status-only peek; 30-minute upstream timeouts; cancel observed within ~250ms (fileserver.ps1:75, 689-690, 730-738, 903-910). |
| **Observable output** | POST → 202 `{id, status:'running'}`; GET → `{id, status, size, next, chunk_b64?, error?, started_at?, updated_at?}`; cancel → 200 `{status:'cancelling'}`; DELETE → 200 `{status:'deleted'}` (202+cancel-flag if still running). |
| **Side effects** | Spool files `.jobs/<id>.{sse,json,cancel}`; worker runspaces reaped on job traffic; 48h retention backstop (fileserver.ps1:69-76, 772-774). |
| **Persisted state** | Spool files (transient). |
| **Error behavior** | Terminal statuses: `done | cancelled | error | interrupted` (fileserver restart mid-job); upstream 4xx/5xx surfaced with llama-server's own body (first 400 chars); unknown job → 404. |
| **Retry or recovery behavior** | Client replays from byte 0; `interrupted`/`lost` produce honest notes (10-chat.js:960-975). |
| **Owner (layer/package)** | integration adapter — fileserver.ps1 Handle-Jobs + worker runspace. |
| **Evidence level** | observed fact |

#### /swap-model and /swap-status

| Field | Value |
|---|---|
| **Feature** | Hot-swap the active GGUF without rebooting. |
| **Trigger or input** | `POST /swap-model {"file":"<name>.gguf"}`; `GET /swap-status` (fileserver.ps1:1270-1445). |
| **Defaults** | Status phases: `idle | starting | ready | error`; readiness = llama-server `/health` 200; fail-fast on process death after 5s grace; 180s timeout. |
| **Observable output** | POST → 202 `{phase:'starting', file, name, message, started_at}`; GET → current status object. |
| **Side effects** | Lock file → kill llama-server → rewrite `.llama-launch.cmd` → update `models-list.json` + `active-model.json` → spawn via `cmd /c start /min` (fileserver.ps1:1330-1371). |
| **Persisted state** | `.swap-status.json`, `.swap-in-progress`, launch script, metadata files. |
| **Error behavior** | 503 not configured; 405 wrong method; 409 swap in flight; 400 bad JSON / missing file / invalid filename (no separators, no `..`, must end `.gguf`); 404 GGUF missing or not in models-list.json; 500 dispatch failure. |
| **Retry or recovery behavior** | Lock cleaned on ready/error/boot; monitor loop stands down while the lock exists. |
| **Owner (layer/package)** | integration adapter — fileserver.ps1 Handle-SwapModel/Handle-SwapStatus. |
| **Evidence level** | observed fact |

#### Reverse proxies (/llm, /search, /embed)

| Field | Value |
|---|---|
| **Feature** | Same-origin passthrough to llama-server (11434), search proxy (11435), embed server (11436). |
| **Trigger or input** | Any method on `/llm/*`, `/search/*`, `/embed/*` (fileserver.ps1:1584-1596). |
| **Defaults** | Streaming, no pre-buffer; 10-minute read timeouts; headers forwarded (Host/Content-Length/Connection etc. excluded); for `/llm` the client Authorization is replaced with the server-side llama-server key when set (fileserver.ps1:389-497). |
| **Observable output** | Upstream status/headers/body passed through; SSE chunks flush as they arrive. |
| **Side effects** | `/search` forwards the client's `Authorization` **verbatim** to the search proxy (fileserver.ps1:1587-1589, 423-436). |
| **Persisted state** | n/a |
| **Error behavior** | Upstream unreachable → 502 `{error:'upstream unreachable', detail}`; embed down → 502 and the client degrades to tag-only RAG. |
| **Retry or recovery behavior** | Client-side retries per feature. |
| **Owner (layer/package)** | integration adapter — fileserver.ps1 Invoke-Proxy. |
| **Evidence level** | observed fact |

#### Static file serving

| Field | Value |
|---|---|
| **Feature** | Serves chat.html, css/, js/, JSON metadata, and any other non-dotfile under the project root. |
| **Trigger or input** | Any authenticated GET not matching a route (fileserver.ps1:1597-1608). |
| **Defaults** | `/` → chat.html; MIME map for common types, else `application/octet-stream` (fileserver.ps1:171-196, 365). |
| **Observable output** | File bytes. |
| **Side effects** | Traversal (`..`) and dot-prefixed paths refused (fileserver.ps1:363-385). |
| **Persisted state** | n/a |
| **Error behavior** | Unsafe/missing path → 404. |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | integration adapter — fileserver.ps1 Resolve-StaticPath. |
| **Evidence level** | observed fact — no size cap and no extension allowlist (mechanical P2-1, mech-CF2b). |

### Surface: Storage / export formats

#### Export bundles

| Field | Value |
|---|---|
| **Feature** | JSON downloads for threads, cards, personas, or a full backup. |
| **Trigger or input** | Data manager export buttons (21-data.js:26-57). |
| **Defaults** | Envelope `{gobbonet_export: 'threads'|'cards'|'personas'|'full', version: 1, exported: <ms>, …payload}`; full backup carries threads, activeThreadId, settings, characterCards, activeCardId, personaCards, activePersonaId, schedules, folders, extensions, searchEnabled, macros (21-data.js:38-55). |
| **Observable output** | Pretty-printed JSON download, `gobbonet-<type>-YYYY-MM-DD.json`. |
| **Side effects** | n/a |
| **Persisted state** | n/a (download). |
| **Error behavior** | n/a |
| **Retry or recovery behavior** | n/a |
| **Owner (layer/package)** | UI layer — js/21-data.js. |
| **Evidence level** | observed fact |

#### Import semantics

| Field | Value |
|---|---|
| **Feature** | Restore from export bundles. |
| **Trigger or input** | Data manager import buttons (21-data.js:59-166). |
| **Defaults** | Threads/cards/personas merge by ID (existing skipped, counts reported); personas patched with `DEFAULT_PERSONA`; full backup replaces everything after confirm; pre-persona backups migrate `settings.userName` into a persona (21-data.js:86-160). |
| **Observable output** | Status line with imported/skipped counts. |
| **Side effects** | Full import re-applies extensions (21-data.js:157). |
| **Persisted state** | Merged/replaced state saved. |
| **Error behavior** | Invalid JSON / not a GobboNet export / wrong bundle type → error status, nothing changed. |
| **Retry or recovery behavior** | Re-import. |
| **Owner (layer/package)** | UI layer — js/21-data.js. |
| **Evidence level** | observed fact |

#### Character card carriers

| Field | Value |
|---|---|
| **Feature** | V1/V2/V3 cards in three carriers, parsed locally (no network, no libraries). |
| **Trigger or input** | Import/export (16-card-io.js:1-15). |
| **Defaults** | `.json` (V1 flat or V2/V3 under `.data`); `.png` (tEXt/zTXt/iTXt chunk keyed `ccv3` preferred, `chara` fallback, base64 UTF-8); `.charx` (ZIP with card.json + assets); export writes both `ccv3` and `chara` chunks (16-card-io.js:9-15, 724-727). |
| **Observable output** | Card object mapped onto the app's card model. |
| **Side effects** | Lorebook flattened to always-on lore (lossy, documented); metadata preserved on `_import` (16-card-io.js:32-38). |
| **Persisted state** | Imported card in state. |
| **Error behavior** | Malformed carriers throw with specific messages. |
| **Retry or recovery behavior** | Re-import. |
| **Owner (layer/package)** | UI layer — js/16-card-io.js. |
| **Evidence level** | observed fact |

#### State blob and redaction

| Field | Value |
|---|---|
| **Feature** | The single persistable state shape used by IndexedDB, localStorage mirror, and `/state`. |
| **Trigger or input** | `buildStateBlob()` on every save (05-persistence.js:470-490). |
| **Defaults** | Blob: threads (cleaned of runtime fields `_reasoningDone`/`_parseState`/`_smartLimitAt`), threadOrder, activeThreadId, settings, characterCards, activeCardId, personaCards, activePersonaId, schedules, sidebarOpen, searchEnabled, folders, extensions, macros (05-persistence.js:454-490). |
| **Observable output** | JSON. |
| **Side effects** | `/state` sync uses `redactedSyncJson` which **deletes `settings.apiKey`** before push (05-persistence.js:416-434). |
| **Persisted state** | IndexedDB `gobbonet-state` v2 (meta/threads/vectors/telemetry), localStorage `gobbonet_chat_state`, `.gobbonet-state.json`. |
| **Error behavior** | Blob build failure → `'{}'` pushed, never garbage (05-persistence.js:423-428). |
| **Retry or recovery behavior** | Quota errors → server backup recovery path (05-persistence.js:436-449). |
| **Owner (layer/package)** | persistence layer — js/05-persistence.js. |
| **Evidence level** | observed fact |

---

## High-Value Behaviors

- **Cancellation and abort handling.** Three layers: user Stop (job cancel flag + AbortController), CoT watchdog (same path, distinct note), smart-limit self-abort (keeps auto-continue chains alive). Cancel lands within ~250ms even mid-silence (fileserver.ps1:730-738). Partial text is always kept; aborts append honest notes (03-generation.js:501-516).
- **Streaming and partial output.** Two transports feed the same parser pipeline: detached job polling (base64 chunks, byte-stable replay) and legacy direct SSE. Thinking-format parsers split reasoning from content; family stop strings cut runaway turn delimiters (06-state-sync.js:576-580). Smart auto-scroll pins to bottom unless the user scrolled up (04-state.js:206-215).
- **Queueing or follow-up behavior.** One generation at a time end-to-end (`isGenerating`, llama-server `--parallel 1`); server caps 4 concurrent jobs with 429 (fileserver.ps1:789-791); auto-continue chains queue the next send 20s after settle; scheduler fires at most one schedule per 30s check.
- **Compaction and summarization.** Token-driven (never message-count-driven): archive oldest until 65% of budget or the 22% trailing reserve; fielded REWRITE prompt (never append); 2400-char head-trim; failure keeps prior lore and records why (07-prompt.js:287, 08-rag.js:518-531).
- **Persistence and resume flows.** Every mutation saves; debounced server push with transient-state guard; force-flush on settle; sendBeacon on pagehide; boot conflict matrix; job breadcrumbs with deterministic replay; quota-truncation recovery (06-state-sync.js:200-293).
- **Tool execution and validation.** Card-code hooks (activate/deactivate/send/reply/context) are wrapped so a throwing hook is disabled, never fatal; imported card code is always disabled until opted in; extensions are unsandboxed by design; macro triggers validated against a reserved-name set (23-card-code.js:26-33, 20-macros.js:58-67).

## Security and Authorization

- **Authentication method.** Single shared password → salted SHA-256 (`SHA256(salt + password)`, lowercase hex) stored in `.gobbonet-secret`; plaintext exists only inside the setup process and the instant a login request is checked (launch.bat:310-362, fileserver.ps1:90-116). Login compares with a constant-time compare (fileserver.ps1:244-257).
- **Session security.** 32-byte random token in an HttpOnly, SameSite=Lax cookie, 12h Max-Age, **no Secure flag** (plain-HTTP LAN by design); sessions in-memory only (restart logs everyone out); each request re-validates the token against a client fingerprint SHA-256(source IP + User-Agent) — a coarse anti-replay bar, explicitly not a strong identity (fileserver.ps1:118-127, 259-316).
- **Authorization model.** Binary: unauthenticated routes are `/login`, `/logout`, `OPTIONS`, `/favicon.ico`; everything else (including all proxies and static files) requires a valid session. No roles, no per-user accounts (fileserver.ps1:1492-1561).
- **Trust boundaries.** llama-server and the search proxy bind to loopback only; the fileserver is the sole LAN-facing process (launch.bat:137-140, 1591-1597). **Untrusted-by-design inputs:** per-card custom code and extensions run unsandboxed with full page access (23-card-code.js:22-28, README.md:320, 349); imported card code is always disabled until the user opts in (23-card-code.js:301-313). **Known gaps routed to defect-scan-semantic (arch-CF5, mech-CF2):** plain-HTTP transport; no request-body size caps on `/state` and `/llm/jobs`; static serving exposes every non-dotfile under the project root (including `models/*.gguf`) to authenticated clients; `webSearch` logs the API key prefix to the console (11-search.js:26); **no rate limiting or lockout on `/login` POST** (observed absence, fileserver.ps1:1497-1531 — routed as contracts-CF3).
- **Secret management.** Password: hash only, never in env/disk as plaintext; passed to fileserver.ps1 as `GEMMA_ACCESS_SECRET` (launch.bat:1651-1667). Ollama API key: stored in browser state, sent as `Authorization: Bearer` to the search proxy, forwarded verbatim to ollama.com; **redacted from `/state` sync** (05-persistence.js:416-434). Optional llama-server `--api-key` is injected server-side by the proxy so the browser never sees it (fileserver.ps1:438-445).
- **CORS/CSP.** `Access-Control-Allow-Origin: *` on all responses (fileserver.ps1:198-206); no CSP headers observed. `portability hazard`: the permissive CORS + cookie auth combination is a LAN-scoped design choice.
- **Search privacy claim vs implementation.** README.md:342 claims "identifying metadata and telemetry are stripped from your searches." The code strips nothing: `privacyFetch` is a bare `fetch` passthrough (02-model.js:398-400), the search proxy forwards method/body/`Authorization` verbatim to `https://ollama.com/api` (decoded launch.bat:1608), and the fileserver `/search` proxy forwards the client's Authorization header unchanged (fileserver.ps1:423-436). **Doc/code conflict — recorded, not resolved** (assessment routed to defect-scan-semantic via arch-CF5).

## Configuration Model

Full matrix in `findings/config-model/config-model.md` (2026-08-18 contracts section appended). Summary of the contract-relevant flow:

- **Sources and precedence.** (1) launch.bat header variables (SERVER_PORT, CTX_SIZE, GPU_LAYERS, KV_CACHE_TYPE, MODEL_*, LLAMA_PIN_TAG/SHA256, EMBED_*, paths — launch.bat:112-290); (2) per-model overrides chosen in the download menu (session-only, not persisted — P6-2); (3) identify-model.ps1 emitted `set` statements (GGUF ground truth) override the model metadata (launch.bat:710-744); (4) `GEMMA_*` env handoff to fileserver.ps1 (convention C02; launch.bat:1651-1667, fileserver.ps1:42-67); (5) browser-side `DEFAULT_SETTINGS` (04-state.js:57-81) and per-card fields (04-state.js:12-56), persisted in browser state and editable in the UI. The browser `tokenLimit` and the server `CTX_SIZE` are separate knobs: tokenLimit budgets the prompt (90% used, 10% + response reserve held for output), CTX_SIZE is the physical server context.
- **Config file format and location.** No config file for the browser side — settings live in IndexedDB/localStorage state. The launcher's config is the batch header block; the password file is `.gobbonet-secret` (`salt:hash`, one line, ASCII, no BOM).
- **Feature flags.** `EMBED_ENABLE` (RAG semantic side), `MODEL_USE_JINJA`/`MODEL_CHAT_TEMPLATE` (template selection), `LLAMA_PIN_TAG`/`LLAMA_PIN_SHA256` (download pinning), browser-side `retrievalEnabled`/`retrieverA`/`retrieverB`, `cotTimeoutEnabled`, `smartLimitEnabled`, `searchEnabled`, `extensions.enabled`, per-card `customCodeEnabled`/`loreEnabled`/`altGreetingsEnabled`/`carouselEnabled`.
- **Config validation and error handling.** Password file format verified at boot (batch check deliberately looser than the PowerShell consumer — P6-3); fileserver refuses to start without a valid `GEMMA_ACCESS_SECRET` (fileserver.ps1:103-107); `/state` bodies JSON-validated before write; `/swap-model` filenames sanity-checked; smart-limit clamped 25-8192 on save (15-cards.js:41). **Known quirk (P1-5):** `loadActiveModel` overwrites `tokenLimit` whenever it equals the default 24576 — a user who deliberately set 24576 gets it silently replaced with the model's `defaultCtx` (02-model.js:42-47).
- **Vestigial setting (contracts-CF1):** the CONFIG UI still exposes "Reminder every N msgs" (`reminderFrequency`, chat.html:165-166) but no code path consumes it since personality became a persistent block (08-rag.js:912). Routed to defect-scan-semantic.

## Doc/Test Conflicts

| # | Doc claim | Code reality | Disposition |
|---|---|---|---|
| 1 | README.md:342: "identifying metadata and telemetry are stripped from your searches." | `privacyFetch` is a bare passthrough (02-model.js:398-400); the search proxy forwards body + `Authorization` verbatim to ollama.com (decoded launch.bat:1608); fileserver `/search` proxy forwards the Authorization header unchanged (fileserver.ps1:423-436). | Recorded here; security assessment already routed to defect-scan-semantic (arch-CF5). |
| 2 | README.md:264-265: logit bias / banned words is "non-functional rather than just hit-or-miss." | The full client path is wired: `/tokenize` → `logit_bias` map → merged into the request body (06-state-sync.js:725-793, 10-chat.js:161-166). | Recorded here; root cause open question `q-logit-bias-root-cause`; request-shape check routed to defect-scan-semantic (mech-CF3). |
| 3 | README.md:317: "Lorebook + RAG lorebook work together to auto-update new information from extended conversations." | Compression writes only `thread.lore` (the running summary); card lorebooks (`startingLore`, `ragStorybook`) are never auto-updated by any code path (07-prompt.js:262-268, 09-threads.js:172-175). | Recorded here; assessment routed to defect-scan-semantic (contracts-CF2); maintainer ruling post-pipeline (post-lorebook-claim-ruling). |
| 4 | README.md:345: "Save AI output as a `.txt` or `.json` file. (Other file types are intentionally left out…)" | `downloadFile` downloads whatever filename the model wrote in a ` ```file:` block — no extension restriction exists (18-utils.js:534-547). | Recorded here; cosmetic (the restriction is prompt-level, not code-level). |
| 5 | chat.html:165-166: "Reminder every N msgs" setting. | `reminderFrequency` is saved (15-cards.js:35) but never read anywhere; personality is now a persistent block (08-rag.js:912, 13-dashboard.js:711). | Recorded here; routed to defect-scan-semantic (contracts-CF1). |
| 6 | README.md:299/298 present auto-stop and smart cutoff as features. | Both exist but ship **disabled by default** (`cotTimeoutEnabled:false`, `smartLimitEnabled:false`, 04-state.js:62-64). | Recorded here; default-state nuance, not a bug. |
| 7 | 07-prompt.js:260 comment: "Keeps last 40 messages verbatim, everything else → lore." | The implementation is token-driven; "Message counts are never used as thresholds" (08-rag.js:518-531). | Recorded here; stale in-code comment. |
| 8 | 16-card-io.js:25 comment: "personality → personality (periodic reminder)". | Personality is injected persistently on every turn, not on a cadence (08-rag.js:667-670). | Recorded here; stale in-code comment. |
| 9 | README.md:308: "older parts of a long chat are automatically summarized." | Matches code (08-rag.js:722-763) — no conflict; listed for completeness. | Consistent. |

## Black-Box Acceptance List

| # | Scenario | Precondition | Action | Expected Outcome |
|---|----------|--------------|--------|------------------|
| 1 | First-run password | No `.gobbonet-secret` | Run launcher; enter 5-char password | Rejected ("at least 6 characters"); re-prompt. |
| 2 | Login | Server running, password set | Open `http://<host>:8080/` in a browser | Login page; correct password → 302 to chat; wrong password → 401 page with "Wrong password." |
| 3 | Session expiry | Valid session | Wait 12h (or restart fileserver) | Next request → 401/login; re-login works. |
| 4 | Cookie replay from another client | Session cookie copied to a different browser/device | Replay the cookie | Rejected (client fingerprint mismatch). |
| 5 | Streaming | Model loaded, thread open | Send a message | Reply appears incrementally; token counter updates; thread floats to top. |
| 6 | Stop | Generation in flight | Click Stop | Partial text kept with a stop note; input re-enabled; auto-continue chain (if any) cancelled. |
| 7 | Reroll variants | A completed assistant reply | Reroll twice, then flip ◀ ▶ | Three variants flippable; flipping never regenerates; each variant's text/timer preserved. |
| 8 | Edit preserves branches | A user message with downstream replies | Edit the user message | Old wording + its AI replies restorable via ◀ ▶; new branch regenerated from the edit. |
| 9 | Branch | Any message | Click Branch | New thread `⑂ …` with shared history up to the branch point; original untouched. |
| 10 | Lore compression | Long thread, small tokenLimit | Keep chatting past the budget | "compressing…" indicator; older messages dimmed; summary appears in the lore inspector; chat never blocks. |
| 11 | Compression failure | Kill llama-server mid-compression | Send a message | Previous lore retained; failure reason recorded in the lore inspector. |
| 12 | Auto-continue | Type `{{auto_continue_3}}` | Send | 3 total posts, 20s apart; indicator shows progress; CANCEL stops the chain. |
| 13 | Scheduler | Create a one-time schedule 1 minute ahead; keep tab open | Wait | Prompt injected into the target thread and sent; schedule removed from the list. |
| 14 | Scheduler while closed | Schedule due; tab closed | Wait past the time, reopen | Nothing fired (schedules run only while the chat is open). |
| 15 | Hot-swap | Two models in `models/` | Pick the other in the dropdown | Toast "Swapping…" → "Active: …"; dropdown disabled during swap; new model answers. |
| 16 | Hot-swap failure | Pick a model whose GGUF was deleted | Swap | 404 surfaced in a toast; dropdown reverts to the previous model. |
| 17 | Export/import threads | Two devices or two origins | Export threads on A; import on B | Threads with new IDs added; existing IDs skipped with counts reported. |
| 18 | Full backup restore | A full backup file | Import as full backup, confirm | All state replaced; extensions re-applied; settings from the backup active. |
| 19 | Purge | Data present | Purge all, confirm | Factory defaults; data manager modal closes. |
| 20 | Card import | A V3 `.png` card with embedded code | Import | Card appears; lorebook flattened to always-on lore; custom code present but **disabled**. |
| 21 | Card export | A card with a storybook | Export | PNG downloads; contains `ccv3` + `chara` chunks; re-import round-trips the storybook. |
| 22 | Extensions | Add an inline script that changes the Send button text; enable | Save | Script runs on save and on every boot; disabling removes it. |
| 23 | Card code teardown | Card A with code active | Switch to card B | A's hooks discarded; B's code (if any) applied; switching back re-evaluates A. |
| 24 | Web search | API key set, toggle on | Send a message | "searching…" then "found N results"; results block saved on the user message and included in context. |
| 25 | Web search without key | Toggle on, no key | Send | "search ON but no API key set"; chat proceeds without search. |
| 26 | File save | Model outputs a ` ```file:notes.txt ` block | Click Save | File downloads with that name and content. |
| 27 | Job resume | Send a message, immediately navigate away, return | Reopen the app | Reply folded in silently (or re-attached live if still running); toast reports it. |
| 28 | Server restart mid-job | Generation in flight; restart fileserver | Reload the client | Job status `interrupted`; partial text kept with an honest note. |
| 29 | State restore | New origin (cleared browser data), server has backup | Open the app | Local empty → silent auto-restore from `/state`; chats reappear. |
| 30 | State conflict | Two devices edited; server newer than local | Open the app | Prompt asking whether to restore; no silent clobber. |
| 31 | RAG degrade | Embed server down | Chat with a card that has a storybook | Tag-only retrieval still works; chat never blocked. |
| 32 | Banned words | Card with banned phrases | Send | Request body contains a `logit_bias` map — but per README.md:264-265 the words are NOT reliably suppressed (known bug). |

## Coverage and limits

- **Inspected scope:** README.md (full, feature list 286-357 as primary contract source); chat.html (modals, settings UI, search toggle, lore inspector); js/01-config.js (IS_SERVED/LLAMA_URL), 02-model.js (full), 03-generation.js (1-120, 330-560, 1087), 04-state.js (full), 05-persistence.js (1-80, 410-490), 06-state-sync.js (1-300, 495-580, 700-819), 07-prompt.js (full), 08-rag.js (1-260, 368, 614-961), 09-threads.js (full), 10-chat.js (full), 11-search.js (full), 12-render.js (1-41, 61-192, 277, 348), 13-dashboard.js (17-34, 456-457, 522, 695-724), 15-cards.js (1-120, 218-279), 16-card-io.js (1-200, 695-737), 17-personas.js (function map, 193-242), 18-utils.js (178, 303-320, 530-548), 19-extensions.js (full), 20-macros.js (full), 21-data.js (full), 22-scheduler.js (full), 23-card-code.js (1-121, 295-313), 24-boot.js (full); fileserver.ps1 (1-400, 401-497, 500-567, 569-967, 969-1070, 1270-1445, 1447-1618); launch.bat (1-300, 300-500, 1591-1668, 1687-1758, 1839-1900); setup-lan.bat (via architecture notes); default-characters.json (full); decoded search-proxy command (launch.bat:1608).
- **Skipped scope:** hardware-probe.ps1 detection layers (201-1961); identify-model.ps1 family tables (62-477); css/* bodies; js/03-generation.js thinking-format parser internals (560-1086); js/05-persistence.js migration bodies (81-410); js/06-state-sync.js restore/conflict-prompt bodies (301-495); js/08-rag.js retriever scoring internals (261-613); js/12-render.js/13-dashboard.js/14-scroll.js render internals; js/16-card-io.js V2/V3 mapping internals (201-694); js/17-personas.js editor bodies; js/18-utils.js utility bodies; launch.bat download-menu bodies (500-1590); fileserver.ps1 Build-LaunchScript tail (1070-1270). These are rendering/formatting details or already covered by architecture/mechanical phases; wire-format extraction is protocols-phase territory (arch-CF1).
- **Evidence basis:** source inspection only. No runtime verification possible (Windows-only), no tests in repo, no CI, no upstream findings beyond the README's own known-bugs section.
- **Known blind spots:** (1) exact Ollama `web_search` request/response schema (q-ollama-api-version); (2) root cause of the logit-bias breakage (q-logit-bias-root-cause); (3) Tekken patch completeness (q-tekken-patch-completeness); (4) installer binaries and REFACTOR-PLAN.md remain absent (q-installer-packaging, q-refactor-plan); (5) behavior under multiple concurrent LAN clients is unmeasured (q-accept-loop-scale); (6) the search proxy's upstream behavior is only visible through the encoded command.
- **Coverage disposition:** COMPLETE — every README feature (README.md:286-357) has a contract with trigger/defaults/output/side effects/persisted state/error/recovery and an owner; arch-CF2 is closed by this document.

## Open Questions

| ID | Kind | Description | Deferred Reason |
|---|---|---|---|
| — | — | No new open questions from this phase. Existing questions (q-installer-packaging, q-refactor-plan, q-font-shipping, q-accept-loop-scale, q-ollama-api-version, q-logit-bias-root-cause, q-tekken-patch-completeness) were re-checked against contracts-phase reading and none became answerable from source. | — |

## Carry-Forward

| ID | Target Phase | Description | Deferred Reason |
|---|---|---|---|
| contracts-CF1 | defect-scan-semantic | The CONFIG UI exposes "Reminder every N msgs" (`reminderFrequency`, chat.html:165-166, 04-state.js:59) but no code path consumes it since personality became a persistent block (08-rag.js:912, 13-dashboard.js:711). Assess as a UI-contract violation under pass 5. | Contract-drift assessment is pass 5 of the semantic scan; the contracts phase records behavior, it doesn't rule on defects. |
| contracts-CF2 | defect-scan-semantic | README.md:317 claims "Lorebook + RAG lorebook work together to auto-update new information from extended conversations," but compression writes only `thread.lore`; card lorebooks are never auto-updated (07-prompt.js:262-268, 09-threads.js:172-175). Assess as a doc/behavior drift under pass 5. | Same rubric as contracts-CF1; final resolution (which side is right) may need the maintainer — tracked post-pipeline as post-lorebook-claim-ruling. |
| contracts-CF3 | defect-scan-semantic | No rate limiting or lockout on `POST /login` (fileserver.ps1:1497-1531): an on-LAN attacker can brute-force the shared password with no backoff. Assess under pass 4 (security and trust). | Security posture assessment is pass 4 of the semantic scan; folds into arch-CF5's security item. |

---

## Validation

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | User-facing surfaces are split by surface type. | PASS | §Surfaces Covered (table) + §Feature Contracts split into Web UI (24 contracts), CLI/launcher (6), HTTP API (6), Storage/export formats (4). |
| 2 | Feature contracts record trigger, defaults, outputs, side effects, persisted state, error behavior, and recovery behavior. | PASS | Every contract table carries all eight fields (Feature, Trigger or input, Defaults, Observable output, Side effects, Persisted state, Error behavior, Retry or recovery behavior) plus Owner and Evidence level. |
| 3 | Security and authorization model is documented (if applicable). | PASS | §Security and Authorization: auth method, session security, authorization model, trust boundaries, secret management, CORS, and the search-privacy doc/code conflict. |
| 4 | Contract ownership is mapped back to a layer or package. | PASS | Every contract table has an Owner (layer/package) row; §Surfaces Covered maps surfaces to owners. |
| 5 | A black-box acceptance list is included. | PASS | §Black-Box Acceptance List: 32 scenario rows with preconditions, actions, and expected outcomes. |
| 6 | Findings are marked with evidence levels. | PASS | Every contract carries an Evidence level row (`observed fact` / `strong inference` / `portability hazard` / `open question`) with file:line citations; conflicts and hazards are labeled. |
| 7 | Coverage and limits name inspected scope, skipped scope, evidence basis, and blind spots. | PASS | §Coverage and limits lists all four plus disposition (COMPLETE). |

**Validated by:** contracts phase, delegated subagent session (2026-08-18)
**Overall:** PASS
