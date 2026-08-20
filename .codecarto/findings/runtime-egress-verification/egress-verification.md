# Runtime Egress Verification Report — GobboNet

<!--
  Output for the `runtime-egress-verification` phase.
  Runtime counterpart to defect-scan-mechanical / defect-scan-semantic: the product is
  executed and network traffic is captured, rather than reasoned about from source.
  Evidence levels: `captured` | `observed fact` | `strong inference` | `open question`.
  `captured` is stronger than `observed fact`: a recorded request/response, not a code read.
-->

## Scan Context

- **Source:** `../../../` (repository root), unmodified working copy at `5524fd4` (v1.5.1-era)
- **Version caveat:** upstream has since moved to `f1b9f50` (v1.5.8), adding ~2,025 lines across 22
  files including `SECURITY.md`, +405 in `fileserver.ps1` and +268 in `chat.html`. Re-checked
  against that tree: the search relay's encoded command is **byte-identical** (md5 `3fed3c1f5730`),
  so R4 still describes what ships; the three README lines in R4/R5 are unchanged; `.jobs/` is still
  unignored (R7); `logit_bias` construction is unchanged. **Not re-measured:** the client-side
  results R1, R2, R3 and R8 were captured on the older tree. Treat them as verified for v1.5.1-era
  and unconfirmed for v1.5.8 until the harness is re-run.
- **Static references:** `findings/defect-scan-semantic/semantic-defects.md`,
  `findings/defect-scan-mechanical/mechanical-defects.md`
- **Date:** 2026-08-19
- **Host:** Fedora Linux 7.1.8, Chromium 148, PowerShell 7.6.5 (linux-x64)
- **Claims under test:** `README.md:3`, `README.md:174`, `README.md:195`, `README.md:342`,
  `README.md:98`, and the in-product banner "LLAMA.CPP — ZERO TELEMETRY, FULLY OFFLINE"
- **Scope:** what crosses the network boundary during boot, chat, idle, render, search,
  and extension load. Not a correctness or performance pass.

---

## Method

Three instruments, so no single failure mode can produce a false "clean" result.

1. **In-page interceptor.** A capture harness stands in for `fileserver.ps1`, serving the
   real unmodified app files and injecting a script as the **first** element in `<head>`,
   ahead of all 24 application scripts. It wraps `fetch`, `XMLHttpRequest`, `WebSocket`,
   `EventSource`, `navigator.sendBeacon`, `Element.setAttribute`, and the `.src`/`.href`
   setters on script, image, iframe and link elements. Console ordering confirms it runs first.
2. **Performance Resource Timing.** Independent of the interceptor, and catches
   subresources however they were created (including via `innerHTML`, which property
   hooks miss).
3. **Shadowed cmdlet.** For the PowerShell relay, a function named `Invoke-WebRequest`
   is defined before the relay body runs. A function outranks a cmdlet in PowerShell's
   command resolution order, so the relay's outbound call is logged with full URI,
   headers and body — and never delivered.

### Instrument validation

Negative results are meaningless without proving the instrument can see a positive, and
that the environment permits egress at all. Both were established before any finding below.

| Check | Result |
|---|---|
| Four egress APIs fired at a documentation-reserved domain | all four caught and flagged non-local |
| External image load from the page | **loaded** — real traffic left and returned |
| `no-cors` fetch to an external host | opaque response — request genuinely went out |

**Instrument caveat (important for anyone repeating this):** the browser devtools network
log did *not* record those four canaries, though it logged their loopback reports. It
under-reports egress and must not be used as the sole channel. The interceptor and the
Performance API agree throughout and are the authoritative record here.

---

## Findings

