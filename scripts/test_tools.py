"""Quick test for GearVN tools."""
import sys
import json

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from src.tools.gearvn_tools import (
    crawl_steam_requirements,
    lookup_game_requirements,
    search_gearvn_products,
    get_gearvn_pc_by_budget,
)

print("=== Steam CS2 ===")
print(crawl_steam_requirements("https://store.steampowered.com/app/730/")[:400])

print("\n=== PC 30 triệu ===")
data = json.loads(get_gearvn_pc_by_budget(30_000_000))
print(f"Collection: {data.get('collection')}, count: {data.get('count')}")
for pc in data.get("pcs", [])[:2]:
    print(f"  {pc['name'][:60]} | {pc['price']} | {pc['link']}")

print("\n=== Search Ryzen ===")
data = json.loads(search_gearvn_products("Ryzen 5", limit=3))
print(f"Found: {data.get('count')}")
for p in data.get("products", [])[:2]:
    print(f"  {p['name'][:50]} | {p['price']}")

print("\nAll tests passed!")
