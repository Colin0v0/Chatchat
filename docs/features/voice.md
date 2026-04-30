# 语音能力

更新时间：2026-04-30

## 1. 功能范围

语音能力分为两部分：

- 语音输入：录音转文字。
- 语音播放：把 assistant 文本读出来。

语音输入和云端语音播放通过 provider 配置接入；浏览器本机朗读通过 Web Speech API 完成。

## 2. 语音输入

流程：

```text
浏览器录音
  -> 上传音频 blob
  -> 后端校验大小、时长、音量
  -> transcription provider
  -> 返回文本
  -> 填入输入框
```

关键 API：

```text
POST /api/audio/transcribe
```

关键文件：

- `backend/app/api/audio.py`
- `backend/app/audio/transcriber.py`
- `frontend/src/features/chats/ui/ChatComposer.tsx`

配置：

```env
AUDIO_TRANSCRIPTION_ENABLED=false
AUDIO_TRANSCRIPTION_BASE_URL=
AUDIO_TRANSCRIPTION_API_KEY=
AUDIO_TRANSCRIPTION_MODEL=
AUDIO_TRANSCRIPTION_LANGUAGE=
AUDIO_TRANSCRIPTION_API_MAX_BYTES=10485760
AUDIO_TRANSCRIPTION_MIN_DURATION_MS=300
AUDIO_TRANSCRIPTION_MIN_RMS_DBFS=-65
```

## 3. 浏览器本机音色

浏览器本机音色：

- 使用 Web Speech API。
- 不经过后端。
- 不需要云端 TTS provider。
- 音色数量取决于浏览器和系统。

## 4. 云端音色

云端音色流程：

```text
assistant text
  -> POST /api/audio/speech
  -> TTS provider
  -> 保存音频
  -> 返回 audio URL
  -> 前端播放
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

关键文件：

- `backend/app/audio/synthesizer.py`
- `backend/app/audio/state.py`
- `frontend/src/features/chats/model/useMessageSpeechPlayback.ts`
- `frontend/src/features/settings/`

## 5. 设置页

设置页支持：

- 选择浏览器本机音色。
- 选择云端音色。
- 切换播放 provider。

用户选择保存在前端偏好里。

## 6. 当前边界

- 云端 ASR 和云端 TTS 都需要对应 provider 配置。
- 浏览器本机音色不保证所有平台一致。
- 云端 TTS 文本长度受 `AUDIO_TTS_MAX_CHARS` 限制。
- 当前不是实时双向语音通话，而是录音转写 + 文本回答 + 播放。
