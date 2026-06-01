import requests
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Get all products and search for RTX 4060
all_products = []
page = 1
while page <= 5:
    url = f"https://gearvn.com/collections/all/products.json?limit=250&page={page}"
    r = requests.get(url, headers=headers, timeout=30)
    products = r.json().get("products", [])
    if not products:
        break
    all_products.extend(products)
    print(f"Page {page}: {len(products)} products")
    page += 1

print(f"\nTotal products fetched: {len(all_products)}")

# Search for keywords
keywords = ["4060", "4070", "1650", "ryzen", "intel", "pc gaming"]
for kw in keywords:
    matches = [p for p in all_products if kw.lower() in p.get("title", "").lower() or kw.lower() in p.get("body_html", "").lower()]
    print(f"\n'{kw}' matches: {len(matches)}")
    for p in matches[:2]:
        v = p["variants"][0]
        price = int(v["price"]) // 1000 if v.get("price") else 0
        print(f"  {p['title'][:60]}")
        print(f"  https://gearvn.com/products/{p['handle']} | {price:,}k VND")

# Sample product structure
if all_products:
    p = all_products[0]
    print("\nSample keys:", list(p.keys()))
    print("Sample:", json.dumps({
        "title": p["title"],
        "handle": p["handle"],
        "product_type": p.get("product_type"),
        "tags": p.get("tags", [])[:5],
        "price": p["variants"][0]["price"],
    }, ensure_ascii=False, indent=2))

# Collections list
r = requests.get("https://gearvn.com/collections.json?limit=50", headers=headers, timeout=15)
if r.status_code == 200:
    cols = r.json().get("collections", [])
    print(f"\nCollections ({len(cols)}):")
    for c in cols[:20]:
        print(f"  {c['handle']} - {c['title']}")
