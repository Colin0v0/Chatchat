const BROWSER_CACHE_SCHEMA_VERSION = 1;
const DEFAULT_BROWSER_CACHE_TTL_MS = 6 * 60 * 60 * 1000;

type BrowserCacheEnvelope<T> = {
  schema_version: number;
  expires_at: number;
  value: T;
};

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

export function readBrowserCache<T>(
  key: string,
  validate: (value: unknown) => value is T,
): T | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return null;
    }

    const envelope = JSON.parse(raw) as Partial<BrowserCacheEnvelope<unknown>>;
    if (
      envelope.schema_version !== BROWSER_CACHE_SCHEMA_VERSION
      || typeof envelope.expires_at !== "number"
      || envelope.expires_at <= Date.now()
      || !validate(envelope.value)
    ) {
      window.localStorage.removeItem(key);
      return null;
    }

    return envelope.value;
  } catch {
    window.localStorage.removeItem(key);
    return null;
  }
}

export function writeBrowserCache<T>(key: string, value: T, ttlMs = DEFAULT_BROWSER_CACHE_TTL_MS) {
  if (typeof window === "undefined") {
    return;
  }

  const envelope: BrowserCacheEnvelope<T> = {
    schema_version: BROWSER_CACHE_SCHEMA_VERSION,
    expires_at: Date.now() + ttlMs,
    value,
  };
  try {
    window.localStorage.setItem(key, JSON.stringify(envelope));
  } catch {
    // 浏览器存储空间不足时清掉当前缓存键，避免下一次读取半截数据。
    window.localStorage.removeItem(key);
  }
}
