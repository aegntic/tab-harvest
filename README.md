<div align="center">

<img src="assets/ae-logo.webp" width="96" alt="Aegntic logo" />

# Tab Harvest

**A free, open-source command-line tool that extracts knowledge from your open browser tabs — full YouTube transcripts, X/Twitter threads, clean page text — and renders an interactive knowledge graph. 100% local.**

[![CI](https://github.com/aegntic/tab-harvest/actions/workflows/ci.yml/badge.svg)](https://github.com/aegntic/tab-harvest/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-55b77e.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg)](https://www.python.org/downloads/)
[![Platforms](https://img.shields.io/badge/platforms-macOS%20%7C%20Linux%20%7C%20Windows-8b95a5.svg)](#requirements)

`browser tab extractor` · `YouTube transcript harvester` · `knowledge graph builder` · `local-first research tool`

</div>

---

## What is Tab Harvest?

Tab Harvest is a standalone CLI application that attaches **read-only** to your already-running Chromium browser over the Chrome DevTools Protocol (CDP) and harvests every open tab into structured, durable formats on your disk. It never launches a browser, never navigates away, never closes your tabs, and never sends data anywhere — extraction happens entirely on your machine.

It is video-first by design: YouTube tabs are captured as complete video records (metadata, chapters, and a **full timestamped transcript** pulled primarily by yt-dlp, with three browser-side fallbacks), X/Twitter tabs become structured tweet lists with authors, engagement, media, and outbound links, and ordinary pages are captured as clean text with headings, code blocks, and tables.

Every run also renders an **interactive knowledge graph** — a single self-contained HTML file (no CDN, works offline) where tabs, videos, tweets, channels, topics, and tier-1 links appear as glow-sprite nodes connected by gradient edges, searchable and filterable by kind.

## What does it output?

Every harvest writes four files into the output directory (default `~/harvests/<timestamp>/`):

| File | What it is |
|---|---|
| `harvest.md` | The complete raw dump in readable markdown — every tab, video transcript, tweet thread, and tier-1 fetch |
| `harvest.json` | Machine-readable sidecar with the same content, for scripting or agent distillation |
| `graph.json` | The knowledge-graph model (nodes + edges) — editable, then re-renderable with `tab-harvest graph --refresh` |
| `graph.html` | The interactive knowledge graph: dark-observatory theme, glow nodes, search, kind filters, detail panel |

## Quick start

```bash
# 1. Install (any of these; all end with `tab-harvest` on your PATH)
pipx install git+https://github.com/aegntic/tab-harvest
# or: uv tool install git+https://github.com/aegntic/tab-harvest
# or: git clone https://github.com/aegntic/tab-harvest && cd tab-harvest \
#      && python3 -m venv .venv && .venv/bin/pip install .

# 2. One-time driver setup (the CDP client; never launches your browser)
tab-harvest doctor   # checks python, yt-dlp, playwright, and your CDP port
pipx run playwright install chromium

# 3. Open your browser with a debugging port (recipes below), then:
tab-harvest harvest --port 9222 --out ~/harvests/first
```

Your browser needs a CDP port open. Full bring-up recipes for macOS, Linux, and Windows are printed by `tab-harvest doctor`; the short version for macOS Chrome:

```bash
# Quit Chrome fully first (Cmd+Q), then:
open -a "Google Chrome" --args --remote-debugging-port=9222 --restore-last-session
curl -s http://127.0.0.1:9222/json/version   # verify
```

Relaunching with `--restore-last-session` reopens your tabs; unsaved PWA windows may be closed — that's a browser relaunch side effect, not Tab Harvest (which itself never touches your windows).

## Commands

| Command | Purpose |
|---|---|
| `tab-harvest harvest` | Attach over CDP and harvest every open tab (+ tier-1 links) |
| `tab-harvest graph <file>` | Build the knowledge graph from a `harvest.json`, or re-render an enriched `graph.json` with `--refresh` |
| `tab-harvest doctor` | Dependency checks + platform-specific browser bring-up recipes |
| `tab-harvest --version` | Print the version |

Key `harvest` flags: `--port` (CDP port, default 9222), `--out` (output dir), `--max-per-tab` (tier-1 links per tab, default 4), `--max-total` (total tier-1 fetches, default 24), `--allow-tabs` (open a budget of throwaway tabs for JS-only content like X status pages), `--tab-budget` (default 6), `--timeout-ms` (default 15000).

## How it works

1. **Attach** — connects to `http://127.0.0.1:<port>` with Playwright's CDP client. Existing tabs are never navigated, clicked, or closed.
2. **Tier 0: every tab** — structured extraction: title, meta description, headings, code blocks, tables, main text (capped at 18k chars), and all outbound links. YouTube watch/shorts/live/youtu.be tabs additionally get `videoDetails` (channel, length, views, description, keywords, caption tracks) and the transcript waterfall: **yt-dlp** (json3/vtt, en-first) → in-page timedtext fetch → static watch-page refetch → budgeted transcript-panel scrape. Chapters are parsed from description timestamps. X tabs get up to 40 tweets per tab.
3. **Tier 1: best links** — each tab's links are scored; watch/status URLs rank highest (12/10), so the next tier is more videos and threads instead of navigation chrome. Top scorers are fetched cookie-bearing via the browser's request context; JS-only pages optionally go through budgeted throwaway tabs (opened and closed, never your originals).
4. **Graph** — `graph_builder` turns the payload into nodes (tab, video, tweet, page, channel, author, topic) and typed edges (`links_to`, `authored_by`, `mentions`, `same_as`), rendered into the offline `graph.html`. The graph is **enrichable**: append `concept` / `action` / `question` nodes and `semantic` edges to `graph.json`, then re-render with `tab-harvest graph --refresh`.

## Use cases

- **Research triage** — 40 open tabs at the end of a session become one markdown dossier plus a visual map, instead of bookmark chaos.
- **Video note-taking** — full transcripts with `[hh:mm:ss]` timestamps and chapter outlines for every YouTube lecture in your session.
- **Thread archiving** — X/Twitter discussions preserved locally (text, author, engagement, media) before they scroll away.
- **Agent input** — `harvest.json` is a clean, complete context payload for LLM distillation; `SKILL.md` ships a full agent workflow (distillation protocol + graph enrichment) for SKILL.md-convention agents like [Hermes Agent](https://github.com/NousResearch/hermes-agent).
- **CI / batch** — the CLI is deterministic, offline, and pipeable (one JSON line to stdout with counts + paths).

## Requirements

- Python 3.11+ (playwright and yt-dlp are installed automatically as dependencies)
- A Chromium-based browser (Chrome, Chromium, Brave, Edge, Arc) running with `--remote-debugging-port`. Firefox and Safari are not supported — they don't implement CDP.
- ~200 MB for the Playwright driver download (one-time)

## Honest limits

Stated plainly, because tools that hide their limits waste your time:

- Transcripts fail on videos with **no captions at all** (e.g. 2-hour ambient videos with zero speech) — reported as `TRANSCRIPT: unavailable (reason)`, never fabricated.
- X timelines only see the **loaded DOM** — tweets below the infinite-scroll fold are missed unless you scrolled.
- Tab text is capped at 18k characters per tab.
- YouTube rate-limits rapid caption fetches; keep `--max-total` sane (~40 for video-heavy sessions).
- The CDP relaunch step restores your session but may close unsaved PWA windows.
- Tier-1 tweet pages always need `--allow-tabs` (X static HTML is a logged-out shell).

## FAQ

**Is Tab Harvest free?**
Yes — MIT-licensed open source. No account, no subscription, no quota, no telemetry. `pipx install` and go.

**Does it send my data anywhere?**
No. Everything runs locally over CDP; output files land on your disk. There is no server component and nothing phones home.

**Can it mess up my tabs?**
No. Attachment is read-only: existing tabs are never navigated, reloaded, or closed. With `--allow-tabs`, new throwaway tabs are opened for JS-only pages and closed after.

**How does it get YouTube transcripts?**
yt-dlp is the primary engine (handles consent walls and token tightening); fallbacks are an in-page timedtext fetch inside your logged-in tab, a static watch-page refetch, and a budgeted transcript-panel scrape in a real tab.

**Which browsers work?**
Any Chromium browser with a debugging port: Chrome, Chromium, Brave, Edge, Arc. Not Firefox or Safari.

**Can I use it with an AI agent?**
Yes — that's its origin. `SKILL.md` defines the full agent workflow (distillation into per-source notes, cross-tab index, graph enrichment with concept/action/question nodes). Any SKILL.md-convention agent can follow it; humans can ignore it entirely.

**Does the knowledge graph need the internet?**
No. `graph.html` is fully self-contained vanilla JS with zero CDN dependencies — open it offline, forever.

## For AI agents and training pipelines

`SKILL.md` in this repo is the canonical agent-facing workflow. `llms.txt` at the repo root summarizes the project for LLM consumption. The `examples/` directory contains a real harvested session (YouTube video + tier-1 videos) with its rendered graph — open `examples/graph-youtube.html` in any browser, no setup, to see exactly what output looks like.

## Repository layout

```
├── src/tab_harvest/        # the Python package (harvest.py, graph_builder.py, cli.py)
├── scripts/dev/            # headless CDP test rigs (verify without touching your browser)
├── tests/test_smoke.py     # CLI + graph-builder smoke tests (run by CI)
├── examples/               # a real harvest + rendered knowledge graph
├── SKILL.md                # agent workflow (distillation + graph enrichment)
├── llms.txt                # LLM-facing project summary
├── index.html + assets/    # the project page (served via GitHub Pages)
└── pyproject.toml          # packaging (console script: tab-harvest)
```

## License

[MIT](LICENSE) — free to use, modify, and redistribute. Built by [Aegntic](https://aegntic.ai) ([@aegntic](https://github.com/aegntic)).
