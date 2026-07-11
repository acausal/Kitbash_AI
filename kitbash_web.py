"""
kitbash_web.py — dead-simple POC web UI for the Kitbash query orchestrator.

NOT the final product. This just makes the stdio CLI feel real in a browser:
  - GET  /         -> static/index.html (chat box + live answer + OPS pane)
  - POST /query    -> spawns kitbash_cli.py, streams its STDOUT (chat JSON,
                      newline-delimited) to the browser as chunked HTTP, so the
                      answer renders progressively. CLI STDERR is teed to ops.log
                      (internal operational stream, not on the chat channel).
  - GET  /ops      -> tail of ops.log (the "internal streams" debug pane)

Stdlib only (http.server). One CLI subprocess per POST (per-request session).
Run:  .venv\\Scripts\\activate && python kitbash_cli.py ... no -- see __main__.
"""

import os
import sys
import subprocess
import logging
import html

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPO = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(REPO, "kitbash_cli.py")
STATIC = os.path.join(REPO, "static")
OPS_LOG = os.path.join(REPO, "ops.log")
PORT = int(os.environ.get("KITBASH_WEB_PORT", "8777"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("kitbash_web")


def _spawn_cli():
    """Spawn the CLI; return (proc, stderr_file). Stderr teed to ops.log."""
    stderr_fh = open(OPS_LOG, "a", encoding="utf-8", buffering=1)
    proc = subprocess.Popen(
        [sys.executable, CLI],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_fh,
        text=True,
        bufsize=1,
        cwd=REPO,
    )
    return proc, stderr_fh


class Handler(BaseHTTPRequestHandler):
    def _send_chunk(self, data: bytes):
        # Manual HTTP chunked framing so the browser streams progressively.
        self.wfile.write(b"%X\r\n" % len(data))
        self.wfile.write(data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._serve_file(os.path.join(STATIC, "index.html"), "text/html; charset=utf-8")
        elif self.path == "/ops":
            self._serve_ops()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/query":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", "replace")
        try:
            import json
            user_query = json.loads(body).get("query", "")
        except Exception:
            user_query = ""

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        if not user_query.strip():
            self._send_chunk(b'{"type":"error","message":"missing query"}\n')
            self._send_chunk(b"")
            return

        try:
            proc, stderr_fh = _spawn_cli()
        except Exception as e:
            self._send_chunk(b'{"type":"error","message":"cli spawn failed: %s"}\n' % str(e).encode())
            self._send_chunk(b"")
            return

        try:
            # Send the request to the CLI's stdin, then close it (EOF -> CLI exits).
            proc.stdin.write(json.dumps({"query": user_query}) + "\n")
            proc.stdin.close()
            # Stream stdout (chat JSON) line-by-line to the browser.
            for line in proc.stdout:
                self._send_chunk(line.encode("utf-8", "replace"))
            proc.stdout.close()
            proc.wait()
        except Exception as e:
            self._send_chunk(b'{"type":"error","message":"stream error: %s"}\n' % str(e).encode())
        finally:
            stderr_fh.close()
            # Terminate defensively.
            if proc.poll() is None:
                proc.kill()
            self._send_chunk(b"")  # end chunked stream

    def _serve_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_ops(self):
        try:
            with open(OPS_LOG, "r", encoding="utf-8") as f:
                lines = f.readlines()[-200:]
        except FileNotFoundError:
            lines = []
        body = "".join(lines).encode("utf-8", "replace")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        log.info("%s - %s", self.address_string(), fmt % args)


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info("kitbash_web POC on http://127.0.0.1:%d  (Ctrl+C to stop)", PORT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
