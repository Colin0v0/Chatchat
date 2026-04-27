import { useCallback, useEffect, useRef, useState } from "react";

import type { SpeechPreferences } from "../../settings/model/useSpeechPreferences";
import { canUseSpeechSynthesis, speakSpeechUtterance } from "../../../lib/speechSynthesis";
import { synthesizeSpeech } from "../../../lib/api";

type MessageId = number | string;
type PlaybackProvider = SpeechPreferences["playbackProvider"];

type PlaybackState = {
  audio: HTMLAudioElement | null;
  messageId: MessageId | null;
  token: number;
  utterance: SpeechSynthesisUtterance | null;
};

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

function canUseHtmlAudio() {
  return typeof window !== "undefined" && "Audio" in window;
}

function canUsePlaybackProvider(provider: PlaybackProvider) {
  return provider === "local" ? canUseSpeechSynthesis() : canUseHtmlAudio() || canUseSpeechSynthesis();
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
    audio: null,
    messageId: null,
    token: 0,
    utterance: null,
  });
  const [playingMessageId, setPlayingMessageId] = useState<MessageId | null>(null);
  const [isSupported, setIsSupported] = useState(() => canUsePlaybackProvider(preferences.playbackProvider));

  const stopPlayback = useCallback(() => {
    playbackRef.current.token += 1;
    const audio = playbackRef.current.audio;
    if (audio) {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    }
    if (canUseSpeechSynthesis()) {
      window.speechSynthesis.cancel();
    }
    playbackRef.current.messageId = null;
    playbackRef.current.audio = null;
    playbackRef.current.utterance = null;
    setPlayingMessageId(null);
  }, []);

  const togglePlayback = useCallback(
    async (messageId: MessageId, content: string) => {
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
      playbackRef.current.token = token;
      playbackRef.current.messageId = messageId;
      playbackRef.current.audio = null;
      playbackRef.current.utterance = null;
      setPlayingMessageId(messageId);

      const clearIfCurrent = () => {
        if (playbackRef.current.token !== token) {
          return;
        }
        playbackRef.current.messageId = null;
        playbackRef.current.audio = null;
        playbackRef.current.utterance = null;
        setPlayingMessageId((current) => (current === messageId ? null : current));
      };

      const playBrowserFallback = () => {
        if (!canUseSpeechSynthesis()) {
          clearIfCurrent();
          setIsSupported(canUsePlaybackProvider(preferences.playbackProvider));
          return false;
        }

        const utterance = new SpeechSynthesisUtterance(speechText);
        const language = detectLanguage(speechText);
        const voice = pickVoice(language, preferredVoiceURIForLanguage(language, preferences));

        if (playbackRef.current.token !== token) {
          return true;
        }

        playbackRef.current.utterance = utterance;
        utterance.lang = language;
        utterance.rate = preferences.rate;
        utterance.pitch = 1;
        utterance.volume = 1;
        if (voice) {
          utterance.voice = voice;
        }

        utterance.onend = clearIfCurrent;
        utterance.onerror = clearIfCurrent;

        if (!speakSpeechUtterance(utterance)) {
          clearIfCurrent();
          setIsSupported(canUsePlaybackProvider(preferences.playbackProvider));
          return false;
        }
        return true;
      };

      if (preferences.playbackProvider === "local" || !canUseHtmlAudio()) {
        return playBrowserFallback();
      }

      try {
        const result = await synthesizeSpeech({
          text: speechText,
          voice: preferences.cloudVoice,
          rate: preferences.rate,
        });
        if (playbackRef.current.token !== token) {
          return true;
        }

        const audio = new Audio(result.url);
        playbackRef.current.audio = audio;
        audio.preload = "auto";
        audio.onended = clearIfCurrent;
        audio.onerror = () => {
          if (playbackRef.current.token !== token) {
            return;
          }
          playbackRef.current.audio = null;
          void playBrowserFallback();
        };
        await audio.play();
        return true;
      } catch {
        if (playbackRef.current.token !== token) {
          return true;
        }
        return playBrowserFallback();
      }
    },
    [
      preferences.chineseVoiceURI,
      preferences.cloudVoice,
      preferences.englishVoiceURI,
      preferences.playbackProvider,
      preferences.rate,
      stopPlayback,
    ],
  );

  useEffect(() => {
    setIsSupported(canUsePlaybackProvider(preferences.playbackProvider));
  }, [preferences.playbackProvider]);

  useEffect(() => {
    return () => {
      const audio = playbackRef.current.audio;
      if (audio) {
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
      }
      if (canUseSpeechSynthesis()) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  return {
    isSupported,
    playingMessageId,
    stopPlayback,
    togglePlayback,
  };
}
