# Readwise Triage

A local web app for fast triage of your Readwise Reader Later list. AI-generated personalized pitches (via Claude Haiku) tell you why each item is worth reading or skipping. Actions are instant — no LLM in the loop during triage.

![Screenshot of Readwise Triage showing a card with title, overview, why-read and why-skip pitches](screenshot.png)

## How It Works

**Overnight (or on-demand):** `triage-prep.py` fetches your Later list, generates personalized pitches using Claude Haiku and your reader persona, and writes everything to `triage-batch.json`.

**Morning triage:** `triage-app.py` serves a local web app. Cards appear one at a time with title, metadata, overview, and why-read/why-skip pitches. You act on each card with a keypress or swipe, then move to the next.

## Setup

### Prerequisites

- Python 3.10+
- [Readwise CLI](https://github.com/readwise/readwise-cli) (`readwise` in PATH)
- An Anthropic API key stored in macOS Keychain:

```sh
security add-generic-password -a readwise-triage \
  -s readwise-triage-anthropic-api-key -w YOUR_KEY -U
```

### Reader Persona (optional but recommended)

Create `reader_persona.md` in the project root describing your reading interests, research areas, and what matters to you. This is sent to Haiku during pitch generation to personalize the why-read/why-skip analysis.

## Usage

### Generate a batch

```sh
python3 triage-prep.py
```

Fetches up to 20 new items from your Later list (configurable via `FRESH_BATCH_SIZE` at the top of the script), generates pitches, and merges with any unprocessed items from prior batches.

On subsequent runs, the script:
- Only generates pitches for new items (no re-processing)
- Prunes items you've already acted on
- Falls back to the full Later list when there are no new items (backlog mode)

### Start the triage app

```sh
python3 triage-app.py
```

This starts a local server and automatically opens your browser to `http://localhost:5111`. No dependencies — uses Python's built-in HTTP server. Press `Ctrl-C` in the terminal to stop the server when you're done.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `a` | Archive |
| `s` | Shortlist |
| `k` | Keep in Later |
| `t` | Tag & Archive (opens tag picker) |
| `o` | Open in Reader |
| `→` | Skip to next (no action) |
| `←` | Go back to previous |
| `Esc` | Close tag picker |
| `Enter` | Confirm tags |

### Swipe gestures

- **Left** = Archive
- **Right** = Shortlist
- **Down** = Keep

### Text selection

Hold **Option** while clicking/dragging to select text from cards.

### Theme

Click the sun/moon icon in the status bar to toggle light/dark. Preference is saved.

### Tag picker

Press `t` to open. Shows your most frequently used tags (derived from recent archived items) plus recently used tags. Type custom tags in the text field (comma-separated). Select tags and press Enter or click Archive.

### Next batch

When you finish all cards, click **Load next batch**. The app runs `triage-prep.py` in the background, generates pitches for the next set of items, and loads them.

## Scheduling nightly prep

To have batches ready each morning:

```sh
cp com.readwise.triage-prep.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.readwise.triage-prep.plist
```

Runs `triage-prep.py` daily at 3:00 AM. Logs to `triage-prep.log`.

To unload:

```sh
launchctl unload ~/Library/LaunchAgents/com.readwise.triage-prep.plist
```

## Files

| File | Purpose |
|------|---------|
| `triage-prep.py` | Batch generator — fetches docs, calls Haiku, writes JSON |
| `triage-app.py` | Local web server (zero dependencies) |
| `triage-app.html` | Single-page triage UI |
| `triage-batch.json` | Current batch (generated, not committed) |
| `triage-acted.json` | IDs of items acted on in current session |
| `reader_persona.md` | Your reading profile for personalized pitches |
| `com.readwise.triage-prep.plist` | launchd schedule for nightly prep |
| `CLAUDE.md` | Project instructions for Claude Code |

## Configuration

Edit the constants at the top of `triage-prep.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `FRESH_BATCH_SIZE` | 20 | Max items to fetch per prep run |
| `MODEL` | claude-haiku-4-5-20251001 | Haiku model for pitch generation |
| `TAG_ARCHIVE_SAMPLE` | 100 | Archived docs to sample for tag stats |
