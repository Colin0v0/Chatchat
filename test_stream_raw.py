#!/usr/bin/env python
"""检查每个token的具体内容"""

import httpx
import json

url = "http://127.0.0.1:8000/api/chat/stream"
data = {
    "message": "二项式(2x - y)^8的展开式中第 3 项的二项式系数为",
    "model": "openai_local:claude-sonnet-4-6",
    "retrieval_mode": "none",
    "thinking_enabled": "true",
}

print("=" * 70)
print("捕获原始JSON行...")
print("=" * 70)
print()

token_count = 0
raw_lines = []

try:
    with httpx.stream("POST", url, data=data, timeout=120) as resp:
        for line in resp.iter_lines():
            if not line.strip():
                continue
            
            raw_lines.append(line)
            
            try:
                event = json.loads(line)
                event_type = event.get("type")
                
                if event_type == "token":
                    token_count += 1
                    # 打印原始JSON行
                    if token_count <= 8:
                        print(f"Token {token_count} 原始行:")
                        print(f"  {line[:180]}")
                        print(f"  token 字段: {repr(event.get('token'))}")
                        print()
                
                elif event_type == "done":
                    print(f"\nDONE 事件：")
                    print(f"  原始行: {line[:200]}")
                    # 尝试获取不同可能的字段名
                    print(f"  content 字段: {repr(event.get('content', 'N/A')[:100])}")
                    print(f"  text 字段: {repr(event.get('text', 'N/A')[:100])}")
                    print(f"  answer 字段: {repr(event.get('answer', 'N/A')[:100])}")
                    
                    # 打印所有字段
                    print(f"  所有字段: {list(event.keys())}")
                    
            except json.JSONDecodeError:
                print(f"解析失败: {line[:100]}")
        
        print(f"\n总共收到 {len(raw_lines)} 行")
        
except Exception as e:
    print(f"异常: {e}")
    import traceback
    traceback.print_exc()
