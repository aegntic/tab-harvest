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

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Knowledge Graph</title>
<style>
  :root {
    --ink: #0b0e14; --ink-2: #0e1219; --panel: #11151d; --panel-2: #151a24;
    --line: rgba(233,237,243,.08); --line-2: rgba(233,237,243,.14);
    --fg: #e9edf3; --dim: #8b95a5; --faint: #5b6472;
    --video:#f26d5f; --x:#45b8dc; --page:#55b77e; --chan:#d9a25f;
    --topic:#9c86e8; --concept:#b48be8; --action:#ddb54c; --question:#7d8a9c;
    --tab:#e9edf3;
    --mono: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", Menlo, Consolas, monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; overflow: hidden; }
  body { background: var(--ink); color: var(--fg);
         font: 14px/1.5 system-ui, "Segoe UI Variable Display", "Avenir Next", sans-serif;
         -webkit-font-smoothing: antialiased; }
  body::after { content:""; position:fixed; inset:0; pointer-events:none; z-index:4;
    background: radial-gradient(120% 90% at 50% 42%, transparent 55%, rgba(4,6,10,.55) 100%); }
  #cv { position: fixed; inset: 0; display:block; cursor: grab; }
  #cv.grabbing { cursor: grabbing; }
  #cv.hovering { cursor: pointer; }

  /* top bar */
  header { position: fixed; top: 0; left: 0; right: 0; z-index: 10; height: 60px;
    display: flex; align-items: center; gap: 20px; padding: 0 22px;
    background: linear-gradient(180deg, rgba(11,14,20,.92), rgba(11,14,20,.72));
    backdrop-filter: blur(14px) saturate(1.3); -webkit-backdrop-filter: blur(14px) saturate(1.3);
    border-bottom: 1px solid var(--line); }
  .brand h1 { font-size: 14.5px; font-weight: 640; letter-spacing: -.01em; white-space: nowrap; }
  .brand .meta { font: 10.5px/1 var(--mono); color: var(--faint); margin-top: 4px;
                 font-variant-numeric: tabular-nums; letter-spacing: .02em; }
  .brand .meta:empty { display: none; }
  .searchbox { position: relative; flex: 0 1 340px; }
  .searchbox svg { position:absolute; left:11px; top:50%; transform:translateY(-50%);
                   color: var(--faint); pointer-events:none; }
  #search { width: 100%; background: var(--ink-2); border: 1px solid var(--line);
    color: var(--fg); border-radius: 9px; padding: 8px 58px 8px 34px; font-size: 13px;
    outline: none; transition: border-color .18s, background .18s; }
  #search:focus { border-color: var(--line-2); background: var(--panel); }
  #search::placeholder { color: var(--faint); }
  .kbd { position:absolute; right:9px; top:50%; transform:translateY(-50%);
    font: 10px var(--mono); color: var(--faint); border: 1px solid var(--line);
    border-radius: 5px; padding: 2px 6px; pointer-events:none; }
  #stats { margin-left: auto; font: 11px var(--mono); color: var(--dim);
           font-variant-numeric: tabular-nums; white-space: nowrap; letter-spacing: .01em; }
  #stats b { color: var(--fg); font-weight: 560; }
  #reset { background: none; border: 1px solid var(--line); color: var(--dim);
    border-radius: 8px; padding: 6.5px 13px; font: 11.5px system-ui; cursor: pointer;
    transition: color .15s, border-color .15s; }
  #reset:hover { color: var(--fg); border-color: var(--line-2); }
  #reset:active { transform: translateY(1px); }

  /* kind pills (filter + legend merged) */
  #kinds { position: fixed; left: 18px; bottom: 18px; z-index: 10; display: flex;
           flex-direction: column; gap: 5px; }
  .kind-pill { display: flex; align-items: center; gap: 8px; padding: 5px 11px 5px 9px;
    background: rgba(17,21,29,.82); border: 1px solid var(--line); border-radius: 999px;
    cursor: pointer; user-select: none; font-size: 11.5px; color: var(--dim);
    backdrop-filter: blur(8px); transition: opacity .15s, color .15s, border-color .15s; }
  .kind-pill:hover { color: var(--fg); border-color: var(--line-2); }
  .kind-pill .dot { width: 8px; height: 8px; border-radius: 50%; flex: none;
    box-shadow: 0 0 8px currentColor; }
  .kind-pill .n { font: 10px var(--mono); color: var(--faint); font-variant-numeric: tabular-nums; }
  .kind-pill.off { opacity: .38; }
  .kind-pill.off .dot { box-shadow: none; background: var(--faint) !important; }

  /* tooltip */
  #tip { position: fixed; z-index: 20; pointer-events: none; display: none;
    max-width: 340px; background: var(--panel-2); border: 1px solid var(--line-2);
    border-radius: 10px; padding: 10px 13px;
    box-shadow: 0 12px 40px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.05); }
  #tip .k { font: 9.5px var(--mono); text-transform: uppercase; letter-spacing: .14em; }
  #tip .t { font-size: 12.5px; font-weight: 560; margin-top: 3px; line-height: 1.35; }
  #tip .u { font: 10px var(--mono); color: var(--faint); margin-top: 4px;
            word-break: break-all; max-width: 300px; }
  #tip .c { font: 10px var(--mono); color: var(--faint); margin-top: 5px; }

  /* detail panel */
  #panel { position: fixed; top: 60px; right: 0; bottom: 0; width: 400px; z-index: 12;
    background: var(--panel); border-left: 1px solid var(--line);
    transform: translateX(100%); transition: transform .26s cubic-bezier(.2,.9,.25,1);
    display: flex; flex-direction: column; }
  #panel.open { transform: translateX(0); }
  @media (prefers-reduced-motion: reduce) { #panel { transition: none; } }
  #panel .scroll { overflow-y: auto; padding: 24px 24px 40px; flex: 1; }
  #pclose { position: absolute; top: 14px; right: 16px; width: 28px; height: 28px;
    display: grid; place-items: center; border-radius: 8px; cursor: pointer;
    color: var(--faint); border: 1px solid transparent; transition: all .15s;
    background: none; font-size: 15px; }
  #pclose:hover { color: var(--fg); border-color: var(--line); }
  #panel .kind { font: 9.5px var(--mono); text-transform: uppercase; letter-spacing: .16em; }
  #panel h2 { font-size: 17px; font-weight: 620; letter-spacing: -.012em; line-height: 1.3;
    margin: 8px 44px 0 0; }
  #panel .url { display: block; font: 10.5px var(--mono); color: #6fa8d8; margin-top: 9px;
    word-break: break-all; text-decoration: none; line-height: 1.5; }
  #panel .url:hover { text-decoration: underline; text-underline-offset: 3px; }
  #panel .hair { height: 1px; background: var(--line); margin: 18px 0; }
  #panel .kv { display: grid; grid-template-columns: 108px 1fr; gap: 7px 12px;
    font-size: 12px; align-items: baseline; }
  #panel .kv b { color: var(--faint); font-weight: 480; font-size: 11px;
    font-family: system-ui, sans-serif; letter-spacing: .01em;
    text-transform: capitalize; }
  #panel .kv span { color: var(--fg); overflow-wrap: anywhere; }
  #panel .snip { margin-top: 4px; font-size: 12px; color: var(--dim); line-height: 1.6;
    border-left: 2px solid var(--line-2); padding-left: 12px; }
  #panel .sechead { font: 9.5px var(--mono); color: var(--faint); text-transform: uppercase;
    letter-spacing: .16em; margin: 20px 0 10px; }
  .conn-row { display: flex; align-items: center; gap: 9px; padding: 7px 9px; margin: 0 -9px;
    border-radius: 8px; cursor: pointer; font-size: 12.5px; color: var(--dim);
    transition: background .12s, color .12s; }
  .conn-row:hover { background: var(--ink-2); color: var(--fg); }
  .conn-row .dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
  .conn-row .cname { color: inherit; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; }
  .conn-row .verb { margin-left: auto; flex: none; font: 10px var(--mono);
    color: var(--faint); padding-left: 10px; }

  /* no-results */
  #nores { position: fixed; inset: 60px 0 0 0; display: none; place-items: center;
    z-index: 8; pointer-events: none; }
  #nores .box { text-align: center; color: var(--faint); }
  #nores .box .q { font: 13px var(--mono); color: var(--dim); margin-top: 8px; }
