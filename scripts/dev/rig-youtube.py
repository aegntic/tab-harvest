#!/usr/bin/env python3
"""Test rig 2: headless Chromium on :9333 with a real YouTube tab + example.com."""
import asyncio
import subprocess
import tempfile

from playwright.async_api import async_playwright

TABS = [
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # "Me at the zoo" — first YouTube video, has captions
    "https://example.com/",
]


async def main() -> None:
    user_data = tempfile.mkdtemp(prefix="tabharvest-test2-")
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data, headless=True, args=["--remote-debugging-port=9333"]
        )
        for i, url in enumerate(TABS):
            page = ctx.pages[0] if i == 0 and ctx.pages else await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1500)
        ver = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:9333/json/version"],
            capture_output=True, text=True,
        ).stdout[:80]
        print("CDP:", ver, flush=True)
        print("rig2 up", flush=True)
        await asyncio.sleep(100000)


asyncio.run(main())
