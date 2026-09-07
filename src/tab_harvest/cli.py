#!/usr/bin/env python3
"""tab-harvest - standalone browser knowledge extraction.

Attaches over CDP to an already-running browser (read-only) and harvests
every open tab: full structured page content, YouTube videos with complete
transcripts (yt-dlp primary engine, three browser fallbacks), X/Twitter tabs
as tweet lists, plus the best tier-1 links each tab points at. Every run
renders an interactive, offline-capable knowledge graph.

Subcommands:
  harvest   attach to a browser and extract everything
  graph     build/re-render the knowledge graph from a harvest
  doctor    check dependencies and print platform bring-up recipes
"""

from __future__ import annotations

import argparse
import platform
import shutil
import socket
import sys

__version__ = "1.0.0"

DOCTOR_BANNER = r"""
  _                          _   _             _
 | |__   __ _ ___  ___ _ __| |_(_)_ __   __ _| |___
 | '_ \ / _` / __|/ _ \ '__| __| | '_ \ / _` | / __|
 | | | | (_| \__ \  __/ |  | |_| | | | | (_| | \__ \
 |_| |_|\__,_|___/\___|_|   \__|_|_| |_|\__,_|_|___/
"""


def _check(label: str, ok: bool, hint: str = "") -> bool:
    mark = "ok" if ok else "MISSING"
    print(f"  [{mark:>7}] {label}" + (f"  — {hint}" if hint and not ok else ""))
    return ok


def _cdp_alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


def cmd_doctor(args: argparse.Namespace) -> int:
    print(DOCTOR_BANNER)
    print(f"  tab-harvest {__version__} · python {sys.version.split()[0]} · {platform.system()}\n")

    deps_ok = True
    deps_ok &= _check("python >= 3.11", sys.version_info >= (3, 11))
    _check("playwright (python)", _import_ok("playwright"), "pip install playwright")
    exe = shutil.which("yt-dlp")
    ytdlp_ok = exe is not None or _venv_ytdlp() is not None
    _check("yt-dlp (transcript engine)", ytdlp_ok, "pip install yt-dlp")
    _check("curl (health probe)", shutil.which("curl") is not None)
    print()

    cdp = _cdp_alive(args.port)
    _check(f"CDP endpoint 127.0.0.1:{args.port}", cdp,
           "relaunch your browser with a debugging port (recipes below)")
    print()

    if deps_ok and cdp:
        print("  all green — run:  tab-harvest harvest --port %d" % args.port)
        return 0
    sysname = platform.system()
    print("  bring-up recipes:")
    print(f"""  macOS (Chrome):
    # Chrome must be fully quit first (Cmd+Q, check with: pgrep -x "Google Chrome")
    open -a "Google Chrome" --args --remote-debugging-port={args.port} --restore-last-session
    # or, explicit binary:
    "/Applications/Google Chrome.app/Contents/MACOS/Google Chrome" \\
      --remote-debugging-port={args.port} --user-data-dir="$HOME/Library/Application Support/Google/Chrome" \\
      --restore-last-session about:blank""")
    print(f"""  Windows (Chrome/Edge):
    :: Chrome must be fully quit first (check: tasklist | findstr chrome.exe)
    "%ProgramFiles%\\Google\\Chrome\\Application\\chrome.exe" ^
      --remote-debugging-port={args.port} --restore-last-session about:blank""")
    print(f"""  Linux (Chromium):
    pids=$(pgrep -x chromium || pgrep -x chrome) && kill $pids; sleep 2
    rm -f ~/.config/chromium/SingletonLock
    /usr/lib/chromium/chromium --remote-debugging-port={args.port} \\
      --user-data-dir=$HOME/.config/chromium --password-store=gnome-libsecret \\
      --no-first-run --restore-last-session about:blank
  (this host: {sysname})""")
    print(f"""
  verify:  curl -s http://127.0.0.1:{args.port}/json/version

  note: relaunching restores your session, but unsaved PWA windows may be
  closed. tab-harvest itself never launches, navigates, or closes anything.""")
    return 1 if not (deps_ok and cdp) else 0


def _import_ok(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def _venv_ytdlp():
    import sysconfig
    from pathlib import Path
    p = Path(sysconfig.get_path("purelib")) / "yt-dlp" / "__main__.py"
    return p if p.exists() else None


def cmd_harvest(args: argparse.Namespace) -> int:
    import asyncio

    from . import harvest
    argv = [
        "--port", str(args.port), "--out", args.out,
        "--max-per-tab", str(args.max_per_tab), "--max-total", str(args.max_total),
        "--tab-budget", str(args.tab_budget), "--timeout-ms", str(args.timeout_ms),
    ] + (["--allow-tabs"] if args.allow_tabs else [])
    return asyncio.run(harvest.main(argv=argv))


def cmd_graph(args: argparse.Namespace) -> int:
    from . import graph_builder
    argv = [args.input]
    if args.refresh:
        argv.append("--refresh")
    if args.out:
        argv += ["--out", args.out]
    if args.html:
        argv += ["--html", args.html]
    return graph_builder.main(argv=argv)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tab-harvest",
        description="Two-tier, read-only browser knowledge extraction. "
                    "Video-first: full YouTube transcripts, X threads, "
                    "interactive knowledge graph.")
    ap.add_argument("--version", action="version", version=f"tab-harvest {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", help="attach over CDP and harvest every open tab")
    h.add_argument("--port", type=int, default=9222, help="CDP port (default 9222)")
    h.add_argument("--out", default=None, help="output dir (default ~/harvests/<timestamp>)")
    h.add_argument("--max-per-tab", type=int, default=4)
    h.add_argument("--max-total", type=int, default=24)
    h.add_argument("--allow-tabs", action="store_true",
                   help="open budgeted throwaway tabs for JS-only content")
    h.add_argument("--tab-budget", type=int, default=6)
    h.add_argument("--timeout-ms", type=int, default=15000)
    h.set_defaults(func=cmd_harvest)

    g = sub.add_parser("graph", help="build or re-render the knowledge graph")
    g.add_argument("input", help="harvest.json (or graph.json with --refresh)")
    g.add_argument("--refresh", action="store_true",
                   help="input is an enriched graph.json; re-render only")
    g.add_argument("--out", default=None, help="output dir (default: beside input)")
    g.add_argument("--html", default=None, help="explicit html output path")
    g.set_defaults(func=cmd_graph)

    d = sub.add_parser("doctor", help="check dependencies + platform bring-up recipes")
    d.add_argument("--port", type=int, default=9222)
    d.set_defaults(func=cmd_doctor)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
