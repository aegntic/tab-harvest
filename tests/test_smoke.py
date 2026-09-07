#!/usr/bin/env python3
"""Smoke tests: CLI wiring, graph builder against the real example harvest,
doctor output, and installability. No live browser needed."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


# 1. version + help work from source tree
r = subprocess.run([sys.executable, "-m", "tab_harvest", "--version"],
                   capture_output=True, text=True, env={**__import__("os").environ,
                   "PYTHONPATH": str(REPO / "src")})
check("module --version", r.returncode == 0 and "1.0.0" in r.stdout, r.stderr[-200:])

r = subprocess.run([sys.executable, "-m", "tab_harvest", "--help"],
                   capture_output=True, text=True, env={**__import__("os").environ,
                   "PYTHONPATH": str(REPO / "src")})
check("module --help", r.returncode == 0 and "harvest" in r.stdout and "doctor" in r.stdout, r.stderr[-200:])

# 2. graph subcommand against the real example harvest
with tempfile.TemporaryDirectory() as td:
    out = Path(td) / "graph-out"
    r = subprocess.run([sys.executable, "-m", "tab_harvest", "graph",
                        str(REPO / "examples" / "harvest-youtube.json"), "--out", str(out)],
                       capture_output=True, text=True, env={**__import__("os").environ,
                       "PYTHONPATH": str(REPO / "src")})
    ok = r.returncode == 0 and (out / "graph.json").exists() and (out / "graph.html").exists()
    check("graph from example harvest", ok, r.stderr[-300:])
    if ok:
        g = json.loads((out / "graph.json").read_text())
        check("graph has nodes+edges", len(g.get("nodes", [])) > 5 and len(g.get("edges", [])) > 5,
              f"nodes={len(g.get('nodes', []))} edges={len(g.get('edges', []))}")
        html = (out / "graph.html").read_text()
        check("graph.html is self-contained", "<script" in html and "cdn" not in html.lower())

    # 3. --refresh path (enrich + re-render)
    r2 = subprocess.run([sys.executable, "-m", "tab_harvest", "graph",
                         str(out / "graph.json"), "--refresh", "--html", str(out / "g2.html")],
                        capture_output=True, text=True, env={**__import__("os").environ,
                        "PYTHONPATH": str(REPO / "src")})
    check("graph --refresh re-render", r2.returncode == 0 and (out / "g2.html").exists(), r2.stderr[-300:])

# 4. doctor: runs, checks deps, exits per CDP state
r = subprocess.run([sys.executable, "-m", "tab_harvest", "doctor"],
                   capture_output=True, text=True, env={**__import__("os").environ,
                   "PYTHONPATH": str(REPO / "src")})
check("doctor runs", r.returncode in (0, 1) and "yt-dlp" in r.stdout, r.stderr[-300:])
check("doctor prints macOS recipe", "Google Chrome" in r.stdout)

# 5. import surface sanity
sys.path.insert(0, str(REPO / "src"))
import tab_harvest  # noqa: E402
check("import tab_harvest", tab_harvest.__version__ == "1.0.0")
from tab_harvest import harvest as h  # noqa: E402
check("harvest module imports", hasattr(h, "main"))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
    sys.exit(1)
print("all smoke tests passed")
