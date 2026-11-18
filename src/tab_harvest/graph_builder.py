#!/usr/bin/env python3
"""graph_builder - turn a tab-harvest payload into an interactive knowledge graph.

Outputs:
  graph.json - {meta, nodes, edges} (agent-editable: add concept/action/
               question nodes + semantic edges, then --refresh to re-render)
  graph.html - self-contained interactive graph (vanilla JS, no CDN, offline)

Design: dark observatory language. Ink background, harmonized kind palette,
curved gradient edges, pre-rendered glow sprites, staggered fade-in,
neighborhood focus, keyboard shortcuts.

CLI:
  build_graph.py <harvest.json> [--out DIR]         build + render
  build_graph.py --refresh <graph.json> [--html P]  re-render enriched graph
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

STOPWORDS = set("""
a about above after again all also am an and any are as at be because been
before being below between both but by can cannot could did do does doing down
during each few for from further had has have having he her here hers herself
him himself his how i if in into is it its itself just me more most my myself
no nor not of off on once only or other our ours ourselves out over own same
she should so some such than that the their theirs them themselves then there
these they this those through to too under until up very was we were what when
where which while who whom why will with you your yours yourself yourselves
get got will would like really new video watch subscribe channel http https
www com one two three make made making way things thing want need see seen
here's it's don't doesn't i'm we're you're they're gonna going know knows said
says say using use used let lets us out now best top vs
""".split())

TOKEN_RE = re.compile(r"[a-z][a-z0-9+#-]{2,}")
MAX_TOPICS = 40
MIN_TOPIC_DF = 2


def registrable(host: str) -> str:
    parts = host.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _tokens(*texts: str) -> set[str]:
    out: set[str] = set()
    for t in texts:
        if not t:
            continue
        for tok in TOKEN_RE.findall(t.lower()):
            if tok not in STOPWORDS and not tok.isdigit():
                out.add(tok)
    return out


def _snip(text: str | None, n: int = 320) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()[:n]


def build_graph(payload: dict) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple] = set()
    topic_docs: dict[str, set[str]] = defaultdict(set)
    vid_nodes: dict[str, list[str]] = defaultdict(list)

    def node(nid: str, kind: str, label: str, url: str = "", **meta) -> dict:
        if nid in nodes:
            return nodes[nid]
        n = {"id": nid, "kind": kind, "label": label[:120] or nid,
             "url": url, "meta": {k: v for k, v in meta.items() if v not in (None, "", [])}}
        nodes[nid] = n
        return n

    def edge(src: str, dst: str, etype: str, weight: float = 1.0) -> None:
        key = (src, dst, etype)
        if key in seen_edges or src == dst or src not in nodes or dst not in nodes:
            return
        seen_edges.add(key)
        edges.append({"source": src, "target": dst, "type": etype, "weight": weight})

    def add_video(idprefix: str, vid: dict | None, url: str, from_id: str | None) -> str | None:
        if not vid:
            return None
        nid = f"{idprefix}:{vid.get('videoId') or url}"
        tr = vid.get("transcript") or []
        node(nid, "video", vid.get("title") or url, url,
             channel=vid.get("author"), views=vid.get("viewCount"),
             length=vid.get("lengthSeconds"), transcript_src=vid.get("transcript_src"),
             transcript_paras=len(tr),
             snippet=_snip(vid.get("description", "")),
             transcript_head=_snip(tr[0]["text"] if tr else ""))
        if vid.get("videoId"):
            vid_nodes[vid["videoId"]].append(nid)
        if vid.get("author"):
            cn = node(f"chan:{vid['author']}", "channel", vid["author"],
                      f"https://www.youtube.com/@{vid['author']}".replace(" ", ""))
            edge(nid, cn["id"], "authored_by")
        if from_id:
            edge(from_id, nid, "links_to")
        topic_docs[nid] |= _tokens(vid.get("title"), " ".join(vid.get("keywords") or []),
                                   vid.get("description", "")[:2000])
        return nid

    for t in payload.get("tabs", []):
        tid = f"tab:{t.get('index')}"
        if t.get("video"):
            add_video("tab", t["video"], t.get("url", ""), None)
            nodes[tid] = nodes[f"tab:{t['video'].get('videoId') or t.get('url')}"]
            continue
        if t.get("tweets"):
            tw = t["tweets"]
            node(tid, "x_feed", f"X feed ({tw.get('tweetCount', 0)} tweets)", t.get("url", ""))
            authors = Counter(x.get("author") for x in tw.get("tweets", []) if x.get("author"))
            for a, _c in authors.most_common(5):
                an = node(f"auth:{a}", "author", f"@{a}", f"https://x.com/{a}")
                edge(tid, an["id"], "features")
            topic_docs[tid] |= _tokens(" ".join(x.get("text", "") for x in tw.get("tweets", [])[:20]))
            continue
        node(tid, "page", t.get("title") or t.get("url", ""), t.get("url", ""),
             error=t.get("error"))

    for r in payload.get("tier1", []):
        href = r.get("href", "")
        rid = f"t1:{href}"
        if r.get("video"):
            add_video("t1", r["video"], href, None)
        elif r.get("kind") == "tweet":
            m = re.search(r"\.com/(\w+)/status/", href)
            handle = m.group(1) if m else "unknown"
            tweets = r.get("tweets_fetched") or []
            node(rid, "tweet", f"@{handle}: {_snip((tweets[0] or {}).get('text', '') if tweets else r.get('anchor', ''), 80)}",
                 href, anchor=r.get("anchor"), tweets=len(tweets),
                 snippet=_snip(" | ".join(x.get("text", "") for x in tweets[:3])))
            if m:
                an = node(f"auth:{handle}", "author", f"@{handle}", f"https://x.com/{handle}")
                edge(rid, an["id"], "authored_by")
            topic_docs[rid] |= _tokens(" ".join(x.get("text", "") for x in tweets))
        else:
            node(rid, "page", r.get("title") or href, href,
                 fetch=r.get("fetch"), snippet=_snip(r.get("text", "")))
            topic_docs[rid] |= _tokens(r.get("title", ""), " ".join(
                h.get("text", "") for h in r.get("headings", [])[:20]), r.get("text", "")[:3000])
        frm = r.get("from", "")
        if frm:
            src = next((n["id"] for n in nodes.values()
                        if n["kind"] in ("page", "x_feed") and n["url"] == frm), None)
            if src:
                edge(src, rid if not r.get("video") else f"t1:{(r.get('video') or {}).get('videoId') or href}", "links_to")

    for ids in vid_nodes.values():
        if len(ids) > 1:
            for extra in ids[1:]:
                if nodes[extra].get("label") == nodes[ids[0]].get("label"):
                    nodes[extra]["label"] = nodes[extra]["label"][:44] + " ↗ linked"
                    nodes[extra].setdefault("meta", {})["twin"] = True
        for i in range(1, len(ids)):
            edge(ids[0], ids[i], "same_as")

    df = Counter()
    for _nid, toks in topic_docs.items():
        df.update(toks)
    topics = [(t, c) for t, c in df.most_common(MAX_TOPICS * 2) if c >= MIN_TOPIC_DF][:MAX_TOPICS]
    for term, count in topics:
        tnode = node(f"topic:{term}", "topic", term, "", sources=count)
        for nid, toks in topic_docs.items():
            if term in toks:
                edge(nid, tnode["id"], "mentions", weight=0.6)

    return {"meta": payload.get("started", ""), "nodes": list(nodes.values()), "edges": edges}


# ── HTML template (dark observatory design) ────────────────────────────────

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en" data-theme="etched">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowledge Graph</title>
<style>
:root{
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
[data-theme="etched"]{
  --bg:#f4f3ee; --ink:#191a1c; --muted:#6b6d70; --hair:#d9d7cf;
  --panel-bg:rgba(252,252,250,.95); --panel-border:#d8d6cd;
  --hdr-bg:rgba(248,247,242,.9); --hdr-border:#d8d6cd;
  --chip-bg:rgba(252,252,250,.92); --chip-border:#d8d6cd;
  --tip-bg:rgba(252,252,250,.97); --tip-border:#d8d6cd;
  --btn-bg:rgba(255,255,255,.7); --btn-border:#c9c7be;
  --shadow:0 10px 30px rgba(30,30,25,.10);
  --sheet-shadow:0 -18px 50px rgba(30,30,25,.14);
  --sel-ring:#191a1c;
}
[data-theme="mono"]{
  --bg:#101114; --ink:#ececee; --muted:#8b8e93; --hair:#26282c;
  --panel-bg:rgba(18,19,22,.93); --panel-border:#2c2f34;
  --hdr-bg:rgba(14,15,17,.88); --hdr-border:#26282c;
  --chip-bg:rgba(18,19,22,.92); --chip-border:#2c2f34;
  --tip-bg:rgba(12,13,15,.97); --tip-border:#2c2f34;
  --btn-bg:rgba(255,255,255,.05); --btn-border:#3a3d43;
  --shadow:0 10px 30px rgba(0,0,0,.45);
  --sheet-shadow:0 -18px 50px rgba(0,0,0,.5);
  --sel-ring:#ffffff;
}
[data-theme="platinum"]{
  --bg:#17191d; --ink:#e8ecf1; --muted:#97a1ac; --hair:#2e3339;
  --panel-bg:linear-gradient(180deg, rgba(38,43,50,.62), rgba(28,32,38,.55));
  --panel-border:rgba(220,228,236,.22);
  --hdr-bg:linear-gradient(180deg, rgba(40,45,52,.55), rgba(24,27,32,.5));
  --hdr-border:rgba(220,228,236,.16);
  --chip-bg:rgba(34,39,46,.55); --chip-border:rgba(220,228,236,.18);
  --tip-bg:rgba(26,30,36,.96); --tip-border:rgba(220,228,236,.2);
  --btn-bg:linear-gradient(180deg, rgba(228,234,240,.16), rgba(228,234,240,.06));
  --btn-border:rgba(228,234,240,.28);
  --shadow:0 14px 40px rgba(0,0,0,.5);
  --sheet-shadow:0 -18px 50px rgba(0,0,0,.55);
  --sel-ring:#dfe5ec;
}
[data-theme="wireframe"]{
  --bg:#0e131c; --ink:#dfe9f5; --muted:#7c8fa6; --hair:#223248;
  --panel-bg:rgba(13,19,29,.66); --panel-border:rgba(124,174,224,.28);
  --hdr-bg:rgba(11,16,24,.8); --hdr-border:rgba(124,174,224,.2);
  --chip-bg:rgba(13,19,29,.8); --chip-border:rgba(124,174,224,.22);
  --tip-bg:rgba(11,16,24,.97); --tip-border:rgba(124,174,224,.3);
  --btn-bg:rgba(124,174,224,.1); --btn-border:rgba(124,174,224,.35);
  --shadow:0 14px 40px rgba(0,0,0,.5);
  --sheet-shadow:0 -18px 50px rgba(0,0,0,.55);
  --sel-ring:#9cc0ff;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%;overflow:hidden;background:var(--bg);color:var(--ink);
  font-family:var(--sans); transition:background .35s ease, color .35s ease}
canvas#cv{position:fixed;inset:0;display:block;cursor:grab}
canvas#cv.hovering{cursor:pointer} canvas#cv.grabbing{cursor:grabbing}

header{position:fixed;top:12px;left:12px;right:12px;z-index:20;display:flex;gap:12px;
  align-items:center;padding:8px 14px;border:1px solid var(--hdr-border);
  background:var(--hdr-bg);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  border-radius:14px;box-shadow:var(--shadow)}
#logo{height:34px;display:block}
.brand{display:flex;align-items:center;gap:12px;min-width:0}
.meta{font:10px var(--mono);color:var(--muted);letter-spacing:.04em;white-space:nowrap}
.searchbox{flex:1;display:flex;align-items:center;gap:8px;min-width:120px;
  border:1px solid var(--chip-border);border-radius:999px;padding:6px 12px;
  background:var(--btn-bg);color:var(--muted)}
.searchbox input{flex:1;border:0;outline:0;background:transparent;color:var(--ink);font:13px var(--sans)}
.kbd{font:10px var(--mono);border:1px solid var(--chip-border);border-radius:5px;padding:1px 6px;color:var(--muted)}
#stats{font:11px var(--mono);color:var(--muted);white-space:nowrap}
#stats b{color:var(--ink);font-weight:600}
#themes{display:flex;border:1px solid var(--btn-border);border-radius:10px;overflow:hidden}
#themes button{border:0;background:transparent;color:var(--muted);font:11px var(--mono);
  letter-spacing:.02em;padding:7px 11px;cursor:pointer;border-right:1px solid var(--hair)}
#themes button:last-child{border-right:0}
#themes button.on{background:var(--btn-bg);color:var(--ink);font-weight:700}
#reset{border:1px solid var(--btn-border);background:var(--btn-bg);color:var(--ink);
  font:11px var(--mono);border-radius:10px;padding:7px 11px;cursor:pointer;white-space:nowrap}

#kinds{position:fixed;top:76px;left:12px;z-index:15;display:flex;flex-wrap:wrap;gap:6px;max-width:62vw}
.kind-pill{display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;
  border:1px solid var(--chip-border);background:var(--chip-bg);
  backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  font:11px var(--mono);color:var(--ink);cursor:pointer;user-select:none}
.kind-pill .dot{width:8px;height:8px;border-radius:50%}
.kind-pill .n{color:var(--muted)}
.kind-pill.off{opacity:.38;filter:saturate(.2)}

#tip{position:fixed;z-index:30;display:none;max-width:340px;padding:10px 12px;border-radius:12px;
  background:var(--tip-bg);border:1px solid var(--tip-border);box-shadow:var(--shadow);pointer-events:none}
#tip .k{font:10px var(--mono);letter-spacing:.08em;text-transform:uppercase;margin-bottom:3px}
#tip .t{font:600 13px var(--sans);color:var(--ink)}
#tip .u{font:10px var(--mono);color:var(--muted);margin-top:3px;word-break:break-all}
#tip .c{font:10px var(--mono);color:var(--muted);margin-top:4px}

/* detail panel: stacked bottom sheet over the canvas */
#panel{position:fixed;left:12px;right:12px;bottom:12px;z-index:25;max-height:46vh;
  background:var(--panel-bg);border:1px solid var(--panel-border);border-radius:16px;
  box-shadow:var(--sheet-shadow);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  transform:translateY(calc(100% + 20px));transition:transform .38s cubic-bezier(.22,.9,.3,1)}
#panel.open{transform:translateY(0)}
#pclose{position:absolute;top:10px;right:12px;z-index:2;width:28px;height:28px;border-radius:9px;
  border:1px solid var(--chip-border);background:var(--btn-bg);color:var(--muted);
  font:14px var(--sans);cursor:pointer;line-height:1}
#panel .scroll{overflow-y:auto;max-height:46vh;padding:16px 18px 18px}
#panel .kind{font:10px var(--mono);letter-spacing:.08em;text-transform:uppercase;margin-bottom:4px}
#panel h2{margin:0 0 6px;font:700 20px/1.15 var(--sans);color:var(--ink);max-width:82%}
#panel .url{display:inline-block;max-width:82%;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font:11px var(--mono);color:var(--muted);text-decoration:none;
  border-bottom:1px dotted var(--hair);padding-bottom:1px}
#panel .hair{height:1px;background:var(--hair);margin:12px 0}
#panel .kv{display:grid;grid-template-columns:auto 1fr;gap:5px 16px}
#panel .kv b{font:11px var(--mono);color:var(--muted);font-weight:500;white-space:nowrap}
#panel .kv span{font:12.5px var(--sans);color:var(--ink)}
#panel .sechead{font:10px var(--mono);letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);margin:0 0 6px}
#panel .snip{font:12.5px/1.55 var(--sans);color:var(--ink);opacity:.92;
  display:-webkit-box;-webkit-line-clamp:6;-webkit-box-orient:vertical;overflow:auto}
.conn-row{display:flex;align-items:center;gap:8px;padding:5px 6px;margin:0 -6px;border-radius:8px;cursor:pointer}
.conn-row:hover{background:var(--chip-bg)}
.conn-row .dot{width:8px;height:8px;border-radius:50%;flex:none}
.conn-row .cname{font:12.5px var(--sans);color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.conn-row .verb{margin-left:auto;font:10px var(--mono);color:var(--muted);white-space:nowrap}

#nores{position:fixed;inset:0;z-index:18;display:none;place-items:center;pointer-events:none}
#nores .box{background:var(--tip-bg);border:1px solid var(--tip-border);border-radius:14px;
  padding:16px 22px;text-align:center;color:var(--muted);font:13px var(--sans);
  box-shadow:var(--shadow)}
#nores .q{font:12px var(--mono);color:var(--ink);margin-top:6px}
@media (max-width:900px){ .meta,#stats{display:none} #kinds{max-width:90vw} }

/* reports drawer (side panel) */
#reports-btn{border:1px solid var(--btn-border);background:var(--btn-bg);color:var(--ink);
  font:11px var(--mono);border-radius:10px;padding:7px 11px;cursor:pointer;white-space:nowrap}
#reports{position:fixed;top:12px;right:12px;bottom:12px;width:min(460px,94vw);z-index:40;
  background:var(--panel-bg);border:1px solid var(--panel-border);border-radius:16px;
  box-shadow:var(--sheet-shadow);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  transform:translateX(calc(100% + 20px));transition:transform .38s cubic-bezier(.22,.9,.3,1);
  display:flex;flex-direction:column}
#reports.open{transform:translateX(0)}
#reports .rhead{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid var(--hair)}
#reports .rhead .rtitle{font:700 14px var(--sans);color:var(--ink);flex:1;min-width:0;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#reports .rhead button{border:1px solid var(--chip-border);background:var(--btn-bg);color:var(--muted);
  font:11px var(--mono);border-radius:8px;padding:5px 9px;cursor:pointer}
#reports .rbody{overflow-y:auto;flex:1;padding:14px 18px 20px}
#reports .rlist .ritem{display:block;padding:8px 10px;margin:0 -8px;border-radius:10px;cursor:pointer;
  font:12.5px var(--sans);color:var(--ink);border-bottom:1px solid var(--hair)}
#reports .rlist .ritem:hover{background:var(--chip-bg)}
#reports .rlist .ritem .rname{font:10px var(--mono);color:var(--muted);letter-spacing:.04em}
#reports .rbody h1{font:700 19px/1.2 var(--sans);color:var(--ink);margin:4px 0 10px}
#reports .rbody h2{font:700 15px var(--sans);color:var(--ink);margin:18px 0 8px;padding-top:10px;
  border-top:1px solid var(--hair)}
#reports .rbody h3{font:600 13px var(--sans);color:var(--ink);margin:14px 0 6px}
#reports .rbody p{font:12.5px/1.55 var(--sans);color:var(--ink);opacity:.92;margin:6px 0}
#reports .rbody li{font:12.5px/1.5 var(--sans);color:var(--ink);margin:4px 0 4px 4px}
#reports .rbody a{color:var(--muted);text-decoration:underline dotted}
#reports .rbody code{font:11px var(--mono);background:var(--chip-bg);border:1px solid var(--hair);
  border-radius:5px;padding:1px 5px}
#reports .rbody table{border-collapse:collapse;width:100%;margin:10px 0;font:12px var(--sans)}
#reports .rbody th,#reports .rbody td{border:1px solid var(--hair);padding:6px 8px;text-align:left;
  vertical-align:top;color:var(--ink)}
#reports .rbody th{font:600 11.5px var(--sans)}
#reports .rbody hr{border:0;border-top:1px solid var(--hair);margin:14px 0}
</style>
</head>
<body>
<header>
  <div class="brand">
    <span id="logofb" style="display:none;font:800 15px/34px var(--sans);letter-spacing:.02em">tab&#9654;harvest</span>
    <img id="logo" src="__LOGO_SRC__" onerror="this.style.display='none';document.getElementById('logofb').style.display='block'" alt="tab-harvest">
    <div class="meta" id="meta"></div>
  </div>
  <div class="searchbox">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
    <input id="search" placeholder="Search nodes" autocomplete="off" spellcheck="false">
    <span class="kbd">/</span>
  </div>
  <div id="stats"></div>
  <div id="themes">
    <button data-t="etched" class="on">Etched</button>
    <button data-t="mono">Mono</button>
    <button data-t="platinum">Platinum</button>
    <button data-t="wire">Wire</button>
  </div>
  <button id="reset" title="Reset view">Reset</button>
  <button id="reports-btn" title="Toggle reports">Reports</button>
</header>
<canvas id="cv"></canvas>
<div id="kinds"></div>
<div id="tip"></div>
<div id="nores"><div class="box"><div>No nodes match</div><div class="q" id="noq"></div></div></div>
<aside id="panel">
  <button id="pclose" title="Close">×</button>
  <div class="scroll" id="pbody"></div>
</aside>
<aside id="reports">
  <div class="rhead">
    <div class="rtitle" id="rtitle">Reports</div>
    <button id="rback" style="display:none">Back</button>
    <button id="rclose" title="Close">×</button>
  </div>
  <div class="rbody" id="rbody"></div>
</aside>

<script>
"use strict";
const DATA = __DATA_JSON__;

/* ---------- themes: canvas palettes + render tweaks ---------- */
const THEMES = {
  etched: { kinds:{ video:"#d95f4e", tab:"#33353a", page:"#3f9d68", tweet:"#2f9fc7",
      x_feed:"#2f9fc7", channel:"#c08a36", author:"#b3822f", topic:"#7f6cc9",
      concept:"#8f74d6", action:"#b8912f", question:"#5f6b7c" },
    fallback:"#5f6b7c", labelBg:"rgba(252,252,250,.93)", labelInk:"#17181a",
    ring:"rgba(25,26,28,.4)", glow:.5, dots:true, wire:false },
  mono: { kinds:{ video:"#f2f2f2", tab:"#ffffff", page:"#a9a9ad", tweet:"#8f9296",
      x_feed:"#8f9296", channel:"#c9c9cd", author:"#b4b4b8", topic:"#9b9ea2",
      concept:"#adaeb2", action:"#d8d8dc", question:"#767a80" },
    fallback:"#8f9296", labelBg:"rgba(10,11,13,.82)", labelInk:"#e3e4e6",
    ring:"rgba(255,255,255,.5)", glow:.85, dots:false, wire:false },
  platinum: { kinds:{ video:"#e6edf3", tab:"#f5f8fb", page:"#9fb4c6", tweet:"#87a3b8",
      x_feed:"#87a3b8", channel:"#ccd6e0", author:"#b6c3ce", topic:"#9db2c3",
      concept:"#abc1d1", action:"#c6d1db", question:"#7e93a4" },
    fallback:"#9db2c3", labelBg:"rgba(14,17,21,.8)", labelInk:"#e3e9ef",
    ring:"rgba(226,232,238,.55)", glow:.9, dots:false, wire:false },
  wireframe: { kinds:{ video:"#d3e6ff", tab:"#f0f6ff", page:"#7fa9d9", tweet:"#6d9cca",
      x_feed:"#6d9cca", channel:"#a9c7e3", author:"#8fb2d4", topic:"#7fa6cf",
      concept:"#8fb5e1", action:"#9dc1e9", question:"#6a89ab" },
    fallback:"#7fa6cf", labelBg:"rgba(10,15,23,.82)", labelInk:"#dbe7f5",
    ring:"rgba(156,192,255,.6)", glow:.95, dots:false, wire:true },
};
let theme = "etched";
try { const s = localStorage.getItem("th-theme"); if (s && THEMES[s]) theme = s; } catch(e){}
function T(){ return THEMES[theme]; }
function KC(kind){ return T().kinds[kind] || T().fallback; }

const tip=document.getElementById("tip"), panel=document.getElementById("panel"),
      pbody=document.getElementById("pbody"), pclose=document.getElementById("pclose");
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const KINDS = {
  video:   {r:13, label:"video"},
  tab:     {r:15, label:"tab"},
  page:    {r:9,  label:"page"},
  tweet:   {r:9,  label:"tweet"},
  x_feed:  {r:12, label:"x feed"},
  channel: {r:10, label:"channel"},
  author:  {r:7,  label:"author"},
  topic:   {r:7,  label:"topic"},
  concept: {r:11, label:"concept"},
  action:  {r:10, label:"action"},
  question:{r:9,  label:"question"},
};
const CURVE = {links_to:.16, authored_by:.30, features:.22, mentions:.12, same_as:.42, semantic:.24, related:.18};
const nodes = DATA.nodes, edges = DATA.edges;
const byId = new Map(nodes.map(n => [n.id, n]));
nodes.forEach((n,i) => { n.idx=i;
  const a = i * 2.39; const rad = 140 + 90*Math.sqrt(i+1);
  n.x = Math.cos(a)*rad; n.y = Math.sin(a)*rad*.72;
  n.vx=0; n.vy=0; n.deg=0; n.match=true; n.hidden=false; n.hr=1; });
const adj = new Map(nodes.map(n => [n.id,[]]));
edges.forEach(e => { if(byId.has(e.source)&&byId.has(e.target)) {
  byId.get(e.source).deg++; byId.get(e.target).deg++;
  adj.get(e.source).push(e); adj.get(e.target).push(e); }});
nodes.forEach(n => { n.r = (KINDS[n.kind]?.r || 9) + Math.min(9, 1.5*Math.sqrt(n.deg));
  if (n.meta && n.meta.twin) n.r = Math.max(5, n.r * .62); });

/* glow sprites (per theme x kind x radius bucket) */
const sprites = new Map();
function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16);
  const ch = v => Math.max(0, Math.min(255, Math.round(v + v*f)));
  return `rgb(${ch(n>>16)},${ch((n>>8)&255)},${ch(n&255)})`;
}
function sprite(kind, r, meta) {
  const key = theme+":"+kind+":"+Math.round(r);
  if (sprites.has(key)) return sprites.get(key);
  const c = KC(kind);
  const dark = theme !== "etched";
  const R = Math.ceil(r*3.2), cx = R, cy = R;
  const cv2 = document.createElement("canvas"); cv2.width = cv2.height = R*2;
  const g = cv2.getContext("2d");
  const glow = T().glow;
  const grd = g.createRadialGradient(cx,cy,r*.2, cx,cy,r*2.6);
  grd.addColorStop(0, c+Math.round(85*glow).toString(16).padStart(2,"0"));
  grd.addColorStop(.35, c+Math.round(34*glow).toString(16).padStart(2,"0"));
  grd.addColorStop(1, c+"00");
  g.fillStyle = grd; g.beginPath(); g.arc(cx,cy,r*2.6,0,7); g.fill();
  const body = g.createRadialGradient(cx-r*.3,cy-r*.35,r*.1, cx,cy,r);
  if (dark) { body.addColorStop(0, "#ffffff"); body.addColorStop(.3, c); body.addColorStop(1, shade(c,-.42)); }
  else { body.addColorStop(0, "#ffffff"); body.addColorStop(.3, c); body.addColorStop(1, shade(c,-.28)); }
  g.fillStyle = body; g.beginPath(); g.arc(cx,cy,r,0,7); g.fill();
  g.strokeStyle = dark ? "rgba(255,255,255,.28)" : "rgba(20,21,23,.7)";
  g.lineWidth = Math.max(1.4, r*.14);
  g.beginPath(); g.arc(cx,cy,r,0,7); g.stroke();
  if (kind === "topic" || kind === "concept") {
    g.setLineDash([r*.45, r*.4]);
    g.strokeStyle = dark ? "rgba(255,255,255,.3)" : "rgba(20,21,23,.3)"; g.lineWidth = 1;
    g.beginPath(); g.arc(cx,cy,r+3.5,0,7); g.stroke();
  } else if (meta && meta.twin) {
    g.setLineDash([r*.5, r*.45]);
    g.strokeStyle = dark ? "rgba(255,255,255,.45)" : "rgba(20,21,23,.45)"; g.lineWidth = 1.2;
    g.beginPath(); g.arc(cx,cy,r+3.5,0,7); g.stroke();
  }
  const out = {cv: cv2, R};
  sprites.set(key, out); return out;
}

/* camera + physics */
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
let W,H,DPR = Math.min(2, window.devicePixelRatio||1);
function resize(){ W=innerWidth; H=innerHeight; cv.width=W*DPR; cv.height=H*DPR;
  cv.style.width=W+"px"; cv.style.height=H+"px"; ctx.setTransform(DPR,0,0,DPR,0,0); }
addEventListener("resize", resize); resize();
let scale=.95, ox=W/2, oy=H*.46, alpha=REDUCED?0.25:0.9, hoverN=null, selN=null,
    dragN=null, panning=null, neigh=null;
const T0 = performance.now();
function appear(n){ if (REDUCED) return 1;
  return Math.min(1, Math.max(0, (performance.now()-T0-120-n.idx*14)/650)); }
function ease(t){ return 1-Math.pow(1-t,3); }
function sx(n){ return n.x*scale+ox; } function sy(n){ return n.y*scale+oy; }
function w2s(x,y){ return [x*scale+ox, y*scale+oy]; }
function wx(px){ return (px-ox)/scale; } function wy(py){ return (py-oy)/scale; }
function reheat(){ alpha = Math.max(alpha, REDUCED?.15:.4); }
function neighborhood(n){ if(!n) return null;
  const s = new Set([n.id]);
  (adj.get(n.id)||[]).forEach(e => s.add(e.source===n.id?e.target:e.source));
  return s; }

/* static wireframe geometry for the wire theme (world space) */
const MESH = (function(){ const pts=[];
  const R = (function(){ let s=42; return ()=>{ s=(s*16807)%2147483647; return s/2147483647; };})();
  for(let r=0;r<4;r++) for(let c=0;c<8;c++)
    pts.push([-320+c*46+(R()-.5)*22, -60+r*38+(R()-.5)*18]);
  const tris=[];
  for(let r=0;r<3;r++) for(let c=0;c<7;c++){
    const i=r*8+c;
    tris.push([i,i+1,i+8],[i+1,i+9,i+8]);
  }
  return {pts,tris};
})();

function drawUnderlay(){
  if (T().dots){
    ctx.fillStyle = "rgba(25,26,28,.07)";
    for(let x=14;x<W;x+=28) for(let y=14;y<H;y+=28){ ctx.fillRect(x,y,1.4,1.4); }
  }
  if (T().wire){
    ctx.strokeStyle = "rgba(140,185,230,.16)"; ctx.lineWidth = 1;
    MESH.tris.forEach(t => {
      const [a,b,c] = t.map(i => w2s(MESH.pts[i][0], MESH.pts[i][1]));
      ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0],b[1]);
      ctx.lineTo(c[0],c[1]); ctx.closePath(); ctx.stroke(); });
    const [gx,gy] = w2s(210,130);
    [118,88,58].forEach((rr,i) => { ctx.beginPath();
      ctx.ellipse(gx,gy,rr*scale,rr*.42*scale,-.3,Math.PI*(.9+i*.1),Math.PI*(1.9+i*.06));
      ctx.stroke(); });
    const [sx0,sy0] = w2s(330,-165); const gr = 34*scale;
    ctx.beginPath(); ctx.arc(sx0,sy0,gr,0,7); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(sx0,sy0,gr,gr*.36,0,0,7); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(sx0,sy0,gr*.36,gr,0,0,7); ctx.stroke();
  }
}

function tick(){
  const REP=3400, K=.03, L=118, GRAV=.05, FR=.85;
  for(let i=0;i<nodes.length;i++){ const a=nodes[i];
    for(let j=i+1;j<nodes.length;j++){ const b=nodes[j];
      let dx=a.x-b.x, dy=a.y-b.y, d2=dx*dx+dy*dy+.05;
      if(d2>360000) continue;
      const f=Math.min(24, REP*alpha/d2), d=Math.sqrt(d2);
      dx/=d; dy/=d; const fx=f*dx, fy=f*dy;
      a.vx+=fx; a.vy+=fy; b.vx-=fx; b.vy-=fy; } }
  edges.forEach(e => { const a=byId.get(e.source), b=byId.get(e.target); if(!a||!b) return;
    const l = L*(e.type==="mentions"?1.9:1)*(2-e.weight);
    let dx=b.x-a.x, dy=b.y-a.y; const d=Math.sqrt(dx*dx+dy*dy)||.01;
    const f=K*(d-l); dx/=d; dy/=d;
    a.vx+=f*dx; a.vy+=f*dy; b.vx-=f*dx; b.vy-=f*dy; });
  nodes.forEach(n => {
    n.vx += -n.x*GRAV*alpha*.12; n.vy += -n.y*GRAV*alpha*.12;
    if(n===dragN) return;
    n.vx*=FR; n.vy*=FR; n.x+=n.vx*alpha; n.y+=n.vy*alpha; });
  alpha *= .9955; if(alpha<.011) alpha=.011;
}
function edgeAlpha(e){
  const a=byId.get(e.source), b=byId.get(e.target);
  const am=a.match&&b.match;
  if(selN) return (a===selN||b===selN)?.9:(am?.12:.03);
  if(hoverN) return (a===hoverN||b===hoverN)?.85:(am?.55:.1);
  return am?.55:.12;
}
function draw(){
  ctx.clearRect(0,0,W,H);
  drawUnderlay();
  ctx.lineCap = "round";
  const dark = theme !== "etched";
  edges.forEach(e => { const a=byId.get(e.source), b=byId.get(e.target); if(!a||!b) return;
    if(a.hidden||b.hidden) return;
    const ap = Math.min(appear(a), appear(b)); if(ap<=0) return;
    const x1=sx(a),y1=sy(a),x2=sx(b),y2=sy(b);
    const mx=(x1+x2)/2, my=(y1+y2)/2;
    const dx=x2-x1, dy=y2-y1, len=Math.sqrt(dx*dx+dy*dy)||1;
    const cur=(CURVE[e.type]||.15)*len*.6;
    const cx2=mx-dy/len*cur, cy2=my+dx/len*cur;
    const al = edgeAlpha(e)*ap*(dark?1:.85);
    const g = ctx.createLinearGradient(x1,y1,x2,y2);
    const ca=KC(a.kind), cb=KC(b.kind);
    g.addColorStop(0, ca); g.addColorStop(1, cb);
    ctx.globalAlpha = al; ctx.strokeStyle = g;
    ctx.lineWidth = Math.max(1, (e.type==="links_to"?2:1.35)*Math.min(1.6,scale));
    ctx.beginPath(); ctx.moveTo(x1,y1); ctx.quadraticCurveTo(cx2,cy2,x2,y2); ctx.stroke(); });
  ctx.globalAlpha = 1;
  nodes.forEach(n => { if(n.hidden) return;
    const ap = appear(n); if(ap<=0) return;
    const x=sx(n), y=sy(n), r=n.r*n.hr*scale*ease(ap);
    if(x<-r*4||x>W+r*4||y<-r*4||y>H+r*4) return;
    const sp = sprite(n.kind, n.r*n.hr, n.meta);
    const dim = selN ? (neigh.has(n.id)?1:.12) : (n.match?1:.13);
    if (dim < .5) { ctx.globalAlpha = 1; return; }
    n.hr += ((n===hoverN||n===selN?1.3:1)-n.hr)*.16;
    ctx.globalAlpha = .9*ease(ap)*dim;
    ctx.drawImage(sp.cv, x-sp.R*n.hr*scale, y-sp.R*n.hr*scale, sp.R*2*n.hr*scale, sp.R*2*n.hr*scale);
    if(n===hoverN||n===selN){
      ctx.globalAlpha = .55*ease(ap);
      ctx.strokeStyle = KC(n.kind); ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.arc(x,y,r+5,0,7); ctx.stroke(); }
    const wantLabel = (n===hoverN||n===selN) ||
      (!(n.meta&&n.meta.twin) && (neigh&&neigh.has(n.id))) ||
      (!(n.meta&&n.meta.twin) && scale>.85 && n.match && (n.deg>2||n.kind==="video"||n.kind==="concept"));
    if(wantLabel){
      let la = Math.min(1,(scale-.6)/.5)*ease(ap)*dim;
      if(n===hoverN||n===selN) la = 1;
      if(la>.03){
        ctx.globalAlpha = la;
        const fs = 11.5;
        ctx.font = fs+"px "+getComputedStyle(document.body).fontFamily;
        ctx.textAlign = "center"; ctx.textBaseline = "top";
        const lbl = n.label.length>34 ? n.label.slice(0,33)+"…" : n.label;
        const tw = ctx.measureText(lbl).width;
        const ly = y+r+7;
        ctx.fillStyle = T().labelBg;
        roundRect(x-tw/2-5, ly-2, tw+10, fs+5, 4); ctx.fill();
        ctx.fillStyle = n===selN ? T().labelInk : T().labelInk;
        ctx.globalAlpha = la*.92; ctx.fillText(lbl, x, ly); } }
    ctx.globalAlpha = 1; });
}
function loop(){ if(alpha>.014||dragN) tick(); draw(); requestAnimationFrame(loop); }
loop();

/* theme switching */
const themeBtns = [...document.querySelectorAll("#themes button")];
function setTheme(t){
  if(!THEMES[t]) return;
  theme = t;
  document.documentElement.dataset.theme = t;
  try{ localStorage.setItem("th-theme", t); }catch(e){}
  sprites.clear();
  themeBtns.forEach(b => b.classList.toggle("on", b.dataset.t===t));
  buildKinds();
}
themeBtns.forEach(b => b.onclick = () => setTheme(b.dataset.t));

/* input */
cv.addEventListener("wheel", e => { e.preventDefault();
  const f = e.deltaY<0?1.13:.885, px=e.offsetX, py=e.offsetY;
  const ns = Math.min(4.5, Math.max(.16, scale*f));
  ox = px-(px-ox)*(ns/scale); oy = py-(py-oy)*(ns/scale); scale = ns; }, {passive:false});
function nodeAt(px,py){ let best=null,bd=1e9;
  nodes.forEach(n => { if(n.hidden) return;
    const dx=sx(n)-px, dy=sy(n)-py, d=dx*dx+dy*dy, r=(n.r*n.hr+5)*scale;
    if(d<r*r && d<bd){ bd=d; best=n; } }); return best; }
cv.addEventListener("mousedown", e => { const n=nodeAt(e.offsetX,e.offsetY);
  if(n){ dragN=n; n.vx=n.vy=0; } else panning={x:e.offsetX,y:e.offsetY};
  cv.classList.add("grabbing"); });
addEventListener("mousemove", e => {
  const rect=cv.getBoundingClientRect();
  const mx=e.clientX-rect.left, my=e.clientY-rect.top;
  if(dragN){ dragN.x=wx(mx); dragN.y=wy(my); reheat(); hideTip(); return; }
  if(panning){ ox+=mx-panning.x; oy+=my-panning.y; panning={x:mx,y:my}; return; }
  hoverN=nodeAt(mx,my);
  cv.classList.toggle("hovering", !!hoverN);
  if(hoverN && appear(hoverN)>.5){
    tip.innerHTML = `<div class="k" style="color:${KC(hoverN.kind)}">${KINDS[hoverN.kind]?.label||hoverN.kind}</div>`+
      `<div class="t">${esc(hoverN.label)}</div>`+
      (hoverN.url?`<div class="u">${esc(hoverN.url)}</div>`:"")+
      `<div class="c">${hoverN.deg} connection${hoverN.deg===1?"":"s"}</div>`;
    tip.style.display="block";
    tip.style.left = Math.min(innerWidth-360, mx+16)+"px";
    tip.style.top = Math.min(innerHeight-160, my+18)+"px";
  } else hideTip(); });
addEventListener("mouseup", () => { dragN=null; panning=null; cv.classList.remove("grabbing"); });
cv.addEventListener("click", e => { const n=nodeAt(e.offsetX,e.offsetY); if(n) select(n); });
cv.addEventListener("dblclick", e => { const n=nodeAt(e.offsetX,e.offsetY);
  if(n&&n.url) window.open(n.url,"_blank"); });
function hideTip(){ tip.style.display="none"; }
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;"); }
function roundRect(x,y,w,h,r){ ctx.beginPath();
  ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
function fmtViews(v){ const n=+v; if(!n) return "";
  if(n>=1e9) return (n/1e9).toFixed(1).replace(/\.0$/,"")+"B";
  if(n>=1e6) return (n/1e6).toFixed(1).replace(/\.0$/,"")+"M";
  if(n>=1e3) return (n/1e3).toFixed(1).replace(/\.0$/,"")+"K"; return String(n); }
function fmtLen(s){ s=+s; if(!s) return "";
  const m=Math.floor(s/60), h=Math.floor(m/60);
  return h ? `${h}:${String(m%60).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`
           : `${m}:${String(s%60).padStart(2,"0")}`; }
function fmtTs(iso){ if(!iso) return ""; const d=new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"}); }

function select(n){ selN=n; neigh=neighborhood(n); reheat(); hideTip();
  let html=`<div class="kind" style="color:${KC(n.kind)}">${KINDS[n.kind]?.label||n.kind}</div><h2>${esc(n.label)}</h2>`;
  if(n.url) html+=`<a class="url" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.url)}</a>`;
  const m=n.meta||{};
  const rows=[];
  if(m.channel) rows.push(["Channel", esc(m.channel)]);
  if(m.views) rows.push(["Views", fmtViews(m.views).replace(" views","")]);
  if(m.length) rows.push(["Length", fmtLen(m.length)]);
  if(m.time) rows.push(["Posted", fmtTs(m.time)]);
  if(m.transcript_paras) rows.push(["Transcript",
    m.transcript_paras===1 ? "captured" : `${m.transcript_paras} paragraphs`]);
  if(m.sources) rows.push(["Appears in", `${m.sources} source${m.sources===1?"":"s"}`]);
  if(m.tweets) rows.push(["Tweets", String(m.tweets)]);
  if(m.anchor) rows.push(["Link text", esc(m.anchor)]);
  if(m.fetch) rows.push(["Fetched via", esc(m.fetch)]);
  if(m.insight) rows.push(["Insight", esc(m.insight)]);
  if(rows.length){ html+=`<div class="hair"></div><div class="kv">`;
    rows.forEach(([a2,b2])=>{ html+=`<b>${a2}</b><span>${b2}</span>`; });
    html+=`</div>`; }
  if(m.snippet) html+=`<div class="hair"></div><div class="snip">${esc(m.snippet)}</div>`;
  if(m.transcript_head) html+=`<div class="hair"></div><div class="sechead">Transcript</div><div class="snip">${esc(m.transcript_head)}</div>`;
  const conn=[...new Set((adj.get(n.id)||[]).flatMap(e=>{
    const o=e.source===n.id?e.target:e.source; return byId.has(o)?[o]:[];}))];
  if(conn.length){
    html+=`<div class="hair"></div><div class="sechead">Connections &middot; ${conn.length}</div>`;
    conn.slice(0,30).forEach(id=>{ const c=byId.get(id);
      const et=(adj.get(n.id)||[]).find(e=>
        (e.source===n.id&&e.target===id)||(e.target===n.id&&e.source===id));
      const verb = et ? ({links_to:"linked from", authored_by:"by", features:"featuring",
        mentions:"mentions", same_as:"same as", semantic:"supports", related:"related to"}[et.type] || et.type) : "";
      html+=`<div class="conn-row" data-id="${esc(id)}">`+
        `<span class="dot" style="background:${KC(c.kind)}"></span>`+
        `<span class="cname">${esc(c.label)}</span>`+
        `<span class="verb">${verb}</span></div>`; }); }
  pbody.innerHTML=html; panel.classList.add("open");
  pbody.querySelectorAll(".conn-row").forEach(el =>
    el.onclick=()=>select(byId.get(el.dataset.id)));
}
pclose.onclick=()=>{ panel.classList.remove("open"); selN=null; neigh=null; };

/* reports side panel */
const REPORTS = __REPORTS_JSON__;
const reportsEl=document.getElementById("reports"), rbody=document.getElementById("rbody"),
      rtitle=document.getElementById("rtitle"), rback=document.getElementById("rback");
function rList(){
  rtitle.textContent = "Reports"; rback.style.display = "none";
  let h = '<div class="rlist">';
  if (REPORTS.index) h += `<div class="ritem" data-i="-1"><span class="rname">INDEX</span><br>${REPORTS.index.title}</div>`;
  REPORTS.docs.forEach((d,i) => { h += `<div class="ritem" data-i="${i}"><span class="rname">${d.tab}</span><br>${d.title}</div>`; });
  rbody.innerHTML = h + '</div>';
  rbody.querySelectorAll(".ritem").forEach(el => el.onclick = () => {
    const i = +el.dataset.i;
    if (i === -1) rView(REPORTS.index.title, REPORTS.index.html);
    else rView(REPORTS.docs[i].title, REPORTS.docs[i].html);
  });
}
function rView(title, html){ rtitle.textContent = title; rback.style.display = "inline-block"; rbody.innerHTML = html; rbody.scrollTop = 0; }
rback.onclick = rList;
document.getElementById("rclose").onclick = () => reportsEl.classList.remove("open");
document.getElementById("reports-btn").onclick = () => {
  reportsEl.classList.toggle("open");
  if (reportsEl.classList.contains("open")) rList();
};

/* search */
const search=document.getElementById("search"), nores=document.getElementById("nores");
function applySearch(){ const t=search.value.trim().toLowerCase();
  let hits=0;
  nodes.forEach(n => { n.match = !t || n.label.toLowerCase().includes(t) ||
    (n.url||"").toLowerCase().includes(t) ||
    JSON.stringify(n.meta||{}).toLowerCase().includes(t);
    if(n.match&&t) hits++; });
  nores.style.display = (t && hits===0) ? "grid" : "none";
  if(t&&hits===0) document.getElementById("noq").textContent = '"'+search.value+'"';
}
search.addEventListener("input", applySearch);
addEventListener("keydown", e => {
  if(e.key==="/" && document.activeElement!==search){ e.preventDefault(); search.focus(); }
  else if(["1","2","3","4"].includes(e.key) && document.activeElement!==search){
    setTheme(["etched","mono","platinum","wireframe"][+e.key-1]); }
  else if(e.key==="Escape"){
    hideTip();
    if(panel.classList.contains("open")){ panel.classList.remove("open"); selN=null; neigh=null; }
    else if(document.activeElement===search){ search.value=""; applySearch(); search.blur(); } } });
document.getElementById("reset").onclick=()=>{ scale=.95; ox=W/2; oy=H*.46; reheat(); };

/* kind pills (rebuilt per theme so dot colors follow the palette) */
const kindsEl=document.getElementById("kinds");
const counts={};
nodes.forEach(n=>counts[n.kind]=(counts[n.kind]||0)+1);
const kindOff = new Set();
function buildKinds(){
  kindsEl.innerHTML = "";
  Object.entries(KINDS).forEach(([kind,k]) => {
    if(!counts[kind]) return;
    const el=document.createElement("div"); el.className="kind-pill"; el.title="Toggle "+k.label;
    if (kindOff.has(kind)) el.classList.add("off");
    el.innerHTML=`<span class="dot" style="background:${KC(kind)}"></span>${k.label}`+
      `<span class="n">${counts[kind]}</span>`;
    el.onclick=()=>{ el.classList.toggle("off");
      if (el.classList.contains("off")) kindOff.add(kind); else kindOff.delete(kind);
      nodes.forEach(n=>{ if(n.kind===kind) n.hidden=el.classList.contains("off"); }); };
    kindsEl.appendChild(el); });
}
buildKinds();
setTheme(theme);

/* header meta + stats */
(function(){
  let s = DATA.meta || "";
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  const months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  if (m) s = `${months[+m[2]-1]} ${+m[3]}, ${m[1]} · ${m[4]}:${m[5]}`;
  document.getElementById("meta").textContent = s ? "harvested " + s : "";
})();
document.getElementById("stats").innerHTML =
  `<b>${nodes.length}</b> nodes · <b>${edges.length}</b> edges` +
  (counts.topic ? ` · <b>${counts.topic}</b> topics` : "");
window.__g = { nodes, edges, select, nodeAt, byId, setTheme };
</script>
</body>
</html>
"""



