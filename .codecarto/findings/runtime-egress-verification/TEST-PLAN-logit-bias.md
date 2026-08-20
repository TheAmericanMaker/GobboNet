# Runtime test plan: q-logit-bias-root-cause

Open question carried by `defect-scan-mechanical` (P1-3) and `defect-scan-semantic` (Pass 5 #2).
Both phases reached the same conclusion by reading and both flagged that source alone cannot
settle it. This is the test that would.

**Needs Windows.** The point is to observe a real `llama-server` reject the payload, which means
the pinned engine build and a loaded GGUF. Reading the code again adds nothing.

## The hypothesis

`buildLogitBias` writes a **map of token-id strings**:

```js
// js/06-state-sync.js:774
logitBias[String(id)] = strength;      // -> {"1234": -5}
```

That map is merged into the body sent to the OpenAI-compatible endpoint
(`js/10-chat.js:166`). llama.cpp takes two different shapes and they are not
interchangeable:

| Endpoint | Expected `logit_bias` shape |
|---|---|
| `/v1/chat/completions` (OpenAI-compatible) | array of `{id, bias}` objects |
| `/completion` (native) | map of token-id to bias |

If the client is sending the map form to the OpenAI-compatible endpoint, it fails to parse into
the expected vector and is dropped without an error surfacing to the user. That matches the
symptom the README reports: fully non-functional rather than unreliable.

## Procedure

1. Launch GobboNet normally on Windows. Load any model. Open a character and set a banned word
   that the model would otherwise produce readily.
2. Open devtools, Network tab. Send a message. Find the `POST` to `/llm/jobs` (or
   `/llm/v1/chat/completions` if the job relay is not in play) and read the request body.
   - **Record:** is `logit_bias` present, and is it `{"1234": -5}` or `[{"id":1234,"bias":-5}]`?
3. Check the `llama-server` console window for a parse complaint mentioning `logit_bias` at the
   same timestamp. It may be silent; note either way.
4. **The decisive step.** Replay the same request twice with only the shape changed, and compare
   whether the banned word appears in the output:
   - once with the body exactly as the client sent it
   - once with `logit_bias` rewritten to the array form
   Easiest way is devtools "Copy as fetch", paste into the console, edit the one field, and run
   both against `/llm/v1/chat/completions` directly.

## What each outcome means

- **Array form suppresses the word, map form does not.** Hypothesis confirmed. The fix is a
  one-line reshape at the call site, and the issue becomes a fix with a before and after rather
  than a guess. This is the outcome worth filing.
- **Neither form suppresses it.** The shape is not the cause, or not the only cause. Look at
  whether the pinned build supports `logit_bias` on the chat endpoint at all, and at the
  tokenizer, since the ids come from `/tokenize` against the same model.
- **Both suppress it.** The endpoint accepts both shapes and the bug is elsewhere entirely.
  Drop the hypothesis.

## Proposed fix, if confirmed

```js
logit_bias: Object.entries(logitBias).map(([id, bias]) => ({ id: Number(id), bias }))
```

## Status

**Test executed 2026-08-20 against the pinned engine. Hypothesis refuted, and inverted.**
Full capture in `TEST-RESULT-logit-bias.md`; the short version is below.

The map form is the shape that *works*. Against `b9294` on `/v1/chat/completions`, at
`temperature: 0` with three deterministic runs per cell, `{"13753": -20}` suppressed the
banned word and `[{"id":13753,"bias":-20}]` — the fix proposed above — came back
byte-identical to the no-bias baseline. Silently ignored: HTTP 200, no parse complaint in
the server console. The pair form `[[13753,-20]]` also works. So the shape table in this
plan is backwards; OpenAI's `logit_bias` is a map of token id to bias and llama.cpp's
OAI-compat layer follows it. The one shape `b9294` ignores is precisely the one this plan
proposed.

**Do not apply the "Proposed fix" section above.** It converts a working map into the only
shape that fails, and it would fail silently. Two related corrections to this plan: the
default strength is `-20` (`js/04-state.js:88`), not the `-5` used in the examples, and
there are **two** call sites — `js/10-chat.js:166` (send) and `js/10-chat.js:779`
(regenerate) — so any reshape would belong inside `buildLogitBias`, not "at the call site".

The endpoint outcome that actually applied was the third one in the table above — both
valid shapes suppress, so the bug is elsewhere. It is the ceiling already documented in
`js/06-state-sync.js:718-721`: `logit_bias` reaches canonical token ids only. Pushed hard
toward the banned word, the model re-spelled it as `y` + `ell` + ` ow` / ` yell` + ` ow`,
with **zero** overlap against the six banned ids. A literal substring check says the ban
held; the reader sees the word anyway, mangled. That is the whole of what `README.md:265`
means by "won't reliably keep it out" — a working parameter with a tokenizer-level
ceiling, not a dropped payload.

Transport and wiring were both cleared while chasing this, so neither needs revisiting:
`POST /llm/jobs` hands the body to its worker as a byte-exact string
(`fileserver.ps1:1046`) with no `ConvertTo-Json` round-trip, and
`card-banned-phrases` -> `card.bannedPhrases` -> `buildLogitBias` is consistent.

Still nothing filed upstream, and the hold now stands for a different reason. `README.md`
still lists logit bias under Known Bugs and no open PR or issue covers the root cause
(upstream queue as of 2026-08-20: PRs #2-#15, issues #1-#14). **The drafted issue body must
not go out as written** — it recommends the harmful reshape. What is worth filing is the
capture: the bias is applied faithfully and the model routes around it, so the fix is a
surface-string guard (GBNF grammar, or a streaming post-filter on decoded text), both
string-level and neither a one-liner. A cheaper partial mitigation is to expand the ban set
with common sub-token splits of each phrase — that raises the cost of routing around the
ban without pretending to close it.

Two gaps this run left open: the app was not driven end-to-end through `launch.bat` to
capture a real in-browser request (the server contract was tested directly, which is what
settles the hypothesis), and no engine build other than `b9294` was checked — the
ignored-shape result may differ on other tags, so re-test before bumping `LLAMA_PIN_TAG`.
