#!/usr/bin/env python3
"""Readwise Triage Web App — zero-dependency local server for fast document triage."""

import json
import os
import subprocess
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).parent
BATCH_FILE = BASE_DIR / "triage-batch.json"
ACTED_FILE = BASE_DIR / "triage-acted.json"
HTML_FILE = BASE_DIR / "triage-app.html"
PORT = 5111


def load_acted_ids():
    try:
        with open(ACTED_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_acted_ids(ids):
    with open(ACTED_FILE, "w") as f:
        json.dump(sorted(ids), f)


def run_readwise(*args):
    """Run a readwise CLI command and return parsed JSON."""
    cmd = ["readwise"] + list(args) + ["--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return {"ok": True}


class TriageHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default access logs

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.serve_html()
        elif path == "/api/batch":
            self.serve_batch()
        elif path.startswith("/api/details/"):
            doc_id = path.split("/api/details/", 1)[1]
            self.serve_details(doc_id)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/action":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            self.handle_action(body)
        elif self.path == "/api/prep":
            self.run_prep()
        else:
            self.send_error(404)

    def serve_html(self):
        try:
            content = HTML_FILE.read_bytes()
        except FileNotFoundError:
            self.send_error(404, "triage-app.html not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def serve_batch(self):
        try:
            with open(BATCH_FILE, "r") as f:
                batch = json.load(f)
        except FileNotFoundError:
            self.send_json({"error": "No batch file. Run triage-prep.py first."}, 404)
            return

        acted = load_acted_ids()
        batch["documents"] = [d for d in batch["documents"] if d["id"] not in acted]
        self.send_json(batch)

    def serve_details(self, doc_id):
        result = run_readwise("reader-get-document-details",
                              "--document-id", doc_id)
        self.send_json(result)

    def run_prep(self):
        """Run triage-prep.py to generate a new batch."""
        prep_script = BASE_DIR / "triage-prep.py"
        env = os.environ.copy()
        # Ensure homebrew/user paths are available for readwise CLI
        extra = "/opt/homebrew/bin:/usr/local/bin"
        env["PATH"] = extra + ":" + env.get("PATH", "")
        result = subprocess.run(
            [sys.executable, str(prep_script)],
            capture_output=True, text=True, cwd=str(BASE_DIR), env=env
        )
        if result.returncode != 0:
            self.send_json({
                "error": result.stderr.strip(),
                "stdout": result.stdout.strip()
            }, 500)
        else:
            self.send_json({"ok": True, "output": result.stdout.strip()})

    def handle_action(self, data):
        doc_id = data.get("id")
        action = data.get("action")
        tags = data.get("tags", [])

        if not doc_id or not action:
            self.send_json({"error": "Missing id or action"}, 400)
            return

        result = {}

        if action == "archive":
            result = run_readwise("reader-move-documents",
                                  "--document-ids", doc_id,
                                  "--location", "archive")
        elif action == "shortlist":
            result = run_readwise("reader-move-documents",
                                  "--document-ids", doc_id,
                                  "--location", "shortlist")
        elif action == "keep":
            pass
        elif action == "tag_archive":
            if tags:
                tag_str = ",".join(tags)
                tag_result = run_readwise("reader-add-tags-to-document",
                                          "--document-id", doc_id,
                                          "--tag-names", tag_str)
                if "error" in tag_result:
                    self.send_json({"error": "Tagging failed: " + tag_result["error"]}, 500)
                    return
            result = run_readwise("reader-move-documents",
                                  "--document-ids", doc_id,
                                  "--location", "archive")
        else:
            self.send_json({"error": f"Unknown action: {action}"}, 400)
            return

        acted = load_acted_ids()
        acted.add(doc_id)
        save_acted_ids(acted)

        self.send_json({"ok": True, "result": result})


if __name__ == "__main__":
    if not BATCH_FILE.exists():
        print(f"No batch file at {BATCH_FILE}. Run triage-prep.py first.")
        sys.exit(1)

    class ThreadedServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True

    server = ThreadedServer(("localhost", PORT), TriageHandler)
    print(f"Triage app running at http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()
