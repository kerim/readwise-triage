# Readwise Project

## Persona

The reader persona file is at `reader_persona.md` in the project root. Load it at the start of any triage or recommendation session to personalize pitches and prioritization.

## Readwise CLI

This project uses the `readwise` CLI to interact with Readwise and Reader. All commands use `--json` for machine-readable output.

### Triage Commands

**List inbox documents:**
```
readwise reader-list-documents --location new --limit 10 --response-fields url,title,author,category,word_count,reading_time,summary,site_name,published_date,saved_at
```

**Get full document details (for deeper pitch):**
```
readwise reader-get-document-details --document-id <id>
```

**Move documents:**
```
readwise reader-move-documents --document-ids <id> --location <archive|later|shortlist|new>
```

**Add tags:**
```
readwise reader-add-tags-to-document --document-id <id> --tag-names <tag1,tag2>
```

**Remove tags:**
```
readwise reader-remove-tags-from-document --document-id <id> --tag-names <tag1,tag2>
```

### Other Useful Commands

- `readwise reader-list-tags` -- list all Reader tags
- `readwise reader-search-documents --query <query>` -- hybrid search across Reader
- `readwise readwise-search-highlights --query <query>` -- search highlights
- `readwise reader-list-documents --location later --limit 10` -- browse Later list
- `readwise reader-list-documents --tag <tag> --limit 10` -- filter by tag

### Notes

- Location values: `new` (inbox), `later`, `shortlist`, `archive`, `feed`
- `reader-list-documents` returns most-recently-saved first
- `reader-move-documents` accepts multiple IDs (max 50) and is rate-limited to 20 calls/min
- `response-fields` reduces token usage; `id` is always included