</style>
</head>
<body>
<header>
  <div class="brand">
    <h1>Knowledge Graph</h1>
    <div class="meta" id="meta"></div>
  </div>
  <div class="searchbox">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
    <input id="search" placeholder="Search nodes" autocomplete="off" spellcheck="false">
    <span class="kbd">/</span>
  </div>
  <div id="stats"></div>
  <button id="reset" title="Reset view">Reset view</button>
</header>
<canvas id="cv"></canvas>
<div id="kinds"></div>
<div id="tip"></div>
<div id="nores"><div class="box"><div>No nodes match</div><div class="q" id="noq"></div></div></div>
<aside id="panel">
  <button id="pclose" title="Close">×</button>
  <div class="scroll" id="pbody"></div>
</aside>
<script>
"use strict";
const DATA = __DATA_JSON__;
const tip=document.getElementById("tip"), panel=document.getElementById("panel"),
      pbody=document.getElementById("pbody"), pclose=document.getElementById("pclose");
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const KINDS = {
  video:   {c:"#f26d5f", r:13, label:"video"},
  tab:     {c:"#e9edf3", r:15, label:"tab"},
  page:    {c:"#55b77e", r:9,  label:"page"},
  tweet:   {c:"#45b8dc", r:9,  label:"tweet"},
  x_feed:  {c:"#45b8dc", r:12, label:"x feed"},
  channel: {c:"#d9a25f", r:10, label:"channel"},
  author:  {c:"#d9a25f", r:7,  label:"author"},
  topic:   {c:"#9c86e8", r:7,  label:"topic"},
  concept: {c:"#b48be8", r:11, label:"concept"},
  action:  {c:"#ddb54c", r:10, label:"action"},
  question:{c:"#7d8a9c", r:9,  label:"question"},
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

/* glow sprites (pre-rendered per kind x radius bucket) */
const sprites = new Map();
function sprite(kind, r, meta) {
  const key = kind+":"+Math.round(r);
  if (sprites.has(key)) return sprites.get(key);
  const c = KINDS[kind]?.c || "#7d8a9c";
  const R = Math.ceil(r*3.2), cx = R, cy = R;
  const cv2 = document.createElement("canvas"); cv2.width = cv2.height = R*2;
  const g = cv2.getContext("2d");
  const grd = g.createRadialGradient(cx,cy,r*.2, cx,cy,r*2.6);
  grd.addColorStop(0, c+"55"); grd.addColorStop(.35, c+"22"); grd.addColorStop(1, c+"00");
  g.fillStyle = grd; g.beginPath(); g.arc(cx,cy,r*2.6,0,7); g.fill();
  const body = g.createRadialGradient(cx-r*.3,cy-r*.35,r*.1, cx,cy,r);
  body.addColorStop(0, "#ffffff"); body.addColorStop(.25, c); body.addColorStop(1, shade(c,-.35));
  g.fillStyle = body; g.beginPath(); g.arc(cx,cy,r,0,7); g.fill();
  g.strokeStyle = "rgba(11,14,20,.85)"; g.lineWidth = Math.max(1.4, r*.14);
  g.beginPath(); g.arc(cx,cy,r,0,7); g.stroke();
  if (kind === "topic" || kind === "concept") {
    g.setLineDash([r*.45, r*.4]); g.strokeStyle = "rgba(233,237,243,.35)"; g.lineWidth = 1;
    g.beginPath(); g.arc(cx,cy,r+3.5,0,7); g.stroke();
  } else if (meta && meta.twin) {
    g.setLineDash([r*.5, r*.45]); g.strokeStyle = "rgba(233,237,243,.5)"; g.lineWidth = 1.2;
    g.beginPath(); g.arc(cx,cy,r+3.5,0,7); g.stroke();
  }
  const out = {cv: cv2, R};
  sprites.set(key, out); return out;
}
function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16);
  const ch = v => Math.max(0, Math.min(255, Math.round(v + v*f)));
  return `rgb(${ch(n>>16)},${ch((n>>8)&255)},${ch(n&255)})`;
}

