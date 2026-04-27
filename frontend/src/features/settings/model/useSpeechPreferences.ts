import { useCallback, useEffect, useMemo, useState } from "react";

import { canUseSpeechSynthesis, unlockSpeechSynthesis } from "../../../lib/speechSynthesis";
import { DEFAULT_CLOUD_VOICE_ID } from "./cloudVoices";

export interface SpeechPreferences {
  cloudVoice: string;
  chineseVoiceURI: string | null;
  englishVoiceURI: string | null;
  rate: number;
  autoPlayAssistant: boolean;
}

const STORAGE_KEY = "chatchat.speech-preferences";
const UPDATED_EVENT = "chatchat:speech-preferences-updated";

const DEFAULT_PREFERENCES: SpeechPreferences = {
  cloudVoice: DEFAULT_CLOUD_VOICE_ID,
  chineseVoiceURI: null,
  englishVoiceURI: null,
  rate: 1,
  autoPlayAssistant: false,
};

function clampRate(value: number) {
  if (!Number.isFinite(value)) {
    return DEFAULT_PREFERENCES.rate;
  }
  return Math.min(1.6, Math.max(0.7, value));
}

type StoredSpeechPreferences = Partial<SpeechPreferences> & {
  voiceURI?: string | null;
};

function normalizeVoiceURI(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

function normalizePreferences(value: StoredSpeechPreferences | null | undefined): SpeechPreferences {
  return {
    cloudVoice:
      typeof value?.cloudVoice === "string" && value.cloudVoice.trim()
        ? value.cloudVoice
        : DEFAULT_PREFERENCES.cloudVoice,
    chineseVoiceURI: normalizeVoiceURI(value?.chineseVoiceURI),
    englishVoiceURI: normalizeVoiceURI(value?.englishVoiceURI),
    rate: clampRate(typeof value?.rate === "number" ? value.rate : DEFAULT_PREFERENCES.rate),
    autoPlayAssistant:
      typeof value?.autoPlayAssistant === "boolean"
        ? value.autoPlayAssistant
        : DEFAULT_PREFERENCES.autoPlayAssistant,
  };
}

function readStoredPreferences(): SpeechPreferences {
  if (typeof window === "undefined") {
    return DEFAULT_PREFERENCES;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PREFERENCES;
    }
    return normalizePreferences(JSON.parse(raw) as StoredSpeechPreferences);
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function writeStoredPreferences(next: SpeechPreferences) {
  if (typeof window === "undefined") {
    return;
  }

  const normalized = normalizePreferences(next);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Ignore storage failures and keep the in-memory state live.
  }
  window.dispatchEvent(
    new CustomEvent<SpeechPreferences>(UPDATED_EVENT, {
      detail: normalized,
    }),
  );
}

function compareVoices(left: SpeechSynthesisVoice, right: SpeechSynthesisVoice) {
  if (left.default !== right.default) {
    return left.default ? -1 : 1;
  }

  const leftLang = left.lang.toLowerCase();
  const rightLang = right.lang.toLowerCase();
  if (leftLang !== rightLang) {
    return leftLang.localeCompare(rightLang);
  }

  return left.name.localeCompare(right.name);
}

export function useSpeechPreferences() {
  const [preferences, setPreferences] = useState<SpeechPreferences>(() => readStoredPreferences());
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [isSupported, setIsSupported] = useState(() => canUseSpeechSynthesis());

  const refreshVoices = useCallback(() => {
    const supported = canUseSpeechSynthesis();
    setIsSupported(supported);
    if (!supported) {
      setVoices([]);
      return;
    }

    const nextVoices = [...window.speechSynthesis.getVoices()].sort(compareVoices);
    setVoices(nextVoices);
  }, []);

  useEffect(() => {
    refreshVoices();
    if (!canUseSpeechSynthesis()) {
      return;
    }

    const synth = window.speechSynthesis;
    const handleVoicesChanged = () => refreshVoices();
    synth.addEventListener("voiceschanged", handleVoicesChanged);
    return () => synth.removeEventListener("voiceschanged", handleVoicesChanged);
  }, [refreshVoices]);

  useEffect(() => {
    if (!preferences.autoPlayAssistant || !canUseSpeechSynthesis()) {
      return;
    }

    let removeActivationListeners = () => undefined;
    const handleUserActivation = () => {
      unlockSpeechSynthesis();
      removeActivationListeners();
    };
    const activationOptions: AddEventListenerOptions = { capture: true, once: true, passive: true };
    const keyboardOptions: AddEventListenerOptions = { capture: true, once: true };
    const removeOptions: EventListenerOptions = { capture: true };

    removeActivationListeners = () => {
      window.removeEventListener("pointerdown", handleUserActivation, removeOptions);
      window.removeEventListener("touchstart", handleUserActivation, removeOptions);
      window.removeEventListener("mousedown", handleUserActivation, removeOptions);
      window.removeEventListener("keydown", handleUserActivation, removeOptions);
    };

    window.addEventListener("pointerdown", handleUserActivation, activationOptions);
    window.addEventListener("touchstart", handleUserActivation, activationOptions);
    window.addEventListener("mousedown", handleUserActivation, activationOptions);
    window.addEventListener("keydown", handleUserActivation, keyboardOptions);

    return removeActivationListeners;
  }, [preferences.autoPlayAssistant]);

  useEffect(() => {
    function handleStorage(event: StorageEvent) {
      if (event.key !== STORAGE_KEY) {
        return;
      }

      setPreferences(readStoredPreferences());
    }

    function handleUpdated(event: Event) {
      const customEvent = event as CustomEvent<SpeechPreferences>;
      setPreferences(normalizePreferences(customEvent.detail));
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener(UPDATED_EVENT, handleUpdated as EventListener);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(UPDATED_EVENT, handleUpdated as EventListener);
    };
  }, []);

  const updatePreferences = useCallback((patch: Partial<SpeechPreferences>) => {
    setPreferences((current) => {
      const next = normalizePreferences({
        ...current,
        ...patch,
      });
      writeStoredPreferences(next);
      return next;
    });
  }, []);

  const selectedChineseVoice = useMemo(
    () => voices.find((voice) => voice.voiceURI === preferences.chineseVoiceURI) ?? null,
    [preferences.chineseVoiceURI, voices],
  );
  const selectedEnglishVoice = useMemo(
    () => voices.find((voice) => voice.voiceURI === preferences.englishVoiceURI) ?? null,
    [preferences.englishVoiceURI, voices],
  );

  return {
    isSupported,
    preferences,
    selectedChineseVoice,
    selectedEnglishVoice,
    setAutoPlayAssistant: useCallback(
      (value: boolean) => {
        if (value) {
          unlockSpeechSynthesis();
          refreshVoices();
        }
        updatePreferences({ autoPlayAssistant: value });
      },
      [refreshVoices, updatePreferences],
    ),
    setRate: useCallback(
      (value: number) => updatePreferences({ rate: clampRate(value) }),
      [updatePreferences],
    ),
    setChineseVoiceURI: useCallback(
      (value: string | null) => updatePreferences({ chineseVoiceURI: value }),
      [updatePreferences],
    ),
    setEnglishVoiceURI: useCallback(
      (value: string | null) => updatePreferences({ englishVoiceURI: value }),
      [updatePreferences],
    ),
    setCloudVoice: useCallback(
      (value: string) => updatePreferences({ cloudVoice: value }),
      [updatePreferences],
    ),
    voices,
  };
}
