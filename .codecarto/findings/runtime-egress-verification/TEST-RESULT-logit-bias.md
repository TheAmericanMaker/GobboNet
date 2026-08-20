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

## Disposition

- `q-logit-bias-root-cause`: **closed, hypothesis refuted.** Not a payload-shape defect.
- The P1-3 / Pass-5-#2 finding should be rewritten: the defect is the absence of a
  surface-string guard, not a malformed request.
- Real fix directions are the two the code comment already names — a GBNF grammar, or a
  streaming post-filter on the decoded text. Both are string-level; neither is a one-liner.
- A cheap partial mitigation: expand the ban set with common sub-token splits of each
  phrase. Raises the cost of routing around the ban without pretending to close it.
- **Nothing filed upstream.** The drafted issue body in the plan should not be sent as
  written — its proposed fix is harmful. No PR or issue was opened by this run.
