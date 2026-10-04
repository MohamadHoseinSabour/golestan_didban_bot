"""
Deep inspection of detail fixture to map all fields (price, area, features, agency, etc.)
"""
import json
import sys
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

FIXTURE = Path("tests/fixtures")

def inspect_detail_file(filename: str):
    path = FIXTURE / filename
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"\n==================== {filename} ====================")

    # 1. Share / Web Info / SEO
    print("SEO title:", data.get("seo", {}).get("title"))
    print("Webengage:", json.dumps(data.get("webengage", {}), ensure_ascii=False, indent=2))

    # 2. Iterate sections
    for s_idx, sec in enumerate(data.get("sections", [])):
        sec_name = sec.get("section_name")
        print(f"\n--- Section {s_idx}: {sec_name} ---")
        for w_idx, w in enumerate(sec.get("widgets", [])):
            wtype = w.get("widget_type")
            wdata = w.get("data", {})

            # Print widget summaries
            if wtype in ("GROUP_INFO_ROW", "UNEXPANDABLE_ROW", "SCORE_ROW", "EVENT_ROW"):
                title = wdata.get("title")
                value = wdata.get("value")
                items = wdata.get("items")
                print(f"  [{wtype}] title='{title}', value='{value}', items={items}")
            elif wtype == "GROUP_FEATURE_ROW":
                items = wdata.get("items", [])
                item_titles = [f"{it.get('title')}: {it.get('available')}" for it in items]
                print(f"  [GROUP_FEATURE_ROW] {', '.join(item_titles)}")
            elif wtype == "CHIPS":
                chips = [c.get("text") for c in wdata.get("chips", [])]
                print(f"  [CHIPS] {chips}")
            elif wtype == "IMAGE_SLIDER":
                images = [img.get("src") for img in wdata.get("items", [])]
                print(f"  [IMAGE_SLIDER] {len(images)} images")
            elif wtype in ("TITLE_ROW", "LEGEND_TITLE_ROW"):
                print(f"  [{wtype}] text='{wdata.get('text') or wdata.get('title')}' subtitle='{wdata.get('subtitle')}'")
            elif wtype == "DESCRIPTION_ROW":
                text = wdata.get("text", "")
                print(f"  [DESCRIPTION_ROW] len={len(text)}, start='{text[:80]}...'")
            else:
                print(f"  [{wtype}] keys={list(wdata.keys())}")

for f in ["detail_gaC7Lwp7.json", "detail_ga-m0OiH.json", "detail_gai5pvUe.json"]:
    inspect_detail_file(f)
