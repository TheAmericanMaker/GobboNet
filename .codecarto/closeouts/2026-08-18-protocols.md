# Closeout — protocols

## Summary

- Extracted 18 protocols/event streams across six boundary classes: process-to-process (GEMMA_* env, model metadata files, .gobbonet-secret, .llama-launch.cmd + lock), UI-to-core (auth/session, /state sync, /llm/jobs relay, swap protocol), core-to-provider (llama-server SSE, /tokenize, embeddings, Ollama web_search), tool-to-runtime (GGUF metadata), runtime-to-persistence (IndexedDB v2, localStorage mirror, spool files), and local-files-to-exported-artifacts (character cards V1/V2/V3, export bundles).
- Converted control flow into 5 state machines: generation-job lifecycle (server + client), swap-status phase machine, client state-sync + boot decision matrix, stream-parser thinking-format phases, and the jobsAvailable probe tri-state. Synchronous barriers separated from observational events in each.
- Persistence semantics captured for IndexedDB v2 (mutable, per-record writes, threadOrder sidecar), localStorage mirror (quota-normalized), /state blob (last-write-wins, mtime-only versioning), job spool (append-only .sse + mutable .json + flag .cancel), swap status/lock, model metadata, secret file, and export bundles.
- 19 compatibility hazards tabled, led by client/fileserver version skew, file:// vs served mode, per-origin storage, GGUF v2/v3-only parsing, card-format lossiness, and the mistral-v7-tekken template-name footgun.

## Routed item closure

- arch-CF1 closed: SSE spool byte format + /llm/jobs chunk framing (chunk_b64, from/max offsets, 256KB budget), /state JSON schema + mtime protocol (ms precision, X-State-Mtime header), swap-status phase machine (idle/starting/ready/error with lazy promotion), GGUF metadata fields consumed (chat_template, architecture, context_length; v2/v3 only), character-card V1/V2/V3 field mapping (all three carriers), and the Ollama web_search schema (proxy decoded from launch.bat:1608 — verbatim forwarder; client request/response extracted; upstream remainder recorded as open question).

## Decisions Beyond Prompt

- The Ollama upstream response schema beyond {results:[{title,content,url}]} is recorded as an open question rather than guessed (the proxy forwards verbatim, so the schema is genuinely not visible in-repo).
- The mid-generation 401 path (client clears breadcrumb + DELETEs the job, cancelling the live generation) is recorded as a protocol fact and routed to defect-scan-semantic as proto-CF1 rather than ruled on here.

## Coverage

- Inspected: fileserver.ps1 (full), js/03-generation.js (full), js/06-state-sync.js (full), js/05-persistence.js (full), js/16-card-io.js (full), js/11-search.js (full), identify-model.ps1 (full), js/24-boot.js (full), large partial reads of js/02-model.js, js/08-rag.js, js/10-chat.js, js/01-config.js, launch.bat; decoded the search-proxy encoded command in full.
- Skipped: js/07-prompt, 12-render, 13-dashboard, 14-scroll, 15-cards, 17-personas, 18-utils, 19-extensions, 20-macros, 21-data, 22-scheduler, 23-card-code; chat.html; css/*; hardware-probe.ps1; setup-lan.bat; remaining launch.bat sections.
- Evidence basis: source inspection only (Windows-only, no runtime verification possible). Disposition: COMPLETE.

## Decisions Beyond Prompt

- The Ollama web_search upstream response schema beyond {results:[{title,content,url}]} is recorded as an open question (q-websearch-response-fields) rather than guessed; the proxy is a verbatim forwarder so the schema is genuinely not visible in-repo.
- The mid-generation 401 path (client clears breadcrumb + DELETEs the job, cancelling the live generation) is recorded as a protocol fact and routed to defect-scan-semantic as proto-CF1 rather than ruled on here; the protocols phase documents behavior, it does not rule on defects.
