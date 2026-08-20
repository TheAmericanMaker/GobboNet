# Runtime test result: q-logit-bias-root-cause

Executes `TEST-PLAN-logit-bias.md`. **The hypothesis is refuted, and inverted.**
The proposed fix would have broken a working feature.

## Environment

| | |
|---|---|
| Engine | `llama-b9294-bin-win-vulkan-x64.zip`, the pinned tag (`launch.bat:352`) |
| Engine SHA-256 | `1aff5b81…9f43d44`, matched GitHub's API digest |
| Model | `Qwen2.5-0.5B-Instruct-Q4_K_M.gguf` (bartowski), SHA-256 matched HF LFS pointer |
| Server | `llama-server.exe --host 127.0.0.1 --port 11434 -c 2048 -t 4 -ngl 0` |
| Sampling | `temperature: 0`, `seed: 1`, 3 runs per cell — every cell was deterministic |
| Host | i7-1165G7, CPU-only inference |

Note: the audit records the engine zip as ~300 MB (`build-and-deploy.md:20`). It is **32.8 MB**.

## Result: the shape table in the plan is backwards

Banned phrase `yellow`; GobboNet's own 8-variant expansion yields 6 canonical ids
`[13753, 25462, 27869, 47699, 81276, 97029]` at strength `-20` (the real default,
`js/04-state.js:88` — the plan's example showed `-5`).

All against `/v1/chat/completions`, 3 deterministic runs each:

| `logit_bias` shape | Output | Verdict |
|---|---|---|
| *(absent — baseline)* | `A ripe banana is a bright yellow color.` | — |
| `{"13753": -20}` — **map, what GobboNet sends** | `…a bright, vibrant orange color.` | **suppressed ✓** |
| `[{"id":13753,"bias":-20}]` — **the proposed fix** | `A ripe banana is a bright yellow color.` | **byte-identical to baseline — silently ignored** |
| `[[13753,-20]]` — pair array | `…a bright, vibrant orange color.` | suppressed ✓ |

Confirmed identical under `stream: true`, which is what the client actually sends
(`js/10-chat.js:166`). No HTTP error and no parse complaint in the server console for
the ignored form — status 200, silently dropped.

**The client's map form is correct for this endpoint.** OpenAI's own `logit_bias` is a
map of token id to bias, and llama.cpp's OAI-compat layer follows it. The one shape
that does *not* work at b9294 is precisely the `[{id, bias}]` form the plan proposed.

### Do not apply the proposed fix

```js
// Would convert a working map into the ONE shape b9294 ignores:
logit_bias: Object.entries(logitBias).map(([id, bias]) => ({ id: Number(id), bias }))
```

Two further notes if anyone revisits this: there are **two** call sites, not one —
`js/10-chat.js:166` (send) and `js/10-chat.js:779` (regenerate) — so any reshape belongs
inside `buildLogitBias`, not at "the call site". And the transport is not implicated:
`POST /llm/jobs` hands the body to its worker as a byte-exact string
(`fileserver.ps1:1046`), never round-tripping it through `ConvertTo-Json`.
Field wiring is clean too (`card-banned-phrases` → `card.bannedPhrases` → `buildLogitBias`).

## What the README symptom actually is

The plan read the README as "fully non-functional", which motivated the shape hypothesis.
The README (`README.md:265`) actually says the ban "won't **reliably** keep it out of
replies" and advises *treating* it as non-functional. That is a different claim, and it is
the ceiling **already documented in the code** at `js/06-state-sync.js:718-721`:
`logit_bias` suppresses canonical token ids only; the model can re-spell the surface
string from other tokens.

Reproduced. Ban active, prompt pushing hard for the word:

```
prompt : "Repeat this word exactly ten times, space separated: yellow"
output : "yell ow, yell ow, yell ow, yell ow, yell ow, …"

literal "yellow" present    : False
normalized "yellow" present : True     <- what the user reads

tokens emitted: id=88 'y'  id=613 'ell'  id=15570 ' ow'  id=64313 ' yell'
ban set       : [13753, 25462, 27869, 47699, 81276, 97029]
overlap       : NONE
```

Zero overlap. The bias was applied faithfully and the model routed around it. The
user-visible failure is not a dropped parameter — it is a working parameter with a
tokenizer-level ceiling, and the degraded output (`yell ow`) reads as *more* broken
than no ban at all.

## Follow-up tests (1-3), same engine and model

Three questions the first pass left open. All at `temperature: 0`, `seed: 1`; determinism
was established in the first pass, so one run per cell.

### 1. Ban-set size and strength — the collapse is real, but only under contention

A 4-phrase ban set (`suddenly / chuckle / nodded / smirked`, GobboNet's own UI placeholder,
39 canonical ids) caused **no** degradation on ordinary prompts at -5, -10 or -20: every
cell was byte-identical to the no-ban control, because greedy decoding never reached for a
banned token. The ban was simply inert.

Degradation appears only when the prompt **contends** with a banned token. Same prompt, ban
off vs on, measured as distinct-word ratio and the max repeat count of any 4-word shingle:

```
ban OFF      chars=207  distinct=0.80  rep4=1   "...the word "yellow letter by letter": **b-l-u-e**..."
ban ON (-20) chars=183  distinct=0.44  rep4=6   "...the word "blue" ... - b-l-u-e - l-u-e - u-l-e - e-l-e - l-e - e"
```

Strength sweep on that contended prompt shows a cliff, not a gradient:

| strength | suppresses | quality |
|---|---|---|
| off, -1, -2, -3 | no | intact (0.80 / rep4=1) |
| -5 | no | intact (0.83 / rep4=1) |
| -10, -20, -50, -100 | **yes** | **collapsed (0.44 / rep4=6)** |

Identical output from -20 through -100 — the bias saturates. There is no value that both
suppresses and preserves the prose. **The strength knob cannot fix this**, so GobboNet's
-20 default is not the defect and retuning it buys nothing. The collapse is structural,
which is further reason the fix has to be a string-level guard.

### 2. Sub-token expansion — refuted, and counterproductive

The first pass suggested expanding the ban set with sub-token splits. Tested and **withdrawn.**
Expanding `yellow` from 6 to 43 ids did not close the decomposition route, it only changed
which route the model took — and made the leak *cleaner*:

| ban set | output | normalized leak |
|---|---|---|
| none | `yellow yellow yellow…` | yes |
| canonical, 6 ids | `yell ow, yell ow…` | yes |
| expanded, 43 ids | `.yellow.yellow.yellow…` | yes — **word fully intact** |

Collateral damage was nil (byte-identical to control on an unrelated prompt), but the
mitigation makes the banned word *more* legible, not less. Do not ship it.

### 3. Version scope — the shape behavior is not version-specific

Repeated the shape matrix on **b10509**, the current release at time of test and 1,215
builds past the pin. Same tokenizer ids, and identical results: map suppresses,
`[{id,bias}]` is silently ignored (byte-identical to baseline, HTTP 200), pairs suppress.
So the "do not apply the proposed fix" conclusion is absolute rather than pinned-build
specific, and this behavior is not a blocker for bumping `LLAMA_PIN_TAG`.

## Disposition

- `q-logit-bias-root-cause`: **closed, hypothesis refuted.** Not a payload-shape defect,
  on either the pinned build or current latest.
- The P1-3 / Pass-5-#2 finding should be rewritten: the defect is the absence of a
  surface-string guard, not a malformed request.
- Real fix directions remain the two the code comment already names — a GBNF grammar, or a
  streaming post-filter on the decoded text. Both are string-level; neither is a one-liner.
  Follow-up test 1 adds a reason to prefer them: the failure is structural, not tunable.
- **Withdrawn:** the sub-token-expansion mitigation floated in the first pass. Follow-up
  test 2 shows it leaves the word fully intact rather than mangled — worse than doing
  nothing.
- Worth filing as its own defect: banning a word the character would naturally use often
  degrades the prose (distinct-word ratio 0.80 -> 0.44) whenever the model actually contends
  with the ban. That is a second, separable bug from the leak itself.
- **Scope caveat, and it bears on the item above.** Every generation in this document came
  from one model, Qwen2.5-0.5B-Instruct-Q4_K_M. The shape findings are model-independent —
  that is server-side parameter parsing — but the decomposition ceiling is **tokenizer-
  specific**, and a 0.5B model degenerates far more readily than the 7B-12B models users
  actually run. So the contention-collapse defect is demonstrated on the model most likely
  to exaggerate it, and should be re-measured at realistic model size before filing. Note
  that `README.md`'s other known bug is also tokenizer-related (Tekken), which is reason to
  assume this behavior varies more across tokenizers than one model can show.
- **Nothing filed upstream.** The drafted issue body in the plan should not be sent as
  written — its proposed fix is harmful. No PR or issue was opened by this run.
