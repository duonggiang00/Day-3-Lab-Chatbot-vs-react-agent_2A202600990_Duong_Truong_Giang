import requests
import re
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

url = "https://store.steampowered.com/app/730/CounterStrike_2/"
r = requests.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(r.text, "lxml")

# Game title
title = soup.select_one(".apphub_AppName")
print("Title:", title.get_text(strip=True) if title else "N/A")

# System requirements
sys_req = soup.select_one("#game_area_sys_req")
if sys_req:
    print("\nSys req HTML found")
    # Windows tab
    win = sys_req.select_one(".sysreq_contents")
    if win:
        print(win.get_text("\n", strip=True)[:500])

# Alternative selectors
for sel in ["#game_area_sys_req_full", ".game_area_sys_req", "[data-panel='sysreq']"]:
    el = soup.select_one(sel)
    if el:
        print(f"\nFound {sel}")

# Try regex for minimum requirements
match = re.search(r"Minimum:.*?Storage:.*?GB", r.text, re.DOTALL)
if match:
    print("\nRegex match:", match.group()[:300])