| # | Location | Finding | Evidence Level | Severity | Action |
|---|----------|---------|----------------|----------|--------|
| R1 | `chat.html`, `js/*.js` | Cold boot, message send, and a 118-second idle soak produce **zero** external requests. 37 app-initiated calls, all loopback. No version check, update ping, analytics, or unload beacon. Every CSS/JS subresource is relative — no CDN, no webfont, no remote asset in the page. | captured | — | confirms claim |
| R2 | `js/12-render.js` | A model reply containing `![chart](https://example.com/…png?exfil=…)` renders as an **anchor, not an `<img>`**: zero img tags created, zero remote fetches. The markdown-image exfiltration vector — the classic one for a local chat app, reachable from a malicious character card, a RAG document, or a search result — does not auto-fire. | captured | — | confirms claim; do not regress |
| R3 | `fileserver.ps1:411`, `:1396`, `:1452` | Executed under PowerShell 7. All outbound call sites build a loopback URL from a hardcoded literal (`'http://127.0.0.1:{0}…' -f $UpstreamPort`); the fourth site is an inbound `HttpListener`. The reverse proxy is **structurally incapable** of leaving the machine. Binds `0.0.0.0:8080` deliberately, for LAN access. | captured | — | confirms claim |
| R4 | decoded `launch.bat:1608` | **Refines `defect-scan-semantic` Pass 4 #1** — see Corrections below. The relay builds a *fresh* header hashtable and does **not** forward browser headers. An injected `User-Agent` and a junk `X-Nosy-Header` were both dropped. What leaves is the query body verbatim plus the user's own `Authorization` key. | captured | medium | fix docs, not code |
| R5 | `js/19-extensions.js:60-67`, `:42` | **Confirms Pass 4 #7 with runtime evidence.** The extension loader accepts arbitrary **public-internet** URLs and fetches them; both channels recorded the requests leaving. Unsandboxed execution is disclosed (`README.md:320`, `:349`), but the *privacy* section (`README.md:174`) says web search is "the *one* feature that needs the internet", and that remote extension URLs need not be LAN-local is stated nowhere. | captured | low | fix docs |
| R6 | `launch.bat` health probes | **Confirms mechanical P1-2 live, by accident.** The test host already ran Ollama 0.32.13 on `*:11434` — GobboNet's default `GEMMA_LLM_PORT`. `fileserver.ps1` proxied a generation into it and Ollama answered `{"error":{"message":"model 'local' not found"}}`. The misdetection P1-2 predicts is not hypothetical; it happens on any machine with Ollama installed. | captured | medium | fix before porting |
| R7 | `.gitignore` vs `fileserver.ps1` job spool | **New.** `.jobs/` is not gitignored. A real job was run through the real server; the spool's `.sse` file reassembles to the model's full reply. `.gitignore` covers `conversations/`, `.gobbonet-state.json`, `.swap-status.json` and others but misses this one, so assistant output can be committed and pushed by accident. The prompt itself is not spooled — only the reply transcript and thread id. | captured | low | fix before porting |
| R8 | `js/11-search.js:12-16`, `state.searchEnabled` | **New (minor).** Search enablement and the API key persist across a full reload. A search fired automatically for a message in a session where search was never toggled on. Enabling it once means every later message leaves the machine until it is manually switched off — there is no per-message or per-session confirmation. | captured | low | fix docs / consider UX |

### R4 in full — what the relay actually sends

The decisive component is not a file in the repo. It is a base64 `-EncodedCommand` blob at
`launch.bat:1608`, started minimized and hidden; decoded, it is 36 lines. It is the only
component that reaches the internet during normal use, and it is invisible to grep-based
review of the source tree. The mechanical pass noted this honestly in its coverage limits
("the encoded search-proxy command (launch.bat:1608) was not fully decoded").

Captured outbound call, sent through the full real chain
(`curl → fileserver.ps1:8080/search/* → 127.0.0.1:11435 → captured`):

```
outbound URI : https://ollama.com/api/web_search
method       : POST
headers      : Authorization: Bearer sk-<user's own search key>
               Content-Type: application/json
body         : {"query":"CHAINCANARY_A77B does my rash mean lymphoma, im 41 in
                Bay City MI","max_results":5}
timeout      : 30

NOT forwarded: User-Agent, X-Nosy-Header, cookies
```

Two conclusions, pulling in opposite directions:

- **The metadata claim is honoured.** The relay constructs
  `$headers = @{ 'Content-Type' = 'application/json' }` and adds only `Authorization`.
  Browser User-Agent, `Accept-Language`, cookies and arbitrary headers are dropped. This
  was verified deliberately, by injecting a header specifically to see whether it rode along.
- **Content is not sanitised.** The query is the user's entire message, verbatim, and the
  request is authenticated with their own API key — so the search is neither anonymous nor
  abridged at the destination. `README.md:174` frames search as the AI "looking things up";
  a reader would not necessarily expect their symptoms, age and town to become the query string.

---

