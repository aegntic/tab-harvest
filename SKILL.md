---
name: tab-harvest
description: "Use when the user says harvest my tabs, distill my browser session, or wants knowledge extracted from open tabs: attaches over CDP read-only, dumps every tab structured (YouTube tabs as video + full transcript, X tabs as tweets), scores and fetches the best tier-1 links, and renders an interactive knowledge graph."
tags: [browser, cdp, tabs, harvest, distill, knowledge, youtube, x, video, transcript]
---

# Tab Harvest (video-first)

Two-tier browser knowledge extraction, read-only on the user's session:
**tier 0** = every open tab's structured content (pages fully; YouTube tabs as
video + transcript; X tabs as tweets); **tier 1** = the best links each tab
points at - watch/status URLs score 12/10, so the next tier is more videos
and threads, not nav chrome.

Tab Harvest is a standalone pip-installable CLI. If `tab-harvest` is not on
PATH, install it first:

```bash
pipx install git+https://github.com/aegntic/tab-harvest
pipx run playwright install chromium   # CDP driver only; never launches the browser
```

## Prerequisites (once per machine)

```bash
tab-harvest doctor   # checks python, yt-dlp, playwright + prints OS-specific
                     # browser bring-up recipes (macOS / Linux / Windows)
```

## Bring-up (user's real browser)

CDP port must be open on the user's Chromium:

```bash
curl -s http://127.0.0.1:9222/json/version || echo "no CDP"
```

If no CDP: warn that relaunching closes their windows/PWAs, then
`tab-harvest doctor` prints the exact relaunch recipe for their OS. Linux
reference:

```bash
pids=$(pgrep -x chromium) && kill $pids; sleep 2
rm -f ~/.config/chromium/SingletonLock
/usr/lib/chromium/chromium --remote-debugging-port=9222 \
  --user-data-dir=$HOME/.config/chromium --password-store=gnome-libsecret \
  --no-first-run --restore-last-session about:blank
```

`--restore-last-session` reopens the user's tabs. YouTube transcripts and X
tweets both depend on the logged-in context - this is why the skill attaches
to the real browser instead of fetching headless.

## Run

```bash
tab-harvest harvest --port 9222 --out ~/harvests/manual
# fallback if the console script is missing:
python -m tab_harvest harvest --port 9222 --out ~/harvests/manual
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
      --write-auto-subs --sub-langs en.* --sub-format json3/vtt`) - primary
      engine; handles YouTube's empty-timedtext tightening, consent, tokens.
      Parsed from json3 or VTT into ~300-char timestamped paragraphs.
   b. In-page `fetch(baseUrl + '&fmt=json3')` inside the live YouTube tab.
   c. Static refetch of the watch page + fresh caption baseUrl.
   d. Throwaway tab: expand description ("...more"), click "Show transcript",
      scrape `ytd-transcript-segment-renderer` (budgeted by --allow-tabs).
3. Chapters parsed from description timestamps.
4. Video with no captions at all → `TRANSCRIPT: unavailable (reason)` - never
   fabricated. 2-hour ambient videos with zero speech legitimately fail here.

### X pipeline

Timeline/search/Status tabs: extract up to 40 `article[data-testid="tweet"]`
(text, author, datetime, engagement aria-label, media, outbound links,
permalink). Logged-out shells yield zero tweets - flagged in output, not
papered over. Tier-1 `status` links always go through a budgeted real tab
(X static HTML is useless).

## Agent workflow after harvest

Every run produces FOUR outputs in the harvest dir:
`harvest.md` (raw dump), `harvest.json` (sidecar), `graph.json` (nodes/edges),
`graph.html` (interactive graph - open in any browser, works offline).

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
Motion: staggered fade-in, hover ring growth, neighborhood focus dimming -
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
   `graph.json` - `concept` (distilled idea), `action` (ranked todo),
   `question` (open thread) - and semantic edges to the sources that
   support them (`{"source": "<node-id>", "target": "concept:<slug>",
   "type": "semantic"}`). Then re-render:
   `tab-harvest graph --refresh graph.json`
   Open graph.html: concepts cluster the sources they came from; topics
   bridge videos/tweets/pages sharing vocabulary; channels/authors group
   their work; links_to shows the discovery path you took.
4. Cross-tab `distilled/INDEX.md`: themes across sources, merged deduped
   action list ranked by impact, contradictions, open questions.
5. Report: counts (tabs → videos/transcripts/tweets → tier-1 → graph
   nodes/edges), 10 highlights, output paths (including graph.html), and
   extraction gaps stated honestly.

- Silencing tabs: this Chromium build's CDP has NO `Page.setAudioMuted`
  ("wasn't found"). What works: `page.evaluate` a snippet that pauses every
  `video,audio` where `!m.paused && !m.ended` — verified to stop all audio.
- Reopening a run's graph.html via CDP: match the EXACT `file://<run-dir>/graph.html`
  URL. `url.endswith("graph.html")` grabs older runs' still-open graph tabs and
  you screenshot/reload the wrong one (bit the 2026-10-27 run).
