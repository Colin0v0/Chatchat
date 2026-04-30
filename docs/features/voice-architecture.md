# 语音对话与播放控制架构

更新时间：2026-04-30

本文档描述 Chatchat 的语音输入、语音播放和播放中断链路。当前语音能力是“录音转写 + 文本回答 + 播放”，不是实时双向音频流。

## 1. 目标

- 录音输入不影响文本聊天主链路。
- 语音转写通过独立 API 完成。
- assistant 回复可以使用浏览器本机音色或外部 TTS provider 播放。
- 播放状态由前端维护，支持停止和切换会话清理。
- 后续可以扩展为分句播报和用户插话打断。

## 2. 前端模块

- 录音输入：`frontend/src/features/chats/model/useAudioRecorder.ts`
- 消息播放：`frontend/src/features/chats/model/useMessageSpeechPlayback.ts`
- 语音偏好：`frontend/src/features/settings/model/useSpeechPreferences.ts`
- 云端音色列表：`frontend/src/features/settings/model/cloudVoices.ts`
- 设置页入口：`frontend/src/features/settings/ui/SettingsDialog.tsx`
- 聊天流消费：`frontend/src/features/chats/model/useConversationStreams.ts`
- 消息区播放按钮：`frontend/src/features/chats/ui/MessageList.tsx`

## 3. 后端模块

- 音频路由：`backend/app/api/audio.py`
- 音频服务装配：`backend/app/audio/state.py`
- 转写服务：`backend/app/audio/transcriber.py`
- 合成服务：`backend/app/audio/synthesizer.py`
- 音频配置：`backend/app/core/config.py`
- 输入输出 schema：`backend/app/schemas.py`

后端接口：

- `POST /api/audio/transcribe`
- `POST /api/audio/speech`

## 4. 语音输入链路

```text
browser recorder
  -> POST /api/audio/transcribe
  -> backend validation
  -> transcription provider
  -> text
  -> composer draft
```

配置：

```env
AUDIO_TRANSCRIPTION_ENABLED=false
AUDIO_TRANSCRIPTION_BASE_URL=
AUDIO_TRANSCRIPTION_API_KEY=
AUDIO_TRANSCRIPTION_MODEL=
AUDIO_TRANSCRIPTION_TIMEOUT_SECONDS=60
AUDIO_TRANSCRIPTION_API_MAX_BYTES=10485760
AUDIO_TRANSCRIPTION_LANGUAGE=
AUDIO_TRANSCRIPTION_MIN_DURATION_MS=300
AUDIO_TRANSCRIPTION_MIN_RMS_DBFS=-65
```

## 5. 语音播放链路

### 5.1 浏览器本机音色

```text
assistant text
  -> browser SpeechSynthesis
  -> local system voice
```

特点：

- 不经过后端。
- 不需要 TTS provider。
- 音色由用户设备和浏览器决定。

### 5.2 云端音色

```text
assistant text
  -> POST /api/audio/speech
  -> TTS provider
  -> audio file / URL
  -> frontend playback
```

配置：

```env
AUDIO_TTS_ENABLED=false
AUDIO_TTS_BASE_URL=
AUDIO_TTS_API_KEY=
AUDIO_TTS_MODEL=
AUDIO_TTS_VOICE=
AUDIO_TTS_FORMAT=mp3
AUDIO_TTS_SAMPLE_RATE=24000
AUDIO_TTS_MAX_CHARS=3000
```

## 6. 播放控制

前端负责：

- 当前播放 message id。
- 当前播放 provider。
- 本机朗读停止。
- 云端音频停止。
- 切换会话或重新生成时清理播放状态。

播放控制不写入聊天 NDJSON 流，避免音频状态和模型文本流耦合。

## 7. 当前边界

- 语音输入不是实时流式识别。
- 语音播放不是边生成边播报。
- TTS 音频会先生成再播放。
- 云端 provider 失败时返回明确错误，由前端展示。

## 8. 后续方向

- 按句子分段合成和播放。
- assistant 流式输出期间提前排队 TTS。
- 播放中断后取消剩余合成任务。
- 增加实时语音会话模式。
