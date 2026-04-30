import { useCallback, useEffect, useState } from "react";

import { transcribeAudio } from "../../../lib/api";
import type { AudioTranscriptionResult } from "../../../types";
import { useAudioRecorder } from "./useAudioRecorder";

interface UseComposerTranscriptionOptions {
  isStreaming: boolean;
  setDraft: (update: (current: string) => string) => void;
  setError: (message: string | null) => void;
}

const MIN_RELIABLE_TRANSCRIPTION_DURATION_MS = 300;
const MEANINGFUL_TRANSCRIPT_PATTERN = /[\u3400-\u9fffA-Za-z0-9]/;

function mergeDraftWithTranscript(current: string, transcript: string): string {
  const normalizedTranscript = transcript.trim();
  if (!normalizedTranscript) {
    return current;
  }

  if (!current.trim()) {
    return normalizedTranscript;
  }

  const suffix = current.endsWith("\n") ? "" : "\n";
  return `${current}${suffix}${normalizedTranscript}`;
}

function shouldIgnoreLowConfidenceTranscript(result: AudioTranscriptionResult): boolean {
  const text = result.text.trim();
  if (!text) {
    return true;
  }

  const compactText = text.replace(/\s+/g, "");
  if (result.duration_ms > 0 && result.duration_ms < MIN_RELIABLE_TRANSCRIPTION_DURATION_MS) {
    return compactText.length <= 1;
  }

  return compactText.length <= 3 && !MEANINGFUL_TRANSCRIPT_PATTERN.test(compactText);
}

function emptyTranscriptionMessage(result: AudioTranscriptionResult): string | null {
  if (result.text.trim()) {
    return null;
  }

  switch (result.reason) {
    case "too_short":
      return "录音时间太短，请说完整一句后再松开。";
    case "too_quiet":
      return "录音音量太低，请靠近麦克风再试。";
    case "empty_audio":
      return "未捕获到有效音频，请检查麦克风权限后重试。";
    case "empty_transcript":
    default:
      return "没有识别到语音内容，请再说一次。";
  }
}

export function useComposerTranscription({
  isStreaming,
  setDraft,
  setError,
}: UseComposerTranscriptionOptions) {
  const [isTranscribing, setIsTranscribing] = useState(false);
  const { cancelRecording, isRecording, recordingError, startRecording, stopRecording } =
    useAudioRecorder();

  useEffect(() => {
    if (!recordingError) {
      return;
    }
    setError(recordingError);
  }, [recordingError, setError]);

  const handleStartRecording = useCallback(async () => {
    if (isStreaming || isTranscribing) {
      return;
    }

    try {
      await startRecording();
    } catch (recordingStartError) {
      const message =
        recordingStartError instanceof Error
          ? recordingStartError.message
          : "Failed to start audio recording.";
      setError(message);
    }
  }, [isStreaming, isTranscribing, setError, startRecording]);

  const handleStopRecording = useCallback(async () => {
    if (!isRecording || isTranscribing) {
      return;
    }

    setIsTranscribing(true);
    try {
      setError(null);
      const capture = await stopRecording();
      if (!capture.audioBlob) {
        setError("未捕获到有效音频，请检查 Edge 麦克风权限后重试。");
        return;
      }

      const result = await transcribeAudio(capture.audioBlob);
      const emptyMessage = emptyTranscriptionMessage(result);
      if (emptyMessage) {
        setError(emptyMessage);
        return;
      }
      if (shouldIgnoreLowConfidenceTranscript(result)) {
        setError("没有识别到可靠语音内容，请再说一次。");
        return;
      }
      setDraft((current) => mergeDraftWithTranscript(current, result.text));
      setError(null);
    } catch (transcriptionError) {
      const message =
        transcriptionError instanceof Error
          ? transcriptionError.message
          : "Failed to transcribe audio.";
      setError(message);
    } finally {
      setIsTranscribing(false);
    }
  }, [isRecording, isTranscribing, setDraft, setError, stopRecording]);

  const handleToggleRecording = useCallback(() => {
    if (isRecording) {
      void handleStopRecording();
      return;
    }
    void handleStartRecording();
  }, [handleStartRecording, handleStopRecording, isRecording]);

  return {
    cancelRecording,
    isRecording,
    isTranscribing,
    onToggleRecording: handleToggleRecording,
  };
}
