"""Find the bundle containing postlist/w/search endpoint."""
import asyncio
import re
from pathlib import Path

import httpx

# From the HTML, these are the bootstrap bundles
BUNDLES = [
    "https://s100.divarcdn.com/web-assets/2026/09/store-962.54a1e03e.desktop.js",
    "https://s100.divarcdn.com/web-assets/2026/09/utils-357.8d421f42.desktop.js",
    "https://s100.divarcdn.com/web-assets/2026/09/components-179.61cc355d.desktop.js",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://divar.ir/",
}


async def run():
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
        for url in BUNDLES:
            name = url.split("/")[-1]
            print(f"\nFetching {name}...")
            r = await c.get(url, headers=HEADERS)
            print(f"  Size: {len(r.text)}")
            text = r.text

            if "postlist" in text.lower():
                print("  ** Contains postlist! **")
                Path("docs").mkdir(exist_ok=True)
                (Path("docs") / name).write_text(text, encoding="utf-8")

                # Find the search call
                for m in re.finditer(r".{0,400}postlist.{0,400}", text, re.IGNORECASE):
                    snippet = m.group(0)
                    if "search" in snippet or "city" in snippet:
                        print(f"  Snippet: {snippet[:400]}")
                        break

                # Find @type in this bundle
                types_here = re.findall(r'"@type"\s*:\s*"([^"]+)"', text)
                if types_here:
                    print(f"  @types: {set(types_here)}")

                # Find pagination_data
                pag = re.findall(r'.{0,100}pagination.{0,200}', text)
                for p in pag[:3]:
                    if "@type" in p or "page_size" in p:
                        print(f"  pag: {p[:200]}")


if __name__ == "__main__":
    asyncio.run(run())
