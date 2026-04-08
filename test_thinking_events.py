#!/usr/bin/env python
"""检查思考事件时间和内容"""

import httpx
import json
import time
from datetime import datetime

url = "http://127.0.0.1:8000/api/chat/stream"
data = {
    "message": "二项式(2x - y)^8的展开式中第 3 项的二项式系数为",
    "model": "openai_local:claude-sonnet-4-6",
    "retrieval_mode": "none",
    "thinking_enabled": "true",
}

print("=" * 70)
print(f"检查思考事件 - {datetime.now().strftime('%H:%M:%S')}")
print(f"message: {data['message']}")
print("=" * 70)
print()

event_types = {}
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
                
                # 统计事件类型
                if event_type not in event_types:
                    event_types[event_type] = {"count": 0, "first": elapsed, "last": elapsed}
                event_types[event_type]["count"] += 1
                event_types[event_type]["last"] = elapsed
                
                if event_type == "thinking":
                    if thinking_start is None:
                        thinking_start = elapsed
                        print(f"[{elapsed:.2f}s] [THINKING START]")
                    thinking_content = event.get("content", "")
                    if len(thinking_content) > 100:
                        print(f"         thinking content: {thinking_content[:100]}...")
                
                elif event_type == "token":
                    if first_token_time is None:
                        first_token_time = elapsed
                        print(f"[{elapsed:.2f}s] [FIRST TOKEN]")
                    
                    token_content = event.get("content", "")
                    if token_content:
                        print(f"[{elapsed:.2f}s] Token: {repr(token_content[:30])}")
                    
                elif event_type == "reasoning":
                    reasoning_content = event.get("content", "")
                    if reasoning_content:
                        print(f"[{elapsed:.2f}s] [REASONING]: {reasoning_content[:60]}...")
                
                elif event_type == "done":
                    done_time = elapsed
                    content = event.get("content", "")
                    finish_reason = event.get("finish_reason")
                    print(f"[{elapsed:.2f}s] [DONE] (reason: {finish_reason}, content: {len(content)} chars)")
                    
                elif event_type in ["meta", "context", "sources"]:
                    pass  # 忽略这些事件的详细输出
                
            except json.JSONDecodeError:
                pass
        
        elapsed_total = time.time() - start_time
        
        print("\n" + "=" * 70)
        print("总体统计:")
        for event_type in sorted(event_types.keys()):
            info = event_types[event_type]
            print(f"  {event_type:12} - {info['count']:4} 个 ({info['first']:.2f}s ~ {info['last']:.2f}s)")
        
        print("\n关键时间点:")
        print(f"  总耗时: {elapsed_total:.2f} seconds")
        if thinking_start is not None:
            print(f"  thinking start: {thinking_start:.2f}s")
            if first_token_time is not None:
                print(f"  first token: {first_token_time:.2f}s (after thinking: {first_token_time - thinking_start:.2f}s)")
            else:
                print(f"  no token events!")
        else:
            print(f"  WARNING: no thinking events! thinking_enabled may not be working")
            if first_token_time is not None:
                print(f"  first token: {first_token_time:.2f}s")
        
        if done_time is not None:
            print(f"  done: {done_time:.2f}s")
        
        print("=" * 70)
        
except Exception as e:
    print(f"异常: {e}")
    import traceback
    traceback.print_exc()