/* camera + physics */
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
let W,H,DPR = Math.min(2, window.devicePixelRatio||1);
function resize(){ W=innerWidth; H=innerHeight; cv.width=W*DPR; cv.height=H*DPR;
  cv.style.width=W+"px"; cv.style.height=H+"px"; ctx.setTransform(DPR,0,0,DPR,0,0); }
addEventListener("resize", resize); resize();
let scale=.95, ox=W/2, oy=H/2+30, alpha=REDUCED?0.25:0.9, hoverN=null, selN=null,
    dragN=null, panning=null, neigh=null;
const T0 = performance.now();
function appear(n){ if (REDUCED) return 1;
  return Math.min(1, Math.max(0, (performance.now()-T0-120-n.idx*14)/650)); }
function ease(t){ return 1-Math.pow(1-t,3); }
function sx(n){ return n.x*scale+ox; } function sy(n){ return n.y*scale+oy; }
function wx(px){ return (px-ox)/scale; } function wy(py){ return (py-oy)/scale; }
function reheat(){ alpha = Math.max(alpha, REDUCED?.15:.4); }
function neighborhood(n){ if(!n) return null;
  const s = new Set([n.id]);
  (adj.get(n.id)||[]).forEach(e => s.add(e.source===n.id?e.target:e.source));
  return s; }

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
  ctx.lineCap = "round";
  edges.forEach(e => { const a=byId.get(e.source), b=byId.get(e.target); if(!a||!b) return;
    if(a.hidden||b.hidden) return;
    const ap = Math.min(appear(a), appear(b)); if(ap<=0) return;
    const x1=sx(a),y1=sy(a),x2=sx(b),y2=sy(b);
    const mx=(x1+x2)/2, my=(y1+y2)/2;
    const dx=x2-x1, dy=y2-y1, len=Math.sqrt(dx*dx+dy*dy)||1;
    const cur=(CURVE[e.type]||.15)*len*.6;
    const cx2=mx-dy/len*cur, cy2=my+dx/len*cur;
    const al = edgeAlpha(e)*ap;
    const g = ctx.createLinearGradient(x1,y1,x2,y2);
    const ca=KINDS[a.kind]?.c||"#7d8a9c", cb=KINDS[b.kind]?.c||"#7d8a9c";
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
    if (dim < .5) { ctx.globalAlpha = 1; return; }  // dimmed: orb only, no label
    n.hr += ((n===hoverN||n===selN?1.3:1)-n.hr)*.16;
    ctx.globalAlpha = .9*ease(ap)*dim;
    ctx.drawImage(sp.cv, x-sp.R*n.hr*scale, y-sp.R*n.hr*scale, sp.R*2*n.hr*scale, sp.R*2*n.hr*scale);
    if(n===hoverN||n===selN){
      ctx.globalAlpha = .5*ease(ap);
      ctx.strokeStyle = KINDS[n.kind]?.c||"#7d8a9c"; ctx.lineWidth = 1.2;
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
        ctx.font = fs+"px system-ui, sans-serif";
        ctx.textAlign = "center"; ctx.textBaseline = "top";
        const lbl = n.label.length>34 ? n.label.slice(0,33)+"…" : n.label;
        const tw = ctx.measureText(lbl).width;
        const ly = y+r+7;
        ctx.fillStyle = "rgba(9,11,16,.82)";
        roundRect(x-tw/2-5, ly-2, tw+10, fs+5, 4); ctx.fill();
        ctx.fillStyle = n===selN ? "#f2f5f9" : "#ccd4df";
        ctx.fillText(lbl, x, ly); } }
    ctx.globalAlpha = 1; });
}
function loop(){ if(alpha>.014||dragN) tick(); draw(); requestAnimationFrame(loop); }
loop();

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
    const k=KINDS[hoverN.kind]||{c:"#7d8a9c",label:hoverN.kind};
    tip.innerHTML = `<div class="k" style="color:${k.c}">${k.label}</div>`+
      `<div class="t">${esc(hoverN.label)}</div>`+
      (hoverN.url?`<div class="u">${esc(hoverN.url)}</div>`:"")+
      `<div class="c">${hoverN.deg} connection${hoverN.deg===1?"":"s"}</div>`;
    tip.style.display="block";
    tip.style.left = Math.min(innerWidth-360, mx+16)+"px";
    tip.style.top = Math.min(innerHeight-120, my+18)+"px";
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
  const k=KINDS[n.kind]||{c:"#7d8a9c",label:n.kind};
  let html=`<div class="kind" style="color:${k.c}">${k.label}</div><h2>${esc(n.label)}</h2>`;
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
    html+=`<div class="sechead">Connections &middot; ${conn.length}</div>`;
    conn.slice(0,30).forEach(id=>{ const c=byId.get(id), ck=KINDS[c.kind]||{c:"#7d8a9c"};
      const et=(adj.get(n.id)||[]).find(e=>
        (e.source===n.id&&e.target===id)||(e.target===n.id&&e.source===id));
      const verb = et ? ({links_to:"linked from", authored_by:"by", features:"featuring",
        mentions:"mentions", same_as:"same as", semantic:"supports", related:"related to"}[et.type] || et.type) : "";
      html+=`<div class="conn-row" data-id="${esc(id)}">`+
        `<span class="dot" style="background:${ck.c}"></span>`+
        `<span class="cname">${esc(c.label)}</span>`+
        `<span class="verb">${verb}</span></div>`; }); }
  pbody.innerHTML=html; panel.classList.add("open");
  pbody.querySelectorAll(".conn-row").forEach(el =>
    el.onclick=()=>select(byId.get(el.dataset.id)));
}
pclose.onclick=()=>{ panel.classList.remove("open"); selN=null; neigh=null; };

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
  else if(e.key==="Escape"){
    hideTip();
    if(panel.classList.contains("open") && !selN?.keep){ panel.classList.remove("open"); selN=null; neigh=null; }
    else if(document.activeElement===search){ search.value=""; applySearch(); search.blur(); }
    else { panel.classList.remove("open"); selN=null; neigh=null; } } });
