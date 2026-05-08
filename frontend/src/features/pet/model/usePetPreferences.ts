import { useCallback, useEffect, useState } from "react";

export type PetProactiveLevel = "low" | "normal" | "high";
export type PetReplyLength = "tiny" | "short" | "normal";
export type PetTone = "calm" | "clingy" | "wry" | "bright";

export interface PetPreferences {
  autoWalk: boolean;
  enabled: boolean;
  proactiveLevel: PetProactiveLevel;
  referenceConversation: boolean;
  referenceDraft: boolean;
  replyLength: PetReplyLength;
  tone: PetTone;
}

const STORAGE_KEY = "chatchat.pet.preferences";
const UPDATED_EVENT = "chatchat:pet-preferences-updated";

const DEFAULT_PREFERENCES: PetPreferences = {
  autoWalk: true,
  // 宠物仍属于可选陪伴功能，新用户默认关闭，避免一进来就被动效打扰。
  enabled: false,
  proactiveLevel: "normal",
  referenceConversation: true,
  referenceDraft: true,
  replyLength: "short",
  tone: "clingy",
};

const PROACTIVE_LEVELS: PetProactiveLevel[] = ["low", "normal", "high"];
const REPLY_LENGTHS: PetReplyLength[] = ["tiny", "short", "normal"];
const TONES: PetTone[] = ["calm", "clingy", "wry", "bright"];

function includesValue<T extends string>(values: T[], value: unknown): value is T {
  return typeof value === "string" && values.includes(value as T);
}

function normalizePreferences(value: Partial<PetPreferences> | null | undefined): PetPreferences {
  return {
    autoWalk: typeof value?.autoWalk === "boolean" ? value.autoWalk : DEFAULT_PREFERENCES.autoWalk,
    enabled: typeof value?.enabled === "boolean" ? value.enabled : DEFAULT_PREFERENCES.enabled,
    proactiveLevel: includesValue(PROACTIVE_LEVELS, value?.proactiveLevel)
      ? value.proactiveLevel
      : DEFAULT_PREFERENCES.proactiveLevel,
    referenceConversation: typeof value?.referenceConversation === "boolean"
      ? value.referenceConversation
      : DEFAULT_PREFERENCES.referenceConversation,
    referenceDraft: typeof value?.referenceDraft === "boolean"
      ? value.referenceDraft
      : DEFAULT_PREFERENCES.referenceDraft,
    replyLength: includesValue(REPLY_LENGTHS, value?.replyLength) ? value.replyLength : DEFAULT_PREFERENCES.replyLength,
    tone: includesValue(TONES, value?.tone) ? value.tone : DEFAULT_PREFERENCES.tone,
  };
}

function readStoredPreferences(): PetPreferences {
  if (typeof window === "undefined") {
    return DEFAULT_PREFERENCES;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return DEFAULT_PREFERENCES;
  }

  return normalizePreferences(JSON.parse(raw) as Partial<PetPreferences>);
}

function writeStoredPreferences(next: PetPreferences) {
  if (typeof window === "undefined") {
    return;
  }

  const normalized = normalizePreferences(next);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  // 同页面里设置弹窗和宠物层不是父子控制关系，用自定义事件让它们立刻同步。
  window.dispatchEvent(
    new CustomEvent<PetPreferences>(UPDATED_EVENT, {
      detail: normalized,
    }),
  );
}

export function usePetPreferences() {
  const [preferences, setPreferences] = useState<PetPreferences>(() => readStoredPreferences());

  useEffect(() => {
    function handleStorage(event: StorageEvent) {
      if (event.key !== STORAGE_KEY) {
        return;
      }

      setPreferences(readStoredPreferences());
    }

    function handleUpdated(event: Event) {
      const customEvent = event as CustomEvent<PetPreferences>;
      setPreferences(normalizePreferences(customEvent.detail));
    }

    window.addEventListener("storage", handleStorage);
    window.addEventListener(UPDATED_EVENT, handleUpdated as EventListener);
    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener(UPDATED_EVENT, handleUpdated as EventListener);
    };
  }, []);

  const updatePreferences = useCallback((patch: Partial<PetPreferences>) => {
    setPreferences((current) => {
      const next = normalizePreferences({
        ...current,
        ...patch,
      });
      writeStoredPreferences(next);
      return next;
    });
  }, []);

  const setEnabled = useCallback((enabled: boolean) => {
    updatePreferences({ enabled });
  }, [updatePreferences]);

  return {
    preferences,
    setEnabled,
    updatePreferences,
  };
}
