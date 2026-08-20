#!/usr/bin/env python3
"""
GobboNet egress-capture harness.
Stands in for fileserver.ps1: serves the static app and records every single
HTTP request the app makes (method, path, headers, body) to requests.jsonl.
Nothing is proxied anywhere. Any attempt to reach a non-local host by the
browser will therefore be visible in the browser network log, not here.
"""
import json, os, re, sys, time, threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.environ.get("GOBBONET_ROOT") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
EV   = os.environ.get("CAPTURE_DIR") or os.path.join(os.path.dirname(__file__), "capture")
LOG  = os.path.join(EV, "requests.jsonl")
EGRESS = os.path.join(EV, "egress.jsonl")
SHIM = os.path.join(os.path.dirname(__file__), "interceptor.js")
_lock = threading.Lock()

def record(entry):
    with _lock:
        with open(LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

class H(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):  # silence stderr noise
        pass

    def end_headers(self):
        # Every response is no-store. Without this the browser happily serves
        # cached js/css from a previous run against freshly-changed HTML, and
        # you end up testing the old application. Ask me how I know.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        SimpleHTTPRequestHandler.end_headers(self)

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode("utf-8", "replace") if n else ""

    def _cap(self, body=""):
        record({
            "ts": round(time.time(), 3),
            "method": self.command,
            "path": self.path,
            "client": self.client_address[0],
            "headers": dict(self.headers.items()),
            "body": body,
        })

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b)

    def _raw(self, data, ctype):
        if isinstance(data, str): data = data.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _chat(self):
        """Serve chat.html with the egress interceptor injected as the FIRST script,
        before any application code can run. Disk copy is never modified."""
        html = open(os.path.join(ROOT, "chat.html"), encoding="utf-8").read()
        # Derive a token from asset mtimes: stable across reloads, changes when
        # the tree changes. Appended to js/ and css/ refs so the browser cannot
        # reuse a previous version's scripts under the same cache key.
        newest = 0
        for sub in ("js", "css"):
            d = os.path.join(ROOT, sub)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    try: newest = max(newest, int(os.path.getmtime(os.path.join(d, f))))
                    except OSError: pass
        tok = str(newest)
        html = re.sub(r'(src|href)="((?:js|css)/[^"?]+)"',
                      lambda m: '%s="%s?v=%s"' % (m.group(1), m.group(2), tok), html)
        tag = '<script src="/_shim.js"></script>'
        i = html.lower().find("<head>")
        html = html[:i+6] + "\n" + tag + html[i+6:] if i >= 0 else tag + html
        return self._raw(html, "text/html; charset=utf-8")

    def _sse(self, chunks):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for c in chunks:
            self.wfile.write(("data: " + json.dumps(c) + "\n\n").encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True

    # ---- stub API surface -------------------------------------------------
    def do_GET(self):
        self._cap()
        p = self.path.split("?")[0]
        if p == "/_shim.js":
            return self._raw(open(SHIM).read(), "application/javascript")
        if p in ("/", "/chat.html", "/index.html"):
            return self._chat()
        if p == "/active-model.json":
            return self._json({"ggufFile": "gemma-4-26b-A4B-Q4_K_M.gguf",
                               "id": "gemma4-26b", "name": "Gemma 4 26B-A4B MoE"})
        if p == "/models-list.json":
            return self._json({"models": [
                {"file": "gemma-4-26b-A4B-Q4_K_M.gguf", "id": "gemma4-26b",
                 "name": "Gemma 4 26B-A4B MoE", "sizeGB": 15.2}]})
        if p.endswith("/health"):
            return self._json({"status": "ok"})
        if p == "/llm/props" or p == "/llm/v1/models":
            return self._json({"data": [{"id": "gemma4-26b"}],
                               "default_generation_settings": {"n_ctx": 16384}})
        if p.startswith("/llm/jobs/"):
            import base64
            reply = os.environ.get("HARNESS_REPLY") or open(
                os.path.join(os.path.dirname(__file__), "reply.txt")).read()
            sse = ""
            for piece in [reply]:
                sse += "data: " + json.dumps({"choices": [{"delta": {"content": piece}}]}) + "\n\n"
            sse += "data: " + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]}) + "\n\n"
            sse += "data: [DONE]\n\n"
            raw = sse.encode()
            frm = 0
            if "from=" in self.path:
                try: frm = int(self.path.split("from=")[1].split("&")[0])
                except Exception: frm = 0
            if frm >= len(raw):
                return self._json({"status": "done", "size": len(raw), "next": len(raw)})
            return self._json({"status": "done", "chunk_b64": base64.b64encode(raw[frm:]).decode(),
                               "next": len(raw), "size": len(raw)})
        if p.startswith("/llm/jobs"):
            return self._json({"jobs": []})
        if p == "/state/info":
            return self._json({"exists": False, "bytes": 0, "revision": 0, "mtime": 0})
        if p == "/state":
            return self._json({})
        if p == "/perf":
            return self._json({"current": {"ctxSize": 16384, "gpuLayers": 99,
                                           "kvCacheType": "q8_0"},
                               "max": {"ctxSize": 262144}})
        if p == "/swap-status":
            return self._json({"state": "idle"})
        # real files
        fs = os.path.join(ROOT, p.lstrip("/"))
        if os.path.isfile(fs):
            return SimpleHTTPRequestHandler.do_GET(self)
        return self._json({"stub": True, "path": p}, 404)

    def do_POST(self):
        body = self._read_body()
        self._cap(body)
        p = self.path.split("?")[0]
        if p == "/_capture":
            with _lock:
                with open(EGRESS, "a") as f:
                    f.write(body + "\n")
            return self._json({"ok": True})
        if p.endswith("/v1/chat/completions"):
            return self._sse([
                {"choices": [{"delta": {"content": "Harness"}}]},
                {"choices": [{"delta": {"content": " reply."}}]},
                {"choices": [{"delta": {}, "finish_reason": "stop"}]},
            ])
        if p == "/search/web_search":
            return self._json({"results": [
                {"title": "Capture stub result", "url": "https://example.invalid/x",
                 "content": "harness"}]})
        if p.startswith("/llm/jobs"):
            return self._json({"id": "job-harness-1", "status": "queued"})
        if p.endswith("/tokenize"):
            return self._json({"tokens": list(range(12))})
        if p.endswith("/embedding") or p.startswith("/embed"):
            return self._json([{"embedding": [0.01] * 768}])
        return self._json({"ok": True})

    def do_PUT(self):
        self._cap(self._read_body()); return self._json({"ok": True})
    def do_DELETE(self):
        self._cap(); return self._json({"ok": True})
    def do_OPTIONS(self):
        self._cap()
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.send_header("Content-Length", "0")
        self.end_headers()

if __name__ == "__main__":
    os.makedirs(EV, exist_ok=True)
    open(LOG, "w").close()
    open(EGRESS, "w").close()
    srv = ThreadingHTTPServer(("127.0.0.1", 8080), H)
    print("harness on http://127.0.0.1:8080 ; log -> " + LOG, flush=True)
    srv.serve_forever()
