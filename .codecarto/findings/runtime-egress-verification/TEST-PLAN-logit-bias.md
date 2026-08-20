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

Not filed upstream. `README.md` still lists logit bias under Known Bugs, and no open PR or issue
covers the root cause (checked against the upstream queue on 2026-08-20: PRs #2-#15, issues #1-#14).
The drafted issue body is ready and is held deliberately until this test runs, because
"probably the bug" is worth much less to the maintainer than a capture.
