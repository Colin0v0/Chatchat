#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check thinking events and stream flow"""

import httpx
import json
import time
import sys

# Force UTF-8 output
if sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

url = "http://127.0.0.1:8000/api/chat/stream"
data = {
    "message": "binomial (2x - y)^8 term 3 coefficient",
    "model": "openai_local:claude-sonnet-4-6",
    "retrieval_mode": "none",
    "thinking_enabled": "true",
}

print("=" * 70)
print("Stream Event Diagnostic")
print(f"Message: {data['message']}")
print("=" * 70)
print()

event_stats = {}
thinking_start = None
first_token_time = None
done_time = None
start_time = time.time()

try:
    with httpx.stream("POST", url, data=data, timeout=120) as resp:
        for line in resp.iter_lines():
            if not line.strip():
                continue
            
            elapsed = time.time() - start_time
            
            try:
                event = json.loads(line)
                event_type = event.get("type")
                
                # Track stats
                if event_type not in event_stats:
                    event_stats[event_type] = {"count": 0, "first": elapsed, "last": elapsed}
                event_stats[event_type]["count"] += 1
                event_stats[event_type]["last"] = elapsed
                
                if event_type == "thinking":
                    if thinking_start is None:
                        thinking_start = elapsed
                        print(f"[{elapsed:.2f}s] THINKING_START")
                    content = event.get("content", "")
                    if content:
                        preview = content[:100] if len(content) > 100 else content
                        print(f"[{elapsed:.2f}s]   content: {preview}")
                
                elif event_type == "token":
                    if first_token_time is None:
                        first_token_time = elapsed
                        print(f"[{elapsed:.2f}s] FIRST_TOKEN")
                    
                    token_content = event.get("content", "")
                    if token_content:
                        preview = token_content[:40]
                        print(f"[{elapsed:.2f}s]   {repr(preview)}")
                    
                elif event_type == "reasoning":
                    content = event.get("content", "")
                    if content:
                        preview = content[:80]
                        print(f"[{elapsed:.2f}s] REASONING: {preview}")
                
                elif event_type == "done":
                    done_time = elapsed
                    content = event.get("content", "")
                    finish_reason = event.get("finish_reason")
                    print(f"[{elapsed:.2f}s] DONE (reason={finish_reason}, len={len(content)})")
                    
            except json.JSONDecodeError as e:
                print(f"[{elapsed:.2f}s] JSON_PARSE_ERROR: {line[:80]}")
        
        elapsed_total = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("STATISTICS:")
        for event_type in sorted(event_stats.keys()):
            info = event_stats[event_type]
            print(f"  {event_type:15} count={info['count']:5} timespan=({info['first']:.2f}s~{info['last']:.2f}s)")
        
        print("\nKEY_TIMELINE:")
        print(f"  Total elapsed: {elapsed_total:.2f}s")
        if thinking_start is not None:
            print(f"  Thinking starts at: {thinking_start:.2f}s")
        else:
            print(f"  NO THINKING EVENTS RECEIVED")
        
        if first_token_time is not None:
            print(f"  First token at: {first_token_time:.2f}s")
            if thinking_start is not None:
                print(f"    (thinking->token delay: {first_token_time - thinking_start:.2f}s)")
        
        if done_time is not None:
            print(f"  Done signal at: {done_time:.2f}s")
        
        print("=" * 70)
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
