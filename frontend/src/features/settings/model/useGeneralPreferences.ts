import { useCallback, useEffect, useState } from "react";

export interface GeneralPreferences {
  defaultModel: string;
  temperature: number;
}

const STORAGE_KEY = "chatchat.general-preferences";
const UPDATED_EVENT = "chatchat:general-preferences-updated";

const DEFAULT_PREFERENCES: GeneralPreferences = {
  defaultModel: "",
  temperature: 0.7,
};

function normalizeTemperature(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return DEFAULT_PREFERENCES.temperature;
  }
  return Math.min(1, Math.max(0, Math.round(value * 10) / 10));
}

function normalizePreferences(value: Partial<GeneralPreferences> | null | undefined): GeneralPreferences {
  const defaultModel =
    typeof value?.defaultModel === "string" && value.defaultModel.trim()
      ? value.defaultModel.trim()
      : DEFAULT_PREFERENCES.defaultModel;

  return {
    defaultModel,
    temperature: normalizeTemperature(value?.temperature),
  };
}

function readStoredPreferences(): GeneralPreferences {
  if (typeof window === "undefined") {
    return DEFAULT_PREFERENCES;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PREFERENCES;
    }
    return normalizePreferences(JSON.parse(raw) as Partial<GeneralPreferences>);
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function writeStoredPreferences(next: GeneralPreferences) {
  if (typeof window === "undefined") {
    return;
  }

  const normalized = normalizePreferences(next);
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // 本地偏好写入失败时，当前页面内存状态仍会继续生效。
  }
  window.dispatchEvent(
    new CustomEvent<GeneralPreferences>(UPDATED_EVENT, {
      detail: normalized,
    }),
  );
}

export function useGeneralPreferences() {
  const [preferences, setPreferences] = useState<GeneralPreferences>(() => readStoredPreferences());

  useEffect(() => {
    function handleStorage(event: StorageEvent) {
      if (event.key !== STORAGE_KEY) {
        return;
      }
      setPreferences(readStoredPreferences());
    }

    function handleUpdated(event: Event) {
      const customEvent = event as CustomEvent<GeneralPreferences>;
      setPreferences(normalizePreferences(customEvent.detail));
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener(UPDATED_EVENT, handleUpdated as EventListener);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(UPDATED_EVENT, handleUpdated as EventListener);
    };
  }, []);

  const updatePreferences = useCallback((patch: Partial<GeneralPreferences>) => {
    setPreferences((current) => {
      const next = normalizePreferences({
        ...current,
        ...patch,
      });
      writeStoredPreferences(next);
      return next;
    });
  }, []);

  return {
    preferences,
    updatePreferences,
  };
}
