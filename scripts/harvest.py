#!/usr/bin/env python3
"""tab-harvest - dump every open browser tab (tier 0) + best links (tier 1).

VIDEO-FIRST: YouTube tabs get videoDetails + chapters + full transcript
(captions fetched inside the logged-in page context). X/Twitter tabs get
tweet/thread extraction (text, author, engagement, media, outbound links).
Tier-1 scoring boosts watch/status URLs so the next tier is more videos and
threads, not nav chrome.

Attaches over CDP to an ALREADY-RUNNING browser (never launches one).
Read-only: existing tabs are never navigated, clicked, or closed.
Writes markdown raw dump + JSON sidecar; distillation is the agent's job.

Usage:
  .venv/bin/python harvest.py [--port 9222] [--out DIR] [--max-per-tab 4]
                              [--max-total 24] [--allow-tabs] [--tab-budget 6]

Stdout: one JSON line with counts + output paths.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

TIER0_JS = r"""
(() => {
  const meta = (n) => { const el = document.querySelector(`meta[name="${n}"], meta[property="og:${n}"]`);
    return el ? (el.getAttribute('content') || '') : ''; };
  const abs = (h) => { try { return new URL(h, location.href).href; } catch { return null; } };
  const bad = /^(mailto:|tel:|javascript:|#)/i;
  const seen = new Set();
  const links = [];
  for (const a of document.querySelectorAll('a[href]')) {
    const href = abs(a.getAttribute('href'));
    if (!href || bad.test(a.getAttribute('href'))) continue;
    if (!/^https?:/i.test(href)) continue;
    if (seen.has(href)) continue;
    seen.add(href);
    links.push({ text: (a.innerText || a.getAttribute('aria-label') || '').trim().slice(0, 140), href });
  }
  const headings = [...document.querySelectorAll('h1,h2,h3')].slice(0, 60)
    .map(h => ({ level: +h.tagName[1], text: h.innerText.trim().slice(0, 160) }))
    .filter(h => h.text);
  const code = [...document.querySelectorAll('pre')].slice(0, 15)
    .map(c => c.innerText.slice(0, 1200));
  const tables = [...document.querySelectorAll('table')].slice(0, 8).map(t => {
    const rows = [...t.querySelectorAll('tr')].slice(0, 25).map(tr =>
      [...tr.querySelectorAll('th,td')].map(c => c.innerText.trim().slice(0, 120)));
    return rows;
  }).filter(r => r.length);
  const main = document.querySelector('article, main, [role=main]') || document.body;
  return {
    url: location.href, title: document.title,
    description: meta('description'), lang: document.documentElement.lang || '',
    text: main.innerText.slice(0, 18000),
    headings, links: links.slice(0, 400), code, tables,
    linkCount: links.length,
  };
})()
"""

YT_JS = r"""
(() => {
  const pr = window.ytInitialPlayerResponse || null;
  const vd = pr?.videoDetails || {};
  const caps = pr?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
  return {
    videoId: vd.videoId || new URLSearchParams(location.search).get('v') || '',
    title: vd.title || document.title.replace(/ - YouTube$/, ''),
    author: vd.author || '', channelId: vd.channelId || '',
    lengthSeconds: +vd.lengthSeconds || 0, viewCount: +vd.viewCount || 0,
    description: vd.shortDescription || '',
    keywords: vd.keywords || [],
    captionTracks: caps.map(c => ({baseUrl: c.baseUrl, lang: c.languageCode, kind: c.kind || ''})),
  };
})()
"""

X_JS = r"""
(() => {
  const tweets = [];
  for (const a of document.querySelectorAll('article[data-testid="tweet"]')) {
    const text = a.querySelector('[data-testid="tweetText"]')?.innerText || '';
    const time = a.querySelector('time')?.getAttribute('datetime') || '';
    const perma = [...a.querySelectorAll('a[href*="/status/"]')]
      .map(x => x.href.split('?')[0])
      .find(h => /\/status\/\d+$/.test(h)) || '';
    const author = perma ? perma.split('://')[1].split('/status/')[0] : '';
    const group = a.querySelector('div[role="group"]');
    const stats = group ? (group.getAttribute('aria-label') || '') : '';
    const media = [...a.querySelectorAll('img[src*="pbs.twimg.com/media"]')].map(i => i.src);
    const links = [...a.querySelectorAll('a[href^="http"]')]
      .map(l => l.href).filter(h => !/(?:x|twitter)\.com\//.test(h));
    if (text || media.length)
      tweets.push({ author, time, text: text.slice(0, 2000), stats, media, links, href: perma });
  }
  return { url: location.href, tweetCount: tweets.length, tweets: tweets.slice(0, 40) };
})()
"""

SKIP_URL = re.compile(r"^(chrome|devtools|edge|about|file|view-source):", re.I)
UTILITY_HREF = re.compile(
    r"/(login|logout|signin|signup|register|share|subscribe|newsletter|privacy|terms|cookie"
    r"|feed|rss|atom|print|embed|channel|playlists|library|history|settings)"
    r"|[?&](utm_|share=|replytocom)|/i/|/hashtag/|/search\?", re.I
)
YT_WATCH_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)([\w-]{11})", re.I
)
X_STATUS_RE = re.compile(r"(?:(?<![\w.])(?:x|twitter)\.com)/(\w+)/status/(\d+)", re.I)
X_ANY_RE = re.compile(r"(?<![\w.])(?:x|twitter)\.com/", re.I)
TS_LINE_RE = re.compile(r"(\d{1,2}:\d{2}(?::\d{2})?)")


def registrable(host: str) -> str:
    parts = host.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def score_link(link: dict, base_url: str, title_words: set[str]) -> int:
    href = link["href"]
    try:
        sp = urlsplit(href)
        bsp = urlsplit(base_url)
    except ValueError:
        return -100
    if UTILITY_HREF.search(href):
        return -100
    if YT_WATCH_RE.search(href):
        return 12  # tier-1 gold: another video
    if X_STATUS_RE.search(href):
        return 10  # a tweet/thread
    if not sp.path or sp.path == "/":
        return -100
    s = 0
    if registrable(sp.netloc) == registrable(bsp.netloc):
        s += 3
    slug = (sp.path.rstrip("/").split("/")[-1] or "").replace("-", " ").replace("_", " ")
    words = set(re.findall(r"[a-z]{3,}", slug.lower()))
    s += min(3, len(words & title_words))
    depth = sp.path.strip("/").count("/")
    if 1 <= depth <= 3:
        s += 1
    if len(link.get("text") or "") > 14:
        s += 1
    if re.search(r"\.(pdf|zip|png|jpe?g|gif|webp|mp4|mp3)$", sp.path, re.I):
        s -= 8
    return s


def watch_url(href: str) -> str | None:
    m = YT_WATCH_RE.search(href)
    if not m:
        return None
    return f"https://www.youtube.com/watch?v={m.group(1)}"


def brace_json(s: str, start: int) -> str | None:
    """Extract a JSON object/array substring starting at s[start] via brace matching."""
    if start >= len(s) or s[start] not in "{[":
        return None
    open_c, close_c = s[start], "}" if s[start] == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None


def parse_watch_html(html: str) -> dict | None:
    """Extract videoDetails + captionTracks from server-rendered watch HTML."""
    vd = {}
    i = html.find('"videoDetails"')
    if i >= 0:
        obj = brace_json(html, html.find("{", i))
        if obj:
            try:
                vd = json.loads(obj)
            except Exception:
                vd = {}
    caps = []
    j = html.find('"captionTracks"')
    if j >= 0:
        arr = brace_json(html, html.find("[", j))
        if arr:
            try:
                caps = json.loads(arr)
            except Exception:
                caps = []
    if not vd and not caps:
        return None
    return {"videoDetails": vd, "captionTracks": caps}


def chapters_from_description(desc: str) -> list[dict]:
    out = []
    for line in desc.splitlines():
        m = TS_LINE_RE.search(line)
        if not m:
            continue
        ts = m.group(1)
        title = line.replace(ts, "").strip(" ---•\t")
        if title:
            out.append({"ts": ts, "title": title[:140]})
    return out[:40]


def fmt_ts(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_json3(raw: str) -> list[dict]:
    """YouTube json3 captions -> merged paragraphs [{t, text}] with timestamps."""
    try:
        events = json.loads(raw).get("events", [])
    except Exception:
        return []
    segs_out = []
    for ev in events:
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
        if text:
            segs_out.append((ev.get("tStartMs", 0) / 1000.0, text))
    paras, cur_t, buf, size = [], None, [], 0
    for t, text in segs_out:
        if cur_t is None:
            cur_t = t
        buf.append(text)
        size += len(text)
        if size >= 300:
            paras.append({"t": round(cur_t, 1), "text": " ".join(buf)})
            cur_t, buf, size = None, [], 0
    if buf:
        paras.append({"t": round(cur_t or 0, 1), "text": " ".join(buf)})
    return paras


async def yt_transcript_page(page, tracks: list[dict]) -> tuple[list[dict] | None, str]:
    """Fetch transcript inside the live YouTube tab (carries its cookies)."""
    if not tracks:
        return None, "no-caption-tracks"
    pick = next((t for t in tracks if t.get("lang", "").startswith("en") and not t.get("kind")), None) \
        or next((t for t in tracks if not t.get("kind")), None) or tracks[0]
    url = pick["baseUrl"] + "&fmt=json3"
    try:
        res = await page.evaluate(
            "async (u) => { const r = await fetch(u); return {s: r.status, t: await r.text()}; }", url
        )
        if res["s"] == 200 and res["t"].strip():
            paras = parse_json3(res["t"])
            if paras:
                return paras, f"in-page({pick['lang']}{' auto' if pick.get('kind') else ''})"
    except Exception:
        pass
    return None, "in-page-fetch-empty"


async def yt_transcript_static(ctx, watch: str) -> tuple[list[dict] | None, str]:
    """Fallback: refetch the watch page, re-extract a fresh caption baseUrl, fetch it."""
    try:
        resp = await ctx.request.get(watch, timeout=15000, max_redirects=5)
        if not resp.ok:
            return None, f"static-watch-http-{resp.status}"
        html = await resp.text()
    except Exception:
        return None, "static-watch-failed"
    info = parse_watch_html(html)
    if not info or not info["captionTracks"]:
        return None, "static-no-caption-tracks"
    pick = info["captionTracks"][0]
    url = pick.get("baseUrl", "")
    if not url:
        return None, "static-no-baseurl"
    if "fmt=" not in url:
        url += "&fmt=json3"
    try:
        resp = await ctx.request.get(url, timeout=15000)
        if resp.ok:
            paras = parse_json3(await resp.text())
            if paras:
                return paras, "static-refetch"
    except Exception:
        pass
    return None, "static-transcript-fetch-failed"


def parse_vtt(raw: str) -> list[dict]:
    """Minimal VTT → [{t, text}] with rolling-caption dedupe."""
    paras, last_text = [], None
    ts_re = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})")
    for block in re.split(r"\n\s*\n", raw):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        text_lines, ts = [], None
        for l in lines:
            if "-->" in l:
                m = ts_re.search(l)
                if m:
                    h, mnt, s, _ms = map(int, m.groups())
                    ts = h * 3600 + mnt * 60 + s
            elif not l.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
                clean = re.sub(r"<[^>]+>", "", l).strip()
                if clean:
                    text_lines.append(clean)
        text = " ".join(text_lines).strip()
        if ts is not None and text and text != last_text:
            paras.append({"t": ts, "text": text})
            last_text = text
    return paras


def yt_dlp_transcript(url: str) -> tuple[list[dict] | None, str]:
    """yt-dlp caption extraction - the most reliable path (handles tokens/consent)."""
    import glob
    import os
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory(prefix="tabharvest-ytdlp-") as td:
        cmd = ["/usr/bin/yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
               "--sub-langs", "en.*,en", "--sub-format", "json3/vtt",
               "-o", os.path.join(td, "%(id)s"), url]
        try:
            subprocess.run(cmd, capture_output=True, timeout=90)
        except Exception:
            return None, "ytdlp-timeout"
        files = [f for f in glob.glob(os.path.join(td, "*")) if f.endswith((".json3", ".vtt"))]

        def rank(f: str) -> tuple:
            name = os.path.basename(f)
            manual = ".en." in name and "auto" not in name
            return (0 if manual else 1, name)

        files.sort(key=rank)
        if not files:
            return None, "ytdlp-no-subs"
        f = files[0]
        name = os.path.basename(f)
        raw = open(f, encoding="utf-8", errors="replace").read()
        if f.endswith(".json3"):
            paras = parse_json3(raw)
            return (paras, "ytdlp-json3-" + ("manual" if "auto" not in name else "auto")) if paras else (None, "ytdlp-empty")
        paras = parse_vtt(raw)
        return (paras, "ytdlp-vtt-" + ("manual" if "auto" not in name else "auto")) if paras else (None, "ytdlp-empty")


async def transcript_via_new_tab(ctx, url: str, timeout_ms: int) -> tuple[list[dict] | None, str]:
    """Open a THROWAWAY tab at the watch URL, pull the transcript, close it.

    Path 1: fresh in-page timedtext fetch (baseUrl is page-fresh here).
    Path 2: click the 'Show transcript' panel and scrape timestamped segments
    (survives the empty-timedtext tightening; works in logged-in contexts).
    Never touches the user's original tab.
    """
    page = await ctx.new_page()
    try:
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        try:
            raw = await page.evaluate(
                """(async () => {
                    const pr = window.ytInitialPlayerResponse || {};
                    const caps = pr?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
                    if (!caps.length) return null;
                    const pick = caps.find(c => (c.languageCode||'').startsWith('en')) || caps[0];
                    const r = await fetch(pick.baseUrl + '&fmt=json3');
                    const t = await r.text();
                    return t.trim() ? t : null;
                })()"""
            )
            if raw:
                paras = parse_json3(raw)
                if paras:
                    return paras, "tab-timedtext"
        except Exception:
            pass
        try:
            # YouTube hides "Show transcript" behind the expanded description
            await page.evaluate(
                """() => {
                    const b = [...document.querySelectorAll('tp-yt-paper-button, button')].find(b =>
                        /\\bmore\\b/i.test(b.getAttribute('aria-label')||'') || /^\\.\\.\\.$|^\\.\\.\\.more$/.test((b.innerText||'').trim()));
                    if (b) b.click();
                }"""
            )
            await page.wait_for_timeout(1200)
            clicked = await page.evaluate(
                """() => {
                    const b = [...document.querySelectorAll('button')].find(b =>
                        /show transcript/i.test((b.innerText||'') + ' ' + (b.getAttribute('aria-label')||'')));
                    if (b) { b.click(); return true; }
                    return false;
                }"""
            )
            if clicked:
                await page.wait_for_selector("ytd-transcript-segment-renderer", timeout=9000)
                await page.wait_for_timeout(900)
                segs = await page.evaluate(
                    """() => [...document.querySelectorAll('ytd-transcript-segment-renderer')].map(s => ({
                        ts: (s.querySelector('.segment-timestamp')?.innerText || '').trim(),
                        tx: (s.querySelector('.segment-text')?.innerText || '').trim()
                    }))"""
                )
                paras = []
                for s in segs:
                    parts = [p for p in s.get("ts", "").split(":") if p.isdigit()]
                    sec = sum(int(p) * 60 ** i for i, p in enumerate(reversed(parts))) if parts else 0
                    if s.get("tx"):
                        paras.append({"t": sec, "text": s["tx"]})
                if paras:
                    return paras, "tab-panel"
        except Exception:
            pass
        return None, "tab-no-transcript"
    finally:
        await page.close()


class TextHTML(HTMLParser):
    SKIP = ("script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "iframe")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.headings: list[dict] = []
        self._skip = 0
        self._h = 0
        self._hbuf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        if tag in ("h1", "h2", "h3") and not self._skip:
            self._h = int(tag[1]); self._hbuf = []
        if tag in ("p", "div", "li", "br", "tr") and not self._skip:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in ("h1", "h2", "h3") and self._h:
            text = " ".join("".join(self._hbuf).split())[:160]
            if text:
                self.headings.append({"level": self._h, "text": text})
            self._h = 0

    def handle_data(self, data):
        if self._skip:
            return
        if self._h:
            self._hbuf.append(data)
        else:
            self.out.append(data)


def html_to_struct(html: str) -> dict:
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    d = ""
    m = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']{0,400})', html, re.I)
    if m:
        d = m.group(1)
    p = TextHTML()
    try:
        p.feed(html)
    except Exception:
        pass
    text = re.sub(r"[ \t]+", " ", "".join(p.out))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return {"title": title, "description": d, "headings": p.headings[:60], "text": text[:18000]}


def video_md(v: dict) -> list[str]:
    lines = ["### Video",
             f"- videoId: {v.get('videoId', '?')} | author: {v.get('author', '?')}",
             f"- length: {fmt_ts(v.get('lengthSeconds', 0))} | views: {v.get('viewCount', '?')}"]
    if v.get("keywords"):
        lines.append(f"- keywords: {', '.join(v['keywords'][:15])}")
    desc = v.get("description", "")
    if desc:
        lines += ["", f"- description ({len(desc)} chars):", desc[:2500]]
    chs = chapters_from_description(desc)
    if chs:
        lines += ["", "- chapters:", *[f"  - {c['ts']} {c['title']}" for c in chs]]
    tr = v.get("transcript")
    if tr:
        lines += ["", f"- TRANSCRIPT ({len(tr)} paras, via {v.get('transcript_src', '?')}):"]
        lines += [f"  [{fmt_ts(p['t'])}] {p['text']}" for p in tr]
    else:
        lines += ["", f"- TRANSCRIPT: unavailable ({v.get('transcript_src', 'not attempted')})"]
    return lines


def tweets_md(x: dict) -> list[str]:
    lines = [f"### X feed - {x.get('tweetCount', 0)} loaded tweets (URL: {x.get('url', '')})"]
    for t in x.get("tweets", []):
        lines += ["", f"- **@{t['author']}** ({t['time'] or 'no ts'}) {t['stats']}",
                  f"  {t['text'].replace(chr(10), ' / ')}"]
        if t["media"]:
            lines.append(f"  media: {', '.join(t['media'][:4])}")
        if t["links"]:
            lines.append(f"  links: {', '.join(t['links'][:4])}")
        if t["href"]:
            lines.append(f"  permalink: {t['href']}")
    if not x.get("tweets"):
        lines += ["", "- (no tweets extracted - logged-out shell or lazy grid not loaded)"]
    return lines


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-per-tab", type=int, default=4)
    ap.add_argument("--max-total", type=int, default=24)
    ap.add_argument("--allow-tabs", action="store_true",
                    help="open real tabs for JS-rendered tier-1 pages (budget: --tab-budget)")
    ap.add_argument("--tab-budget", type=int, default=6)
    ap.add_argument("--timeout-ms", type=int, default=15000)
    args = ap.parse_args()

    from playwright.async_api import async_playwright

    started = dt.datetime.now()
    out_dir = Path(args.out or f"{Path.home()}/harvests/{started:%Y%m%d_%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{args.port}")
        tabs, errors = [], []
        tab_t1_budget = [args.tab_budget]  # shared budget for throwaway-tab work
        pages = [p for ctx in browser.contexts for p in ctx.pages]
        for i, page in enumerate(pages):
            url = page.url
            entry = {"kind": "tab", "index": i, "url": url, "title": "", "error": None,
                     "data": None, "video": None, "tweets": None}
            tabs.append(entry)
            if SKIP_URL.search(url):
                entry["error"] = "skipped: non-http scheme"
                continue
            try:
                data = await page.evaluate(TIER0_JS)
                entry["title"] = data.get("title", "")
                entry["data"] = data
                if YT_WATCH_RE.search(url):
                    v = await page.evaluate(YT_JS)
                    tr, src = yt_dlp_transcript(url)  # primary: yt-dlp
                    if tr is None:
                        tr, src = await yt_transcript_page(page, v.get("captionTracks", []))
                    if tr is None and v.get("videoId"):
                        tr, src = await yt_transcript_static(browser.contexts[0],
                                                             f"https://www.youtube.com/watch?v={v['videoId']}")
                    if tr is None and v.get("videoId") and args.allow_tabs and tab_t1_budget[0] > 0:
                        tab_t1_budget[0] -= 1
                        tr, src = await transcript_via_new_tab(
                            browser.contexts[0], url, args.timeout_ms)
                    v["transcript"], v["transcript_src"] = tr, src
                    entry["video"] = v
                elif X_ANY_RE.search(url):
                    entry["tweets"] = await page.evaluate(X_JS)
            except Exception as e:
                entry["error"] = f"tier0 evaluate failed: {type(e).__name__}: {str(e)[:120]}"
                errors.append({"url": url, "error": entry["error"]})

        # tier-1 selection
        picked, per_tab_count = [], {}
        for entry in tabs:
            if not entry.get("data"):
                continue
            base = entry["url"]
            tw = set(re.findall(r"[a-z]{3,}", (entry.get("title") or "").lower()))
            scored = sorted(
                ((score_link(l, base, tw), l) for l in entry["data"]["links"]),
                key=lambda x: -x[0],
            )
            n = 0
            for s, l in scored:
                if s < 2 or n >= args.max_per_tab:
                    break
                if any(p["href"] == l["href"] for p in picked):
                    continue
                picked.append({"href": l["href"], "text": l["text"], "score": s,
                               "from": base, "via_tab_title": entry.get("title", "")})
                n += 1
                if len(picked) >= args.max_total:
                    break
            per_tab_count[entry["url"]] = n
            if len(picked) >= args.max_total:
                break

        # tier-1 fetch (cookie-bearing API fetch; real tabs only as fallback)
        ctx = browser.contexts[0] if browser.contexts else None
        tier1, needs_js = [], []
        for p in picked:
            rec = {"href": p["href"], "from": p["from"], "score": p["score"],
                   "anchor": p["text"], "title": "", "text": "", "headings": [],
                   "fetch": "api", "kind": "page", "video": None}
            tier1.append(rec)
            w = watch_url(p["href"])
            if w:
                rec["kind"] = "video"
                try:
                    resp = await ctx.request.get(w, timeout=args.timeout_ms, max_redirects=5)
                    html = await resp.text() if resp.ok else ""
                    info = parse_watch_html(html) if html else None
                    if info:
                        vd = info["videoDetails"]
                        v = {"videoId": vd.get("videoId", YT_WATCH_RE.search(p["href"]).group(1)),
                             "title": vd.get("title", ""), "author": vd.get("author", ""),
                             "lengthSeconds": int(vd.get("lengthSeconds", 0) or 0),
                             "viewCount": vd.get("viewCount", ""),
                             "description": vd.get("shortDescription", ""),
                             "keywords": vd.get("keywords", []),
                             "captionTracks": info["captionTracks"]}
                        tr, src = yt_dlp_transcript(w)  # primary: yt-dlp
                        if tr is None:
                            tr, src = await yt_transcript_static(ctx, w)
                        if tr is None and args.allow_tabs and tab_t1_budget[0] > 0:
                            tab_t1_budget[0] -= 1
                            tr, src = await transcript_via_new_tab(ctx, w, args.timeout_ms)
                        v["transcript"], v["transcript_src"] = tr, src
                        rec["video"] = v
                        rec["title"] = v["title"]
                        rec["fetch"] = "api-yt-static"
                    else:
                        rec["text"] = "[watch html parse failed]"
                except Exception:
                    rec["text"] = "[youtube fetch failed]"
                continue
            if X_STATUS_RE.search(p["href"]):
                rec["kind"] = "tweet"
                if args.allow_tabs and len(needs_js) < args.tab_budget:
                    needs_js.append((rec, p["href"]))  # X static HTML is a shell; force tab
                continue
            try:
                resp = await ctx.request.get(p["href"], timeout=args.timeout_ms, max_redirects=5)
                ct = resp.headers.get("content-type", "")
                if resp.ok and "html" in ct:
                    html = await resp.text()
                    st = html_to_struct(html)
                    rec.update(st)
                    if len(st["text"]) < 400 and args.allow_tabs and len(needs_js) < args.tab_budget:
                        needs_js.append((rec, p["href"]))
                elif resp.ok:
                    rec["text"] = f"[non-html content-type: {ct}]"
                    rec["fetch"] = "api-nonhtml"
                else:
                    rec["text"] = f"[HTTP {resp.status}]"
            except Exception:
                rec["text"] = "[fetch failed]"
                rec["fetch"] = "api-failed"
                if args.allow_tabs and len(needs_js) < args.tab_budget:
                    needs_js.append((rec, p["href"]))

        for rec, href in needs_js:
            page = None
            try:
                page = await ctx.new_page()
                await page.goto(href, timeout=args.timeout_ms, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
                if rec["kind"] == "tweet":
                    x = await page.evaluate(X_JS)
                    rec["title"] = f"@{X_STATUS_RE.search(href).group(1)} status"
                    rec["text"] = " | ".join(t["text"].replace("\n", " ")[:200] for t in x["tweets"][:6])
                    rec["tweets_fetched"] = x["tweets"]
                    rec["fetch"] = "tab-js-x"
                else:
                    data = await page.evaluate(TIER0_JS)
                    rec.update({"title": data["title"], "text": data["text"],
                                "headings": data["headings"]})
                    rec["fetch"] = "tab-js"
            except Exception:
                rec["text"] = (rec.get("text") or "") + " [tab fallback failed]"
            finally:
                if page:
                    await page.close()

        await browser.close()  # disconnect only

    stamp = f"{started:%Y-%m-%d %H:%M}"
    md, js = out_dir / "harvest.md", out_dir / "harvest.json"
    lines = [f"# Tab harvest - {stamp}", "",
             f"- Tabs seen: {len(tabs)} (extracted: {sum(1 for t in tabs if t.get('data'))}, "
             f"skipped/errored: {sum(1 for t in tabs if not t.get('data'))})",
             f"- Tabs with video: {sum(1 for t in tabs if t.get('video'))}; with transcripts: "
             f"{sum(1 for t in tabs if (t.get('video') or {}).get('transcript'))}",
             f"- Tabs with tweets: {sum(1 for t in tabs if t.get('tweets'))}",
             f"- Tier-1 links fetched: {len(tier1)} "
             f"(videos: {sum(1 for r in tier1 if r['kind'] == 'video')}, "
             f"tweets: {sum(1 for r in tier1 if r['kind'] == 'tweet')})", ""]
    for t in tabs:
        if not t.get("data"):
            lines += [f"## [TAB {t['index']}] {t['url']}", f"- error: {t['error']}", ""]
            continue
        d = t["data"]
        lines += [f"## [TAB {t['index']}] {d['title'] or d['url']}", "",
                  f"- url: {d['url']}", f"- links on page: {d['linkCount']}"]
        if t.get("video"):
            lines += video_md(t["video"])
        if t.get("tweets"):
            lines += tweets_md(t["tweets"])
        if not t.get("video") and not t.get("tweets"):
            lines += ["", "### Headings",
                      *([f"- {'#' * h['level']} {h['text']}" for h in d["headings"]] or ["- (none)"])]
            if d["code"]:
                lines += ["", "### Code blocks", *[f"```\n{c}\n```" for c in d["code"][:6]]]
            if d["tables"]:
                lines += ["", "### Tables"]
                for tb in d["tables"][:4]:
                    lines += ["| " + " | ".join(r) + " |" for r in tb[:12]] + [""]
            lines += ["", "### Text", d["text"]]
        lines += [""]
    lines += ["", "---", "", "# Tier-1 fetches", ""]
    for r in tier1:
        lines += [f"## → {r['title'] or r['href']}", "",
                  f"- url: {r['href']}", f"- linked from: {r['from']} (score {r['score']})",
                  f"- fetch mode: {r['fetch']}", ""]
        if r.get("video"):
            lines += video_md(r["video"])
        for t in r.get("tweets_fetched", []):
            lines += [f"- **@{t['author']}** ({t['time']}) {t['stats']}",
                      f"  {t['text'].replace(chr(10), ' / ')}"]
        if r["kind"] == "page":
            if r["headings"]:
                lines += [f"- {'#' * h['level']} {h['text']}" for h in r["headings"][:25]]
            lines += ["", r["text"][:12000]]
        lines += [""]
    md.write_text("\n".join(lines), encoding="utf-8")

    def slim_video(v):
        if not v:
            return None
        out = {k: v.get(k) for k in ("videoId", "title", "author", "lengthSeconds",
                                     "viewCount", "keywords", "transcript_src")}
        out["chapters"] = chapters_from_description(v.get("description", ""))
        out["transcript"] = v.get("transcript")
        out["description_head"] = v.get("description", "")[:800]
        return out

    payload = {"started": stamp, "port": args.port, "args": vars(args),
               "tabs": [{"kind": t["kind"], "index": t["index"], "url": t["url"],
                         "title": t["title"], "error": t["error"],
                         "video": slim_video(t.get("video")),
                         "tweets": t.get("tweets")} for t in tabs],
               "tier1": [{k: (slim_video(v) if k == "video" else v) for k, v in r.items()
                          if k != "tweets_fetched"} for r in tier1],
               "errors": errors, "per_tab_tier1": per_tab_count}
    js.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")

    # knowledge graph (best-effort: never fails the harvest)
    graph_info = {}
    try:
        import subprocess as _sp
        gb = Path(__file__).parent / "graph_builder.py"
        r = _sp.run([sys.executable, str(gb), str(js), "--out", str(out_dir)],
                    capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            graph_info = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        graph_info = {"ok": False, "error": str(e)[:120]}

    print(json.dumps({"ok": True, "tabs": len(tabs), "extracted": sum(1 for t in tabs if t.get("data")),
                      "videos": sum(1 for t in tabs if t.get("video")),
                      "transcripts": sum(1 for t in tabs if (t.get("video") or {}).get("transcript")),
                      "tweet_tabs": sum(1 for t in tabs if t.get("tweets")),
                      "tier1": len(tier1),
                      "tier1_videos": sum(1 for r in tier1 if r["kind"] == "video"),
                      "tier1_tweets": sum(1 for r in tier1 if r["kind"] == "tweet"),
                      "markdown": str(md), "json": str(js)}))
    return 0


if __name__ == "__main__":
    sys.exit(__import__("asyncio").run(main()))