- Curated maps beat force graphs for legibility: 94-node force layout read as a
  hairball; a hand-placed SVG (5 themes × 3-5 concepts, source-number tags,
  legend table) read at a glance. Generate with fixed coordinates, then verify
  by screenshot + vision pass and hand-place colliding pills.

## Fleet notes (verified 2026-10-27 run, window-scoped)

- To harvest ONE window only (e.g. a dedicated "tabs2harvest" video queue) without
  dumping PII tabs (Gmail/Stripe/LinkedIn) to disk: the CLI always harvests every
  tab — instead attach with playwright, map pages via CDP
  `Browser.getWindowForTarget`, and run a scoped driver that imports this package's
  own functions (TIER0_JS, parse_watch_html, yt_dlp_transcript, yt_transcript_static,
  transcript_via_new_tab, chapters_from_description). Write harvest.json/harvest.md
  in the standard shape, then graph_builder.py <json> --out <dir> still works.
- Dedupe repeated video tabs by videoId before transcript pulls — a video open in 6
  tabs must cost one yt-dlp call, not six.
- Pitfall: a script-level `BUDGET = 3` decremented inside a function raises
  UnboundLocalError in Python (implicit local). Use `budget = [3]` and `budget[0] -= 1`.
- Chromium relaunch on Omarchy (verified twice): graceful `kill <main-pid>`, wait for
  proc count 0, `rm -f ~/.config/chromium/SingletonLock`, then
  `systemd-run --user /usr/lib/chromium/chromium --remote-debugging-port=9222
  --user-data-dir=~/.config/chromium --password-store=gnome-libsecret --no-first-run
  --restore-last-session about:blank` — CDP binds within ~2s and all windows/tabs
  restore (PWA app windows do not; separate-profile apps like ChatGPT are untouched).

- Driving NotebookLM ("Gemini Notebook" — notebook.google.com; notebooklm.google.com
  redirects there) over CDP works end to end: New notebook → `[aria-label="Add source"]`
  → "Upload files" tile → input[type=file] mounts; set_input_files ONE file per call in
  a loop (dialog closes after the first). Rename: click the title heading, fill the input
  that already holds the old title, Enter. TRAP: the "Discover sources" query box is the
  first visible empty input on the page — a blind fill+Enter submits a web-discovery
  query (results land as an unimported card, not as sources). Deleting a source: row
  More menu → "Remove source" → scoped `[role=dialog]` Delete confirm; re-locate buttons
  after every click (handles go stale on re-render). NotebookLM auto-titles from the
  first source's content and auto-writes a briefing into chat on upload.

- Self-adding knowledge bank: after every harvest, run the ingest contract in
  aegntic/intel-distillations (bank/SCHEMA.md): `python3 bank.py ingest <dir>`,
  write the synthesis draft (fNN citation map, `### update:` concept blocks,
  candidate-moves JSON), apply accepted blocks to wiki/, refresh HOT.md,
  `python3 bank.py verify` must PASS, commit `bank: ingest <date>`, push.
  github-d's weekly cron runs bank/sweep.sh to catch un-ingested ~/harvests dirs.

## Fleet notes (verified 2026-10-23 run)

- Skill name collides across external_dirs (shared + cldcde-private vault copy);
  `skill_view` refuses the bare name — read the shared SKILL.md from disk instead.
- CLI not on PATH (no pipx here) but the shared skill's `.venv` has the package
  installed: run everything via
  `~/.hermes/shared/skills/tab-harvest/.venv/bin/python -m tab_harvest <cmd>`
  (works for `doctor`, `harvest`, and `graph --refresh graph.json` re-render).
- Omarchy relaunch: `systemd-run --user /usr/bin/chromium --remote-debugging-port=9222
  --user-data-dir=~/.config/chromium ... --restore-last-session about:blank` inherits
  the Wayland session env; CDP bound within ~2s.
- Parallel distiller subagents on zai can HTTP 429 mid-batch; a child that dies after
  its write_file calls has still produced valid output — verify files on disk and
  re-dispatch only the gaps, don't redo the whole batch.
- Transcripts occasionally appear duplicated within a tab's range (harmless; distill
  from the first pass).

## Limits

- Transcript via in-page fetch fails if captions are disabled on the video;
  static fallback fails on hard bot-walled refetches. Both are reported.
- X timelines only see loaded DOM - infinite scroll below the fold is missed
  unless the user scrolled. Tier-1 tweet tabs are capped by --tab-budget.
- Tab text capped at 18k chars. Read-only: existing tabs never navigated.
- YouTube rate-limits rapid caption fetches; keep --max-total sane (~40).

## Troubleshooting

- `connect_over_cdp` refused → port not bound ("Opening in existing browser
  session" means it never bound - kill all, verify count 0, relaunch).
- Zero tweets extracted → tab is a logged-out shell; reload logged-in or note gap.
- json3 empty from in-page fetch → captions disabled; try the video in a real
  tab with --allow-tabs (already the tier-1 tweet path), else mark unavailable.
- Playwright driver mismatch after system Chromium update → rerun
  `playwright install chromium`.
