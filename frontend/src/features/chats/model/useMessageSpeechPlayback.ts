import { useCallback, useEffect, useRef, useState } from "react";

import type { SpeechPreferences } from "../../settings/model/useSpeechPreferences";

type MessageId = number | string;

type PlaybackState = {
  messageId: MessageId | null;
  token: number;
  utterance: SpeechSynthesisUtterance | null;
};

function canUseSpeechSynthesis() {
  return (
    typeof window !== "undefined"
    && "speechSynthesis" in window
    && "SpeechSynthesisUtterance" in window
  );
}

const EMOJI_PATTERN =
  /(?:\p{Extended_Pictographic}|\p{Emoji_Presentation})(?:[\uFE0E\uFE0F]|\u{1F3FB}|\u{1F3FC}|\u{1F3FD}|\u{1F3FE}|\u{1F3FF})?(?:\u200D(?:\p{Extended_Pictographic}|\p{Emoji_Presentation})(?:[\uFE0E\uFE0F]|\u{1F3FB}|\u{1F3FC}|\u{1F3FD}|\u{1F3FE}|\u{1F3FF})?)*|\p{Regional_Indicator}{2}|[#*0-9]\uFE0F?\u20E3/gu;
const EMOJI_JOINER_PATTERN = /[\u200D\uFE0E\uFE0F]/g;

function stripMarkdownForSpeech(content: string) {
  return content
    .replace(/```[\s\S]*?```/g, " 代码片段。 ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\(([^)]*)\)/g, "$1")
    .replace(/^>\s?/gm, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/\|/g, " ")
    .replace(EMOJI_PATTERN, " ")
    .replace(EMOJI_JOINER_PATTERN, "")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function detectLanguage(text: string) {
  return /[\u3400-\u9fff]/.test(text) ? "zh-CN" : "en-US";
}

function preferredVoiceURIForLanguage(lang: string, preferences: SpeechPreferences) {
  return lang.toLowerCase().startsWith("zh")
    ? preferences.chineseVoiceURI
    : preferences.englishVoiceURI;
}

function pickVoice(lang: string, preferredVoiceURI: string | null) {
  if (!canUseSpeechSynthesis()) {
    return null;
  }

  const voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) {
    return null;
  }

  if (preferredVoiceURI) {
    const preferred = voices.find((voice) => voice.voiceURI === preferredVoiceURI);
    if (preferred) {
      return preferred;
    }
  }

  const normalizedLang = lang.toLowerCase();
  return (
    voices.find((voice) => voice.lang.toLowerCase() === normalizedLang)
    ?? voices.find((voice) => voice.lang.toLowerCase().startsWith(normalizedLang.split("-")[0] ?? normalizedLang))
    ?? voices[0]
  );
}

export function useMessageSpeechPlayback(preferences: SpeechPreferences) {
  const playbackRef = useRef<PlaybackState>({
    messageId: null,
    token: 0,
    utterance: null,
  });
  const [playingMessageId, setPlayingMessageId] = useState<MessageId | null>(null);
  const [isSupported, setIsSupported] = useState(() => canUseSpeechSynthesis());

  const stopPlayback = useCallback(() => {
    if (!canUseSpeechSynthesis()) {
      setPlayingMessageId(null);
      return;
    }

    playbackRef.current.token += 1;
    playbackRef.current.messageId = null;
    playbackRef.current.utterance = null;
    window.speechSynthesis.cancel();
    setPlayingMessageId(null);
  }, []);

  const togglePlayback = useCallback(
    (messageId: MessageId, content: string) => {
      if (!canUseSpeechSynthesis()) {
        setIsSupported(false);
        return false;
      }

      const speechText = stripMarkdownForSpeech(content);
      if (!speechText) {
        return false;
      }

      const currentlyPlayingMessageId = playbackRef.current.messageId;
      const shouldStopCurrentMessage = currentlyPlayingMessageId === messageId;
      stopPlayback();
      if (shouldStopCurrentMessage) {
        return true;
      }

      const token = playbackRef.current.token + 1;
      const utterance = new SpeechSynthesisUtterance(speechText);
      const language = detectLanguage(speechText);
      const voice = pickVoice(language, preferredVoiceURIForLanguage(language, preferences));

      playbackRef.current.token = token;
      playbackRef.current.messageId = messageId;
      playbackRef.current.utterance = utterance;

      utterance.lang = language;
      utterance.rate = preferences.rate;
      utterance.pitch = 1;
      utterance.volume = 1;
      if (voice) {
        utterance.voice = voice;
      }

      utterance.onend = () => {
        if (playbackRef.current.token !== token) {
          return;
        }
        playbackRef.current.messageId = null;
        playbackRef.current.utterance = null;
        setPlayingMessageId((current) => (current === messageId ? null : current));
      };

      utterance.onerror = () => {
        if (playbackRef.current.token !== token) {
          return;
        }
        playbackRef.current.messageId = null;
        playbackRef.current.utterance = null;
        setPlayingMessageId((current) => (current === messageId ? null : current));
      };

      setPlayingMessageId(messageId);
      window.speechSynthesis.speak(utterance);
      return true;
    },
    [preferences.chineseVoiceURI, preferences.englishVoiceURI, preferences.rate, stopPlayback],
  );

  useEffect(() => {
    setIsSupported(canUseSpeechSynthesis());
  }, []);

  useEffect(() => {
    return () => {
      if (!canUseSpeechSynthesis()) {
        return;
      }
      window.speechSynthesis.cancel();
    };
  }, []);

  return {
    isSupported,
    playingMessageId,
    stopPlayback,
    togglePlayback,
  };
}
