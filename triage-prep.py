#!/usr/bin/env python3
"""Pre-generate triage pitches for Readwise Reader Later list documents.

Runs nightly (via launchd). Fetches new Later items since last run, generates
Haiku pitches for new items only, merges with stale backlog, prunes acted-on
items, and caches tag frequency/recency data.

Output: triage-batch.json
"""

import json
import os
import subprocess
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone

# --- Configuration ---
FRESH_BATCH_SIZE = 20  # max new items to fetch per run
MODEL = "claude-haiku-4-5-20251001"
TAG_ARCHIVE_SAMPLE = 100  # how many archived docs to sample for tag stats

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BATCH_FILE = os.path.join(BASE_DIR, "triage-batch.json")
ACTED_FILE = os.path.join(BASE_DIR, "triage-acted.json")
PERSONA_FILE = os.path.join(BASE_DIR, "reader_persona.md")
DOC_FIELDS = "url,title,author,category,word_count,reading_time,summary,site_name,published_date,saved_at"


def get_api_key():
    result = subprocess.run(
        ["security", "find-generic-password", "-a", "readwise-triage",
         "-s", "readwise-triage-anthropic-api-key", "-w"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Error: Could not retrieve API key from keychain.", file=sys.stderr)
        print("Store it with: security add-generic-password -a readwise-triage "
              "-s readwise-triage-anthropic-api-key -w YOUR_KEY -U", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def run_readwise(*args):
    """Run a readwise CLI command and return parsed JSON."""
    cmd = ["readwise"] + list(args) + ["--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Readwise CLI error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def fetch_later_documents(limit, updated_after=None):
    """Fetch documents from Later list."""
    args = ["reader-list-documents", "--location", "later",
            "--limit", str(limit), "--response-fields", DOC_FIELDS]
    if updated_after:
        args += ["--updated-after", updated_after]
    data = run_readwise(*args)
    return data.get("results", []), data.get("count", 0)


def fetch_tag_stats():
    """Derive tag frequency and recency from recently archived documents."""
    data = run_readwise("reader-list-documents", "--location", "archive",
                        "--limit", str(TAG_ARCHIVE_SAMPLE),
                        "--response-fields", "tags")
    docs = data.get("results", [])

    tag_counts = Counter()
    tag_latest = {}  # tag_name -> most recent created timestamp

    for doc in docs:
        tags = doc.get("tags") or {}
        for key, info in tags.items():
            name = info.get("name", key)
            tag_counts[name] += 1
            created = info.get("created", 0)
            if created > tag_latest.get(name, 0):
                tag_latest[name] = created

    frequent = [name for name, _ in tag_counts.most_common(10)]
    recent_all = sorted(tag_latest.keys(), key=lambda n: tag_latest[n], reverse=True)
    recent = [n for n in recent_all if n not in frequent][:5]

    return frequent, recent


def load_persona():
    try:
        with open(PERSONA_FILE, "r") as f:
            return f.read()
    except FileNotFoundError:
        return None


def load_existing_batch():
    try:
        with open(BATCH_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_acted_ids():
    try:
        with open(ACTED_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def clear_acted():
    """Remove acted file after pruning."""
    try:
        os.remove(ACTED_FILE)
    except FileNotFoundError:
        pass


def generate_pitches(documents, persona, api_key):
    """Call Haiku to generate pitches for a list of documents."""
    if not documents:
        return {"batch_overview": "", "pitches": []}

    docs_summary = []
    for i, doc in enumerate(documents):
        docs_summary.append(
            f"Document {i+1}:\n"
            f"  Title: {doc.get('title', 'Untitled')}\n"
            f"  Author: {doc.get('author', 'Unknown')}\n"
            f"  Site: {doc.get('site_name', 'Unknown')}\n"
            f"  Category: {doc.get('category', 'article')}\n"
            f"  Word count: {doc.get('word_count', '?')}\n"
            f"  Reading time: {doc.get('reading_time', '?')}\n"
            f"  Published: {doc.get('published_date', 'Unknown')}\n"
            f"  Summary: {doc.get('summary', 'No summary available')}"
        )

    persona_section = ""
    if persona:
        persona_section = f"\n\n## Reader Persona\n\n{persona}"

    prompt = f"""You are generating triage pitches for a Readwise Reader Later list.
{persona_section}

## Documents

{chr(10).join(docs_summary)}

## Task

For each document, generate a JSON array with one object per document containing:
- "overview": 2-4 sentence synthesis of what the piece is about (not just restating the summary)
- "why_read": A genuine, opinionated pitch for why this reader should read it, connecting to their interests/goals
- "why_skip": An honest reason they might not need to read it

Return ONLY valid JSON in this format:
{{"pitches": [{{"overview": "...", "why_read": "...", "why_skip": "..."}}, ...]}}"""

    request_body = json.dumps({
        "model": MODEL,
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    )

    try:
        with urllib.request.urlopen(req) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)

    if response.get("stop_reason") == "max_tokens":
        print("Warning: API response was truncated (max_tokens reached).", file=sys.stderr)

    text = response["content"][0]["text"]
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Failed to parse API response: {e}", file=sys.stderr)
        print(f"Raw text: {text[:500]}", file=sys.stderr)
        sys.exit(1)


def build_doc_entry(doc, pitch, is_fresh):
    """Build a document entry for the batch JSON."""
    return {
        "id": doc["id"],
        "title": doc.get("title", "Untitled"),
        "author": doc.get("author", "Unknown"),
        "url": doc.get("url", ""),
        "site_name": doc.get("site_name", ""),
        "category": doc.get("category", "article"),
        "word_count": doc.get("word_count", 0),
        "reading_time": doc.get("reading_time", ""),
        "summary": doc.get("summary", ""),
        "published_date": doc.get("published_date", ""),
        "saved_at": doc.get("saved_at", ""),
        "overview": pitch.get("overview", ""),
        "why_read": pitch.get("why_read", ""),
        "why_skip": pitch.get("why_skip", ""),
        "is_fresh": is_fresh,
    }


def main():
    existing = load_existing_batch()
    acted_ids = load_acted_ids()

    # Determine fetch window
    last_fetched = None
    if existing:
        last_fetched = existing.get("last_fetched_since")

    # 1. Fetch new Later items
    print(f"Fetching up to {FRESH_BATCH_SIZE} new Later items...")
    if last_fetched:
        print(f"  (since {last_fetched})")
    new_docs, total_count = fetch_later_documents(FRESH_BATCH_SIZE, updated_after=last_fetched)

    # Filter out any we've already processed (in existing batch or acted on)
    already_seen = set(acted_ids)
    if existing:
        already_seen.update(d["id"] for d in existing.get("documents", []))
    new_docs = [d for d in new_docs if d["id"] not in already_seen]

    print(f"  Found {len(new_docs)} new items (of {total_count} total in Later).")

    # If no new items since last run AND no stale carryover, fetch next batch
    # from the full Later list (backlog processing)
    stale_remaining = 0
    if existing:
        stale_remaining = sum(1 for d in existing.get("documents", []) if d["id"] not in acted_ids)

    if not new_docs and stale_remaining == 0:
        print("No new items and no stale backlog. Fetching next batch from Later list...")
        new_docs, total_count = fetch_later_documents(FRESH_BATCH_SIZE)
        new_docs = [d for d in new_docs if d["id"] not in already_seen]
        print(f"  Found {len(new_docs)} unprocessed items from Later list.")

    # 2. Generate pitches for new items
    new_entries = []
    if new_docs:
        persona = load_persona()
        if persona:
            print("Loaded reader persona.")
        else:
            print("No persona file — pitches will be generic.")

        api_key = get_api_key()
        print(f"Generating pitches for {len(new_docs)} new items with {MODEL}...")
        result = generate_pitches(new_docs, persona, api_key)

        if len(result.get("pitches", [])) < len(new_docs):
            print(f"Warning: API returned {len(result.get('pitches', []))} pitches "
                  f"for {len(new_docs)} documents.", file=sys.stderr)

        for i, doc in enumerate(new_docs):
            pitch = result["pitches"][i] if i < len(result.get("pitches", [])) else {}
            new_entries.append(build_doc_entry(doc, pitch, is_fresh=True))

    # 3. Carry over stale items (prune acted-on ones, mark as not fresh)
    stale_entries = []
    if existing:
        for doc in existing.get("documents", []):
            if doc["id"] not in acted_ids:
                doc["is_fresh"] = False
                stale_entries.append(doc)

    # Deduplicate: new items take precedence over stale
    new_ids = {e["id"] for e in new_entries}
    stale_entries = [e for e in stale_entries if e["id"] not in new_ids]

    print(f"  Carrying over {len(stale_entries)} stale items "
          f"({len(acted_ids)} pruned as acted-on).")

    # 4. Fetch tag stats
    print("Fetching tag stats from recent archives...")
    frequent_tags, recent_tags = fetch_tag_stats()
    print(f"  Frequent: {frequent_tags[:5]}{'...' if len(frequent_tags) > 5 else ''}")
    print(f"  Recent: {recent_tags}")

    # 5. Write batch (new items first, then stale)
    all_docs = new_entries + stale_entries
    batch = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_fetched_since": datetime.now(timezone.utc).isoformat(),
        "total_later_count": total_count,
        "frequent_tags": frequent_tags,
        "recent_tags": recent_tags,
        "documents": all_docs,
    }

    with open(BATCH_FILE, "w") as f:
        json.dump(batch, f, indent=2)

    clear_acted()

    print(f"\nWrote {len(all_docs)} documents to {BATCH_FILE}")
    print(f"  ({len(new_entries)} fresh + {len(stale_entries)} stale)")


if __name__ == "__main__":
    main()
