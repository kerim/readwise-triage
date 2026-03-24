"""Shared utilities for Readwise triage scripts."""

import json
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
BATCH_FILE = BASE_DIR / "triage-batch.json"
ACTED_FILE = BASE_DIR / "triage-acted.json"


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


def load_acted_ids():
    try:
        with open(ACTED_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_acted_ids(ids):
    tmp = ACTED_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(sorted(ids), f)
    os.replace(str(tmp), str(ACTED_FILE))


def clear_acted():
    ACTED_FILE.unlink(missing_ok=True)
