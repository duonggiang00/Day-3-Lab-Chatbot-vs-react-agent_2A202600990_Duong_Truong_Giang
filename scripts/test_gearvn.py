import requests
import re
import json

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Test various endpoints
endpoints = [
    "https://gearvn.com/collections/vga/products.json?limit=10",
    "https://gearvn.com/collections/cpu/products.json?limit=10",
    "https://gearvn.com/collections/pc-gaming/products.json?limit=10",
    "https://gearvn.com/collections/may-tinh-de-ban/products.json?limit=10",
    "https://gearvn.com/collections/all/products.json?limit=10",
]

for url in endpoints:
    r = requests.get(url, headers=headers, timeout=15)
    print(f"\n{url} -> {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        products = data.get("products", [])
        print(f"  Products count: {len(products)}")
        for p in products[:3]:
            print(f"  - {p.get('title')} | {p.get('variants', [{}])[0].get('price')} VND")

# Test search via collections filter
search_url = "https://gearvn.com/search?q=4060&type=product"
r = requests.get(search_url, headers=headers, timeout=15)
print(f"\nSearch page: {r.status_code}, len={len(r.text)}")
if "4060" in r.text:
    print("  Found 4060 in HTML")

# Steam requirements test
steam_url = "https://store.steampowered.com/app/730/"
r = requests.get(steam_url, headers=headers, timeout=15)
print(f"\nSteam CS2: {r.status_code}")
if "sysreq" in r.text.lower() or "System Requirements" in r.text:
    # Find sysreq section
    idx = r.text.find("game_area_sys_req")
    if idx > 0:
        print("  Found game_area_sys_req at", idx)
        print(r.text[idx:idx+500])
