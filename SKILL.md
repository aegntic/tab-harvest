---
name: tab-harvest
description: "Extract all details and actionable knowledge from every open browser tab plus their best next-tier links, video-first: YouTube tabs get full metadata, chapters, and complete transcripts; X/Twitter tabs get tweet/thread extraction; tier-1 scoring surfaces more videos and threads from every page. Attaches over CDP to the user's already-running browser, read-only. Use when the user says harvest my tabs, distill my browser session, extract from open tabs/videos, or wants knowledge captured before closing tabs."
tags: [browser, cdp, tabs, harvest, distill, knowledge, youtube, x, video, transcript]
---

# Tab Harvest (video-first)

Two-tier browser knowledge extraction, read-only on the user's session:
**tier 0** = every open tab's structured content (pages fully; YouTube tabs as
video + transcript; X tabs as tweets); **tier 1** = the best links each tab
points at — watch/status URLs score 12/10, so the next tier is more videos
and threads, not nav chrome.

## Prerequisites (once per machine)

```bash
uv venv ~/.hermes/shared/skills/tab-harvest/.venv
uv pip install --python ~/.hermes/shared/skills/tab-harvest/.venv/bin/python playwright
~/.hermes/shared/skills/tab-harvest/.venv/bin/playwright install chromium  # driver only
```

## Bring-up (user's real browser)

CDP port must be open on the user's Chromium:

```bash
curl -s http://127.0.0.1:9222/json/version || echo "no CDP"
```

If no CDP: warn that relaunching closes their windows/PWAs, then

```bash
pids=$(pgrep -x chromium) && kill $pids; sleep 2
rm -f ~/.config/chromium/SingletonLock
/usr/lib/chromium/chromium --remote-debugging-port=9222 \
  --user-data-dir=$HOME/.config/chromium --password-store=gnome-libsecret \
  --no-first-run --restore-last-session about:blank
```

`--restore-last-session` reopens the user's tabs. YouTube transcripts and X
tweets both depend on the logged-in context — this is why the skill attaches
to the real browser instead of fetching headless.

## Run

```bash
SKILL=~/.hermes/shared/skills/tab-harvest
$SKILL/.venv/bin/python $SKILL/scripts/harvest.py --port 9222 --out ~/harvests/manual
```

Flags: `--max-per-tab N` (4), `--max-total N` (24), `--allow-tabs` opens
throwaway tabs for JS-only content (X status pages ALWAYS need it; budget
`--tab-budget` 6; tabs are closed after). Video bump: raise `--max-total` to
~40 for video-heavy sessions. Stdout = one JSON line with counts + paths.

### Video pipeline (YouTube)

1. Tab matches watch/shorts/live/youtu.be → extract
   `ytInitialPlayerResponse.videoDetails` in-page: title, channel, length,
   views, description, keywords, captionTracks.
2. Transcript, in order until one succeeds:
   a. **yt-dlp** (`/usr/bin/yt-dlp --skip-download --write-subs
      --write-auto-subs --sub-langs en.* --sub-format json3/vtt`) — primary
      engine; handles YouTube's empty-timedtext tightening, consent, tokens.
      Parsed from json3 or VTT into ~300-char timestamped paragraphs.
   b. In-page `fetch(baseUrl + '&fmt=json3')` inside the live YouTube tab.
   c. Static refetch of the watch page + fresh caption baseUrl.
   d. Throwaway tab: expand description ("...more"), click "Show transcript",
      scrape `ytd-transcript-segment-renderer` (budgeted by --allow-tabs).
3. Chapters parsed from description timestamps.
4. Video with no captions at all → `TRANSCRIPT: unavailable (reason)` — never
   fabricated. 2-hour ambient videos with zero speech legitimately fail here.

### X pipeline

Timeline/search/Status tabs: extract up to 40 `article[data-testid="tweet"]`
(text, author, datetime, engagement aria-label, media, outbound links,
permalink). Logged-out shells yield zero tweets — flagged in output, not
papered over. Tier-1 `status` links always go through a budgeted real tab
(X static HTML is useless).

## Agent workflow after harvest

Every run produces FOUR outputs in the harvest dir:
`harvest.md` (raw dump), `harvest.json` (sidecar), `graph.json` (nodes/edges),
`graph.html` (interactive graph — open in any browser, works offline).

**graph.html design contract (dark observatory, non-negotiable):**
ink `#0b0e14` canvas + radial vignette; harmonized kind palette (video coral,
X cyan, page green, channel gold, topics purple, actions amber); pre-rendered
radial-gradient glow sprites (never flat dots); curved edges with endpoint-
color gradients, alpha ≥ .42 resting, hover/selection boost to .8+; labels
upright 11.5px sans with dark rounded backing chips; twin duplicates render
smaller + dashed ring + no standing label; detail panel: color eyebrow →
title → link → human-formatted metadata (411.9M views, 0:19, "captured") →
transcript pull-quote → connection list with verb labels ("by", "mentions");
kind pills double as legend + filters with counts; header shows formatted
harvest date, tabular-numeral stats, `/` search focus, Esc closes.
Motion: staggered fade-in, hover ring growth, neighborhood focus dimming —
all honoring prefers-reduced-motion. No AI tells: no purple-on-purple, no
neon, no italic mono labels, no raw schema keys in the panel.

1. Read `harvest.md` fully; `harvest.json` is the machine-readable sidecar
   (per-video: metadata + chapters + transcript paras).
2. Distill per source into `distilled/<tab-N>-<slug>.md`:
   - Videos: claims with timestamps ([12:34] …), techniques, tools mentioned,
     opinions, chapter-level outline, actionable takeaways
   - Threads/tweets: the argument, the numbers, who said it, outbound sources
   - Pages: facts, concepts (one sentence + URL), actionable items, quotes
3. **Enrich the graph** (this is the interconnection step): append nodes to
   `graph.json` — `concept` (distilled idea), `action` (ranked todo),
   `question` (open thread) — and semantic edges to the sources that
   support them (`{"source": "<node-id>", "target": "concept:<slug>",
   "type": "semantic"}`). Then re-render:
   `scripts/graph_builder.py --refresh graph.json`
   Open graph.html: concepts cluster the sources they came from; topics
   bridge videos/tweets/pages sharing vocabulary; channels/authors group
   their work; links_to shows the discovery path you took.
4. Cross-tab `distilled/INDEX.md`: themes across sources, merged deduped
   action list ranked by impact, contradictions, open questions.
5. Report: counts (tabs → videos/transcripts/tweets → tier-1 → graph
   nodes/edges), 10 highlights, output paths (including graph.html), and
   extraction gaps stated honestly.

## Limits

- Transcript via in-page fetch fails if captions are disabled on the video;
  static fallback fails on hard bot-walled refetches. Both are reported.
- X timelines only see loaded DOM — infinite scroll below the fold is missed
  unless the user scrolled. Tier-1 tweet tabs are capped by --tab-budget.
- Tab text capped at 18k chars. Read-only: existing tabs never navigated.
- YouTube rate-limits rapid caption fetches; keep --max-total sane (~40).

## Troubleshooting

- `connect_over_cdp` refused → port not bound ("Opening in existing browser
  session" means it never bound — kill all, verify count 0, relaunch).
- Zero tweets extracted → tab is a logged-out shell; reload logged-in or note gap.
- json3 empty from in-page fetch → captions disabled; try the video in a real
  tab with --allow-tabs (already the tier-1 tweet path), else mark unavailable.
- Playwright driver mismatch after system Chromium update → rerun
  `playwright install chromium`.
