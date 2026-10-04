"""Find type URLs and pagination data structure in the Divar bundle."""
import re

text = open("docs/services_bundle.js", encoding="utf-8").read()

# 1. Find @type values
types = re.findall(r'"@type"\s*:\s*"([^"]+)"', text)
if types:
    print("@type values found:")
    for t in sorted(set(types)):
        print(f"  {t}")
else:
    print("No @type values found")

# 2. Find googleapis type strings
googleapis = re.findall(r'"type\.googleapis\.com[^"]{0,100}"', text)
if googleapis:
    print("\ngoogleapis type strings:")
    for g in sorted(set(googleapis)):
        print(f"  {g}")

# 3. Find pagination context
print("\n--- pagination_data context ---")
for m in re.finditer(r'.{0,200}pagination.{0,200}', text):
    s = m.group(0)
    if "@type" in s or "size" in s.lower():
        print(s[:300])
        print("---")
        break

# 4. Look for the search API call in detail
print("\n--- postlist/w/search context ---")
for m in re.finditer(r'.{0,500}postlist/w/search.{0,500}', text):
    print(m.group(0)[:600])
    print("---")
    break

# 5. Find city_ids format (string vs int)
print("\n--- city_ids format ---")
for m in re.finditer(r'.{0,100}city_ids.{0,200}', text):
    s = m.group(0)
    if "search" in s.lower() or "post" in s.lower():
        print(s[:250])
        print("---")
        break
