"""Probe MiMo endpoints for tp-* API key."""
import os
import sys

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

key = os.getenv("MIMO_API_KEY", "").strip()
bases = [
    "https://token-plan-cn.xiaomimimo.com/v1",
    "https://token-plan-sgp.xiaomimimo.com/v1",
    "https://api.xiaomimimo.com/v1",
]
payload = {
    "model": "mimo-v2.5-pro",
    "messages": [{"role": "user", "content": "Xin chao"}],
    "max_completion_tokens": 32,
    "thinking": {"type": "disabled"},
}

print("Key prefix:", key[:6] + "...")
for base in bases:
    for auth_name, headers in [
        ("api-key", {"api-key": key, "Content-Type": "application/json"}),
        ("bearer", {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}),
    ]:
        try:
            r = requests.post(
                f"{base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=45,
            )
            print(f"{auth_name:8} {base:45} -> {r.status_code} {r.text[:120]}")
        except Exception as exc:
            print(f"{auth_name:8} {base:45} -> ERR {exc}")
