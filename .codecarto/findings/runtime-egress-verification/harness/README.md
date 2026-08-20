# Egress capture harness

Reproduces every finding in `../egress-verification.md`. Nothing here modifies the
repository — the app is served from an unmodified working copy and instrumentation is
injected at serve time.

Requires: Python 3, a Chromium-based browser, and (for the relay test) PowerShell 7.
Tested on Fedora Linux; the client tests work on any OS, the relay test needs `pwsh`.

## 1. Client egress (findings R1, R2, R5, R8)

```bash
cd .codecarto/findings/runtime-egress-verification/harness
python3 harness.py            # serves the real app on 127.0.0.1:8080
```

Open `http://127.0.0.1:8080/chat.html`. The console must log
`[EGRESS INTERCEPTOR ACTIVE]` **before** `[chat.html build]` — that ordering is what
proves the interceptor wrapped the network APIs before any app code ran. If it doesn't,
the run is invalid.

Then, in the devtools console:

```js
// every network call the app has made, and whether it was local
window.__EGRESS.map(r => `${r.api} ${r.method} ${r.host} local=${r.local}`)

// anything that left the machine
window.__EGRESS.filter(r => !r.local)
```

Server-side records land in `capture/` (`requests.jsonl` = every request with headers and
body; `egress.jsonl` = the interceptor's own feed).

**Validate the instrument first.** A clean result means nothing until you have shown the
harness can see a positive and that egress is actually possible from your browser:

```js
// negative control — all four must appear in window.__EGRESS as local=false
await fetch('https://example.com/canary-fetch').catch(()=>{});
new Image().src = 'https://example.com/canary-img.png';
navigator.sendBeacon('https://example.com/canary-beacon', 'x');
const x = new XMLHttpRequest(); x.open('POST','https://example.com/canary-xhr'); x.send('x');

// confound check — must resolve 'LOADED', or you are measuring a sandbox, not the app
await new Promise(r => { const i = new Image();
  i.onload = () => r('LOADED'); i.onerror = () => r('blocked');
  i.src = 'https://www.google.com/favicon.ico?cb=' + Math.random(); })
```

Note: the devtools **Network panel does not reliably show these external canaries**. Trust
`window.__EGRESS` and `performance.getEntriesByType('resource')`, not the Network tab.

`reply.txt` is what the stubbed model returns; it contains a remote markdown image, which
is how R2 (remote images render as links, not `<img>`) is tested. Edit it to try variants.

## 2. Search relay egress (finding R4)

```bash
./decode-relay.sh                                   # extracts the base64 blob from launch.bat
cat shadow-prelude.ps1 search-relay.ps1 > run-relay.ps1
CAPTURE_PATH=./capture/proxy-outbound.jsonl pwsh -NoProfile -File run-relay.ps1 &
```

`shadow-prelude.ps1` defines a function named `Invoke-WebRequest`, which outranks the real
cmdlet, so the relay's outbound request is written to `CAPTURE_PATH` and **never sent**.
Then drive it:

```bash
curl -s -X POST http://127.0.0.1:11435/web_search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer FAKE-KEY" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0)" \
  -H "X-Nosy-Header: should-not-be-forwarded" \
  -d '{"query":"canary query","max_results":5}'

cat ./capture/proxy-outbound.jsonl
```

The captured record shows the destination and exactly which headers survive the hop. The
point of the nosy header and the User-Agent is to demonstrate that they are *dropped* —
that is the evidence for the metadata half of R4.

## 3. Full chain through the real file server

```bash
# pick a port that is NOT 11434 — Ollama's default collides with GEMMA_LLM_PORT (see R6)
SALT=a1b2c3d4e5f60718
HASH=$(printf '%s' "${SALT}testpass123" | sha256sum | cut -d' ' -f1)
GEMMA_ROOT="$PWD/../../../.." GEMMA_ACCESS_SECRET="$SALT:$HASH" GEMMA_LLM_PORT=11444 \
  pwsh -NoProfile -File ../../../../fileserver.ps1
```

`fileserver.ps1` refuses to start without `GEMMA_ACCESS_SECRET` in `salt:sha256(salt+password)`
form — normally set by `launch.bat`. Log in at `/login` with the password, keep the **same
User-Agent** for every subsequent request (sessions are fingerprint-bound, so changing it
invalidates the cookie), then POST to `/search/web_search` to exercise
`browser → fileserver → relay`.

## Cleanup

```bash
rm -rf capture search-relay.ps1 run-relay.ps1 ../../../../.jobs
```

`.jobs/` is the server's spool and is **not** currently gitignored (finding R7) — check it
before committing.
