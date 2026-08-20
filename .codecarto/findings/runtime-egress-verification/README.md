# Runtime Egress Verification

Runtime counterpart to the static defect scans. Where `defect-scan-semantic` reads the
code to reason about trust boundaries, this phase **executes the product** and records
what actually crosses the network boundary.

**Primary output:** `egress-verification.md`

**Depends on:** `defect-scan-mechanical` and `defect-scan-semantic` (it confirms, refines,
and in one case corrects their findings).

**What it executes:**

- the browser client (`chat.html` + `js/*.js`) under a total in-page network interceptor
- the real `fileserver.ps1`, under PowerShell 7 on Linux
- the search relay decoded from the base64 `-EncodedCommand` blob at `launch.bat:1608`,
  with `Invoke-WebRequest` shadowed so its outbound call is captured rather than delivered

**Why it exists:** three claims in `README.md` are about network behaviour ("your words
never leave your home", "web search is the one feature that needs the internet",
"identifying metadata and telemetry are stripped from your searches"). Those are
empirical claims, and reading the code was not enough to settle them — the decisive
component is a base64 blob that the mechanical pass explicitly left undecoded.

**Reproducing:** see `harness/README.md`. The harness is self-contained and does not
modify the repository; it serves the app from an unmodified working copy and injects
instrumentation at serve time.

See `egress-verification.md` for findings, including a **Corrections to earlier phases**
section that revises two static conclusions in light of captured traffic.
