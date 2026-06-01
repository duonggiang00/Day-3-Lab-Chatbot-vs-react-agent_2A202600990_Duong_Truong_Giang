import requests
import sys
import json

sys.stdout.reconfigure(encoding="utf-8")
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Get all collections
r = requests.get("https://gearvn.com/collections.json?limit=250", headers=headers, timeout=30)
cols = r.json().get("collections", [])
print(f"Total collections: {len(cols)}")

# Find relevant collections
for kw in ["vga", "cpu", "ram", "pc", "main", "nguon", "case", "ssd", "build"]:
    matches = [c for c in cols if kw in c["handle"].lower() or kw in c["title"].lower()]
    print(f"\n--- {kw} ({len(matches)}) ---")
    for c in matches[:8]:
        url = f"https://gearvn.com/collections/{c['handle']}/products.json?limit=3"
        pr = requests.get(url, headers=headers, timeout=15)
        count = len(pr.json().get("products", []))
        print(f"  {c['handle']} | {c['title']} | products in first page: {count}")

# Test PC budget collections
pc_cols = [c for c in cols if "pc-gvn" in c["handle"]]
print(f"\n--- PC GVN collections ({len(pc_cols)}) ---")
for c in pc_cols:
    url = f"https://gearvn.com/collections/{c['handle']}/products.json?limit=5"
    pr = requests.get(url, headers=headers, timeout=15)
    products = pr.json().get("products", [])
    print(f"\n{c['title']} ({c['handle']}): {len(products)} products")
    for p in products[:3]:
        price = int(p["variants"][0]["price"])
        print(f"  {p['title'][:70]} | {price:,} VND")
