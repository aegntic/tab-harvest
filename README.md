# tab-harvest

Extract all details and actionable knowledge from every open browser tab plus
their best next-tier links. Video-first: YouTube tabs get full metadata,
chapters, and complete transcripts; X/Twitter tabs get tweet/thread
extraction. Every run also builds an interconnected, interactive knowledge
graph (self-contained HTML, works offline).

Built for [Hermes Agent](https://github.com/NousResearch/hermes-agent) but
works anywhere a SKILL.md-convention agent runs.

## What it does

1. Attaches over CDP to your already-running browser (read-only: never
   navigates, clicks, or closes your tabs)
2. Tier 0: every open tab dumped structured: title, description, headings,
   code, tables, text, links. YouTube tabs become video records with
   transcripts (yt-dlp primary engine, three browser fallbacks). X tabs
   become tweet lists with engagement and media.
3. Tier 1: the best links each tab points at, scored (watch/status URLs
   rank 12/10, so the next tier is more videos and threads), fetched
   cookie-bearing
4. Knowledge graph: nodes (tabs, videos, pages, tweets, channels, authors,
   topics) + edges (links_to, authored_by, mentions, same_as) rendered into
   a dark-observatory interactive graph.html: glow-sprite nodes, gradient
   edges, search, kind filters, detail panel with human-formatted metadata.
   Enrichable: add concept/action/question nodes and semantic edges, then
   re-render.

## Quick start

```bash
# once per machine
uv venv .venv && uv pip install --python .venv/bin/python playwright
.venv/bin/playwright install chromium   # driver only; never launches your browser

# your browser needs a CDP port (relaunch recipe in SKILL.md)
curl -s http://127.0.0.1:9222/json/version

# run
.venv/bin/python scripts/harvest.py --port 9222 --out ~/harvests/manual
```

Outputs land in the harvest dir: `harvest.md`, `harvest.json`,
`graph.json`, `graph.html` (the interactive graph; just open it).

## Files

- `SKILL.md` — full workflow, bring-up recipes, agent distillation protocol,
  design contract for the graph presentation
- `scripts/harvest.py` — the two-tier CDP harvester (YouTube transcript
  waterfall: yt-dlp → in-page timedtext → static refetch → transcript-panel
  scrape; X tweet extraction; tier-1 scoring)
- `scripts/graph_builder.py` — payload → graph.json + graph.html renderer;
  `--refresh` re-renders agent-enriched graphs

## Requirements

- Python 3.11+, playwright (CDP client), yt-dlp on PATH for transcripts
- Chromium/Chrome running with `--remote-debugging-port`

## License

MIT
