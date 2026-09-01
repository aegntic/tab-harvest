#!/usr/bin/env python3
"""Test rig: headless Chromium on :9333 with three content tabs, kept alive."""
import asyncio
import subprocess
import sys
import tempfile

from playwright.async_api import async_playwright

TABS = [
    "https://raw.githubusercontent.com/BuilderIO/agent-native/main/README.md",
    "https://raw.githubusercontent.com/zapier/wade-skills/main/skills/war-council/SKILL.md",
    "https://example.com/",
]


async def main() -> None:
    user_data = tempfile.mkdtemp(prefix="tabharvest-test-")
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data, headless=True, args=["--remote-debugging-port=9333"]
        )
        for i, url in enumerate(TABS):
            page = ctx.pages[0] if i == 0 and ctx.pages else await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(500)
        ver = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:9333/json/version"],
            capture_output=True, text=True,
        ).stdout[:120]
        print("CDP:", ver, flush=True)
        print("test browser up", flush=True)
        await asyncio.sleep(100000)


asyncio.run(main())
