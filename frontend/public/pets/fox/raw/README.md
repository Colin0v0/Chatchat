# 狐狸透明素材说明

当前 `raw` 目录只保留这一张透明大图：

- `fox_sprites_transparent.png`

这张图已经确认是透明背景，后续切图脚本只读取它，不再回头依赖旧的 `thread-image-*` 素材。

## 已接入的动作分组

- `idle`：待机
- `walk`：走路
- `eat`：吃饭
- `drink`：喝水
- `sleep`：睡觉
- `emotion`：轻表情
- `sad`：委屈/低状态
- `angry`：生气
- `surprised`：惊讶
- `happy`：开心
- `pickup`：被抱起
- `putdown`：放下
- `praise`：夸夸
- `hurt`：受伤
- `click`：互动反应

## 切图原则

1. 只保留单个动作主体，不把别的格子的东西卷进来。
2. 尽量统一大小和落点，底部脚线对齐。
3. AI 动作不连贯的帧可以直接跳过，不要硬塞全帧。