document.getElementById("reset").onclick=()=>{ scale=.95; ox=W/2; oy=H/2+30; reheat(); };

/* kind pills */
const kindsEl=document.getElementById("kinds");
const counts={};
nodes.forEach(n=>counts[n.kind]=(counts[n.kind]||0)+1);
Object.entries(KINDS).forEach(([kind,k]) => {
  if(!counts[kind]) return;
  const el=document.createElement("div"); el.className="kind-pill"; el.title="Toggle "+k.label;
  el.innerHTML=`<span class="dot" style="background:${k.c};color:${k.c}"></span>${k.label}`+
    `<span class="n">${counts[kind]}</span>`;
  el.onclick=()=>{ el.classList.toggle("off");
    nodes.forEach(n=>{ if(n.kind===kind) n.hidden=el.classList.contains("off"); }); };
  kindsEl.appendChild(el); });

/* header meta */
(function(){
  let s = DATA.meta || "";
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
  const months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  if (m) s = `${months[+m[2]-1]} ${+m[3]}, ${m[1]} · ${m[4]}:${m[5]}`;
  document.getElementById("meta").textContent = s ? "harvested " + s : "";
})();
document.getElementById("stats").innerHTML =
  `<b>${nodes.length}</b> nodes &middot; <b>${edges.length}</b> edges` +
  (counts.topic ? ` &middot; <b>${counts.topic}</b> topics` : "");
