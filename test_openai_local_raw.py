#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check raw response from openai_local API"""

import httpx
import json

url = "http://127.0.0.1:18000/v1/chat/completions"
payload = {
    "model": "claude-sonnet-4-6",
    "messages": [
        {"role": "user", "content": "Calculate: 2+2"}
    ],
    "stream": True,
    "thinking": {"type": "enabled"}
}

print("=" * 70)
print("Direct test of openai_local API")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("=" * 70)
print()

try:
    with httpx.stream("POST", url, json=payload, timeout=120) as resp:
        print(f"Status: {resp.status_code}\n")
        
        for i, line in enumerate(resp.iter_lines()):
            if not line.strip():
                continue
            
            # Show first 10 and last 5 events
            if i < 10 or i >= 200:
                print(f"Line {i}: {line[:200]}")
            elif i == 10:
                print("...")
                
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
