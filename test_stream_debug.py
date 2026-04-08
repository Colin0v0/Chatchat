#!/usr/bin/env python
"""直接测试流式请求，诊断截断问题"""

import httpx
import json
import sys
from datetime import datetime

url = "http://127.0.0.1:8000/api/chat/stream"
data = {
    "message": "二项式(2x - y)^8的展开式中第 3 项的二项式系数为",
    "model": "openai_local:claude-sonnet-4-6",
    "retrieval_mode": "none",
    "thinking_enabled": "true",
}

print("=" * 70)
print(f"开始流式请求 - {datetime.now().strftime('%H:%M:%S')}")
print(f"问题: {data['message']}")
print("=" * 70)
print()

token_count = 0
done_received = False
start_time = datetime.now()
event_list = []

try:
    with httpx.stream("POST", url, data=data, timeout=120) as resp:
        print(f"状态码: {resp.status_code}")
        
        for line in resp.iter_lines():
            if not line.strip():
                continue
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            try:
                event = json.loads(line)
                event_type = event.get("type")
                
                if event_type == "token":
                    token_count += 1
                    token_text = event.get("token", "")
                    
                    if token_count <= 5 or token_count % 50 == 0:
                        print(f"[{elapsed:.1f}s] Token {token_count}: {repr(token_text[:60])}")
                    
                    event_list.append({
                        "type": "token",
                        "content": token_text,
                        "elapsed": elapsed,
                    })
                
                elif event_type == "thinking":
                    thinking_text = event.get("thinking", "")
                    print(f"[{elapsed:.1f}s] THINKING: {thinking_text[:80]}...")
                    event_list.append({
                        "type": "thinking",
                        "content": thinking_text,
                        "elapsed": elapsed,
                    })
                
                elif event_type == "done":
                    done_received = True
                    content = event.get("content", "")
                    finish_reason = event.get("finish_reason", "unknown")
                    
                    print(f"\n[{elapsed:.1f}s] === DONE 事件 ===")
                    print(f"Finish Reason: {finish_reason}")
                    print(f"Content 长度: {len(content)} 字符")
                    print(f"内容前200字符:")
                    print(content[:200])
                    print()
                    
                    event_list.append({
                        "type": "done",
                        "content_len": len(content),
                        "finish_reason": finish_reason,
                        "elapsed": elapsed,
                    })
                
                elif event_type == "error":
                    error_msg = event.get("error", "")
                    print(f"[{elapsed:.1f}s] ERROR: {error_msg}")
                    event_list.append({
                        "type": "error",
                        "error": error_msg,
                        "elapsed": elapsed,
                    })
                
                else:
                    print(f"[{elapsed:.1f}s] 未知事件类型: {event_type}")
                    
            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {line[:100]}")
        
        elapsed_total = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "=" * 70)
        print("总结:")
        print(f"  总耗时: {elapsed_total:.2f} 秒")
        print(f"  Token 数: {token_count}")
        print(f"  Done 收到: {done_received}")
        print(f"  事件总数: {len(event_list)}")
        
        # 分析时间序列
        if event_list:
            print("\n事件时间线:")
            for i, evt in enumerate(event_list[:10] + event_list[-3:]):
                if i == 10 and len(event_list) > 13:
                    print("  ...")
                else:
                    evt_type = evt.get("type")
                    elapsed = evt.get("elapsed", 0)
                    if evt_type == "token":
                        print(f"  [{elapsed:.2f}s] Token {i+1}")
                    elif evt_type == "thinking":
                        print(f"  [{elapsed:.2f}s] Thinking")
                    elif evt_type == "done":
                        print(f"  [{elapsed:.2f}s] Done (reason: {evt.get('finish_reason')})")
                    elif evt_type == "error":
                        print(f"  [{elapsed:.2f}s] Error: {evt.get('error')}")
        
        print("=" * 70)
        
except Exception as e:
    print(f"异常: {type(e).__name__}: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
