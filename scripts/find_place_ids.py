import asyncio
import json
import sys

import httpx

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

async def main():
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://map.divarcdn.com/places-web.json")
        data = r.json()
        print(f"Items in list: {len(data)}")
        # Look for Ahvaz
        ahvaz = [x for x in data if x.get("id") == 7 or x.get("slug") == "ahvaz"]
        if ahvaz:
            print("Ahvaz:", json.dumps(ahvaz[0], ensure_ascii=False, indent=2)[:500])
        # Find Golestan
        golestan = [x for x in data if "golestan" in str(x.get("slug", "")).lower() or x.get("id") == 323]
        print(f"Golestan items found: {len(golestan)}")
        for g in golestan:
            print(f"  id={g.get('id')}, name={g.get('name')}, slug={g.get('slug')}, parent={g.get('parent')}")

if __name__ == "__main__":
    asyncio.run(main())