_MD_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")

def _md_inline(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = _MD_RE_BOLD.sub(r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s

def md_to_html(md: str) -> str:
    """Minimal markdown -> HTML for distillation files (headings, lists, tables, bold, links)."""
    out, lines = [], md.split("\n")
    i = 0
    list_stack = []
    def close_lists():
        while list_stack:
            out.append(f"</{list_stack.pop()}>")
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            close_lists(); i += 1; continue
        if s == "---":
            close_lists(); out.append("<hr>"); i += 1; continue
        m = re.match(r"^(#{1,4}) (.*)", s)
        if m:
            close_lists()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_md_inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-\s|:]+\|$", lines[i+1].strip()):
            close_lists()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^\|[-\s|:]+\|$", lines[i].strip()):
                    rows.append(cells)
                i += 1
            if rows:
                out.append("<table><tr>" + "".join(f"<th>{_md_inline(c)}</th>" for c in rows[0]) + "</tr>")
                for r in rows[1:]:
                    out.append("<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>")
                out.append("</table>")
            continue
        m = re.match(r"^[-*] (.*)", s)
        if m:
            if not list_stack or list_stack[-1] != "ul":
                close_lists(); list_stack.append("ul"); out.append("<ul>")
            out.append(f"<li>{_md_inline(m.group(1))}</li>"); i += 1; continue
        m = re.match(r"^\d+\. (.*)", s)
        if m:
            if not list_stack or list_stack[-1] != "ol":
                close_lists(); list_stack.append("ol"); out.append("<ol>")
            out.append(f"<li>{_md_inline(m.group(1))}</li>"); i += 1; continue
        close_lists()
        out.append(f"<p>{_md_inline(s)}</p>"); i += 1
    close_lists()
    return "\n".join(out)

def render_html(graph: dict, theme: str = "etched", reports: dict | None = None) -> str:
    data_json = json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")
    meta_title = (graph.get("meta") or "harvest").replace("<", "&lt;")
    logo_src = ""
    for base in Path(__file__).resolve().parents:
        cand = base / "assets" / "brand" / "tab-harvest-logo-small.png"
        if cand.exists():
            logo_src = "data:image/png;base64," + base64.b64encode(cand.read_bytes()).decode()
            break
    reports_json = json.dumps(reports or {"docs": []}, ensure_ascii=False).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json).replace("__THEME_DEFAULT__", theme).replace("__THEME_DEFAULT_JSON__", json.dumps(theme)).replace("__LOGO_SRC__", logo_src).replace("__REPORTS_JSON__", reports_json)
    return html.replace("<title>Knowledge Graph</title>",
                        f"<title>Knowledge Graph {meta_title}</title>", 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("harvest", help="harvest.json (or graph.json with --refresh)")
    ap.add_argument("--refresh", action="store_true", help="input is an enriched graph.json; re-render only")
    ap.add_argument("--out", default=None, help="output dir (default: beside input)")
    ap.add_argument("--html", default=None, help="explicit html output path (refresh mode)")
    ap.add_argument("--theme", default="etched", choices=["etched", "mono", "platinum", "wireframe"],
                    help="default theme (all four remain toggleable in the UI)")
    args = ap.parse_args(argv)

    src = Path(args.harvest)
    out_dir = Path(args.out) if args.out else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    reports = {"docs": []}
    ddir = out_dir / "distilled"
    if ddir.is_dir():
        index_html, index_title = None, "INDEX"
        docs = []
        for f in sorted(ddir.glob("*.md")):
            html = md_to_html(f.read_text(encoding="utf-8", errors="replace"))
            title_m = re.search(r"^# (.+)$", html, re.M)
            if f.name.startswith("INDEX"):
                index_html, index_title = html, title_m.group(1).strip() if title_m else "INDEX"
            else:
                docs.append({"tab": f.name[:2], "file": f.name,
                             "title": title_m.group(1).strip() if title_m else f.stem, "html": html})
        if index_html or docs:
            reports = {"index": ({"title": index_title, "html": index_html} if index_html else None),
                       "docs": docs}

    if args.refresh:
        graph = json.loads(src.read_text(encoding="utf-8"))
        html_path = Path(args.html) if args.html else out_dir / "graph.html"
        html_path.write_text(render_html(graph, args.theme, reports), encoding="utf-8")
        print(json.dumps({"ok": True, "graph": str(src), "html": str(html_path),
                          "nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", []))}))
        return 0

    payload = json.loads(src.read_text(encoding="utf-8"))
    graph = build_graph(payload)
    (out_dir / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "graph.html").write_text(render_html(graph, args.theme, reports), encoding="utf-8")
    print(json.dumps({"ok": True, "nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
                      "graph": str(out_dir / "graph.json"), "html": str(out_dir / "graph.html")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
