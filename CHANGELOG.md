# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-22

### Added

- Card-based triage UI with keyboard shortcuts (a/s/k/t/o/arrows) and swipe gestures
- AI-generated personalized pitches (overview, why read, why skip) via Claude Haiku
- Reader persona support for personalized pitch generation
- Tag & Archive workflow with frequent/recent tag picker and custom tag input
- Light/dark theme toggle with Radix color scales, saved to localStorage
- Option-click text selection on cards
- Incremental batch processing: new items first, stale backlog carried over, acted-on items pruned
- Backlog mode: when no new items exist, fetches next unprocessed batch from full Later list
- "Load next batch" button when all cards are triaged
- Session persistence via triage-acted.json
- Tag frequency/recency derived from recently archived documents
- Zero-dependency web server (Python stdlib http.server)
- Threaded server so batch generation doesn't block other requests
- launchd plist for nightly batch prep at 3am
- AGPL-3.0 license
