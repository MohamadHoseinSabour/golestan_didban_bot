"""
Test resolving neighborhood slug to district ID using Divar places data.
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

async def test_places():
    async with httpx.AsyncClient(timeout=20) as client:
        # Check places endpoint
        r = await client.get("https://map.divarcdn.com/places-web.json")
        print(f"places-web status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            # Find Ahvaz (id 7)
            # data is typically a dict or list
            print("Type of data:", type(data))
            if isinstance(data, dict):
                print("Keys:", list(data.keys())[:10])
                # Save small slice
                Path("docs").mkdir(exist_ok=True)
                # Search for golestan or 323
                text = json.dumps(data, ensure_ascii=False)
                import re
                matches = re.findall(r'\{[^{}]*golestan[^{}]*\}', text)
                print(f"Golestan matches: {len(matches)}")
                for m in matches[:3]:
                    print("  ", m)

if __name__ == "__main__":
    asyncio.run(test_places())