## Corrections to earlier phases

Runtime evidence revised two static conclusions. Both directions matter.

### 1. `defect-scan-semantic` Pass 4 #1 overstates the defect

The static finding concludes the README's search-privacy claim "is false as written" and
that "the code strips nothing", describing the relay as forwarding "verbatim to
`https://ollama.com/api`".

That is accurate for the **first** hop — `fileserver.ps1:423-436` does forward request
headers unchanged to `127.0.0.1:11435`. It is **not** accurate for the hop that actually
leaves the machine. The relay discards the incoming header set and builds a new one. So
identifying *metadata* is in fact stripped before egress, which is the narrow thing
`README.md:342` claims.

**Suggested restatement:** the claim is true of metadata and false of content. The
defensible correction to `README.md:342` is to say that searches are sent without browser
identifying headers, but that the search text itself is sent as typed, under the user's own
API key. The current wording invites a reader to assume the query is anonymised.

`privacyFetch` being a bare passthrough (`02-model.js:398-400`) is still worth flagging —
it is a misleading name for an identity function, and it is not on the search path at all —
but it is not the mechanism by which the claim would be honoured or broken.

### 2. A first-pass scoping count of this phase's own was too pessimistic

An initial pattern count of outbound call sites attributed five to `fileserver.ps1` and
treated them as untested egress surface. Executed, **none** reach the internet (R3). Pattern
counts over `Invoke-WebRequest|HttpWebRequest|WebClient|curl` are a scoping heuristic only;
they do not distinguish a loopback relay from an internet client. Recorded here so the
number is not quoted onward as an egress figure.

### 3. Two claims in this phase's early framing were softened by the static passes

Worth recording because it cuts against this phase's own first read:

- The plaintext-LAN password was initially framed as an undisclosed contradiction of
  `README.md:98` ("never leaves your computer"). Pass 4 #6 is right that this is a
  **documented design choice** — the login page itself says, verbatim, "This connection is
  over your local network in plain text (not encrypted)… Avoid using it on shared or public
  Wi-Fi." The user is warned at the point of use. The residual issue is narrower and purely
  editorial: `README.md:98` contradicts the product's own login page, and only one of them
  can be right.
- Unsandboxed extension/card code was initially framed as undisclosed. It is disclosed
  (`README.md:320`, `:349`, and `23-card-code.js:22-28`). Only the *network* dimension —
  that extension URLs may be remote and public — is undocumented (R5).

---

## Coverage and limits

- **Executed:** `chat.html` + all 24 `js/*.js` (12,593 lines); `fileserver.ps1` (1,618 lines);
  the decoded search relay (36 lines). Boot, thread creation, message send, streamed reply
  render, job spool round-trip, login/session/fingerprint gating, search with a live key,
  extension load, 118-second idle soak.
- **Not executed:** `launch.bat` (1,973 lines) — batch, cannot run on Linux at all. Its
  outbound sites target `github.com/ggml-org/llama.cpp/releases` and `huggingface.co`,
  consistent with the disclosed one-time setup, but this is read from source, not observed.
  Confirming it needs a Windows host. `hardware-probe.ps1` (1,961) and `identify-model.ps1`
  (477) were not executed; neither contains an outbound call site, so both are low-risk by
  construction rather than by test.
- **No packet capture.** The host lacked `CAP_NET_RAW`, so there is no NIC-level record.
  Egress is established at the browser API boundary and at the PowerShell cmdlet boundary.
  Both are *upstream* of the network, so they capture attempts regardless of whether a
  request would have succeeded — which is the right measurement for these claims, but it is
  not the same as a wire capture.
- **`llama-server` was stubbed.** Inference itself was never run against a real GGUF; the
  upstream was an OpenAI-compatible stub. This phase tests the transport, not the model.
- **No canary data was transmitted to any third party.** The relay's outbound call was
  captured before delivery; API keys and passwords used in testing were fabricated.

## Validation

- Repository left unmodified: working tree clean at `5524fd4` after testing, `.jobs/` test
  spool removed, all harness processes stopped and ports released.
- Every finding above is backed by a recorded request. The decisive capture is committed at
  `evidence/proxy-outbound.jsonl`; the harness that produced it is in `harness/`.
- Instrument validated in both directions before use (negative control caught; egress
  confirmed possible) — see Method.