window.__g = { nodes, edges, select, nodeAt, byId };  // debug/e2e handle
</script>
</body>
</html>
"""


def render_html(graph: dict) -> str:
    data_json = json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")
    meta_title = (graph.get("meta") or "harvest").replace("<", "&lt;")
    html = HTML_TEMPLATE.replace("__DATA_JSON__", data_json)
    return html.replace("<title>Knowledge Graph</title>",
                        f"<title>Knowledge Graph {meta_title}</title>", 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("harvest", help="harvest.json (or graph.json with --refresh)")
    ap.add_argument("--refresh", action="store_true", help="input is an enriched graph.json; re-render only")
    ap.add_argument("--out", default=None, help="output dir (default: beside input)")
    ap.add_argument("--html", default=None, help="explicit html output path (refresh mode)")
    args = ap.parse_args()

    src = Path(args.harvest)
    out_dir = Path(args.out) if args.out else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.refresh:
        graph = json.loads(src.read_text(encoding="utf-8"))
        html_path = Path(args.html) if args.html else out_dir / "graph.html"
        html_path.write_text(render_html(graph), encoding="utf-8")
        print(json.dumps({"ok": True, "graph": str(src), "html": str(html_path),
                          "nodes": len(graph.get("nodes", [])), "edges": len(graph.get("edges", []))}))
        return 0

    payload = json.loads(src.read_text(encoding="utf-8"))
    graph = build_graph(payload)
    (out_dir / "graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "graph.html").write_text(render_html(graph), encoding="utf-8")
    print(json.dumps({"ok": True, "nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
                      "graph": str(out_dir / "graph.json"), "html": str(out_dir / "graph.html")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
