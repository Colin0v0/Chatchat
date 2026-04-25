import { useCallback, useEffect, useMemo, useState } from "react";

export interface SpeechPreferences {
  voiceURI: string | null;
  rate: number;
  autoPlayAssistant: boolean;
}

const STORAGE_KEY = "chatchat.speech-preferences";
const UPDATED_EVENT = "chatchat:speech-preferences-updated";

const DEFAULT_PREFERENCES: SpeechPreferences = {
  voiceURI: null,
  rate: 1,
  autoPlayAssistant: false,
};

function canUseSpeechSynthesis() {
  return (
    typeof window !== "undefined"
    && "speechSynthesis" in window
    && "SpeechSynthesisUtterance" in window
  );
}

function clampRate(value: number) {
  if (!Number.isFinite(value)) {
    return DEFAULT_PREFERENCES.rate;
  }
  return Math.min(1.6, Math.max(0.7, value));
}

function normalizePreferences(value: Partial<SpeechPreferences> | null | undefined): SpeechPreferences {
  return {
    voiceURI: typeof value?.voiceURI === "string" && value.voiceURI.trim() ? value.voiceURI : null,
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
    return normalizePreferences(JSON.parse(raw) as Partial<SpeechPreferences>);
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

  const selectedVoice = useMemo(
    () => voices.find((voice) => voice.voiceURI === preferences.voiceURI) ?? null,
    [preferences.voiceURI, voices],
  );

  return {
    isSupported,
    preferences,
    selectedVoice,
    setAutoPlayAssistant: useCallback(
      (value: boolean) => updatePreferences({ autoPlayAssistant: value }),
      [updatePreferences],
    ),
    setRate: useCallback(
      (value: number) => updatePreferences({ rate: clampRate(value) }),
      [updatePreferences],
    ),
    setVoiceURI: useCallback(
      (value: string | null) => updatePreferences({ voiceURI: value }),
      [updatePreferences],
    ),
    voices,
  };
}
