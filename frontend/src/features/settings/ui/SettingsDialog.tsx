import { Settings2, Volume2, X } from "lucide-react";
import { useEffect } from "react";

import { useSpeechPreferences } from "../model/useSpeechPreferences";

interface SettingsDialogProps {
  onClose: () => void;
  open: boolean;
  username: string;
}

export function SettingsDialog({
  onClose,
  open,
  username,
}: SettingsDialogProps) {
  const {
    isSupported,
    preferences,
    selectedVoice,
    setAutoPlayAssistant,
    setRate,
    setVoiceURI,
    voices,
  } = useSpeechPreferences();

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  if (!open) {
    return null;
  }

  const voiceSelectValue =
    preferences.voiceURI && voices.some((voice) => voice.voiceURI === preferences.voiceURI)
      ? preferences.voiceURI
      : "";

  return (
    <div className="pointer-events-none fixed inset-0 z-40 flex items-stretch justify-end p-3 md:p-4">
      <div
        className="pointer-events-auto flex h-full w-full max-w-[720px] flex-col overflow-hidden rounded-[28px] border border-app-border bg-app-panel px-6 py-6 shadow-[0_24px_80px_rgba(34,24,16,0.18)] md:px-7"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-app-panel-soft text-app-accent-strong">
              <Settings2 className="size-5" />
            </div>
            <div className="mt-4 text-[30px] font-semibold tracking-[-0.04em] text-app-text">
              Settings
            </div>
            <div className="mt-2 text-[14px] leading-7 text-app-muted">
              调整语音播报偏好。账号设置后面可以继续接进来。
            </div>
          </div>

          <button
            aria-label="Close settings"
            className="flex h-10 w-10 items-center justify-center rounded-2xl text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={onClose}
            type="button"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="app-scrollbar mt-6 min-h-0 flex-1 overflow-y-auto pr-1">
          <div className="grid gap-4 md:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.9fr)]">
          <section className="rounded-[24px] border border-app-border bg-app-panel-strong p-5">
            <div className="flex items-center gap-3">
              <div className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-white/70 text-app-accent-strong">
                <Volume2 className="size-5" />
              </div>
              <div>
                <div className="text-[18px] font-semibold tracking-[-0.03em] text-app-text">Voice</div>
                <div className="text-[13px] leading-6 text-app-muted">
                  控制当前浏览器朗读使用的音色和节奏。
                </div>
              </div>
            </div>

            {isSupported ? (
              <div className="mt-5 flex flex-col gap-5">
                <label className="flex flex-col gap-2">
                  <span className="text-[13px] font-medium uppercase tracking-[0.14em] text-app-muted">
                    Voice
                  </span>
                  <select
                    className="rounded-2xl border border-app-border bg-white/70 px-4 py-3 text-[15px] text-app-text outline-none transition focus:border-app-border-strong"
                    onChange={(event) => setVoiceURI(event.target.value || null)}
                    value={voiceSelectValue}
                  >
                    <option value="">跟随系统默认</option>
                    {voices.map((voice) => (
                      <option key={voice.voiceURI} value={voice.voiceURI}>
                        {voice.name} ({voice.lang})
                        {voice.default ? " · default" : ""}
                      </option>
                    ))}
                  </select>
                  <span className="text-[13px] leading-6 text-app-muted">
                    当前：
                    {" "}
                    {selectedVoice ? `${selectedVoice.name} (${selectedVoice.lang})` : "系统自动选择"}
                  </span>
                </label>

                <label className="flex flex-col gap-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[13px] font-medium uppercase tracking-[0.14em] text-app-muted">
                      Rate
                    </span>
                    <span className="rounded-full bg-app-panel-soft px-2.5 py-1 text-[12px] font-medium text-app-accent-strong">
                      {preferences.rate.toFixed(1)}x
                    </span>
                  </div>
                  <input
                    className="accent-app-accent-strong"
                    max={1.6}
                    min={0.7}
                    onChange={(event) => setRate(Number(event.target.value))}
                    step={0.1}
                    type="range"
                    value={preferences.rate}
                  />
                  <div className="flex items-center justify-between text-[12px] text-app-muted">
                    <span>更稳</span>
                    <span>更快</span>
                  </div>
                </label>

                <label className="flex items-start gap-3 rounded-2xl border border-app-border/80 bg-white/60 px-4 py-3">
                  <input
                    checked={preferences.autoPlayAssistant}
                    className="mt-1 h-4 w-4 accent-app-accent-strong"
                    onChange={(event) => setAutoPlayAssistant(event.target.checked)}
                    type="checkbox"
                  />
                  <span className="min-w-0">
                    <span className="block text-[15px] font-medium text-app-text">新回复自动播报</span>
                    <span className="mt-1 block text-[13px] leading-6 text-app-muted">
                      当一条 assistant 回复流式完成后，自动朗读最新内容。
                    </span>
                  </span>
                </label>
              </div>
            ) : (
              <div className="mt-5 rounded-2xl border border-app-border/80 bg-white/60 px-4 py-4 text-[14px] leading-7 text-app-muted">
                当前浏览器不支持 `SpeechSynthesis`，所以这台设备上还不能直接用浏览器朗读。
              </div>
            )}
          </section>

          <section className="rounded-[24px] border border-app-border bg-app-panel-strong p-5">
            <div className="text-[18px] font-semibold tracking-[-0.03em] text-app-text">Account</div>
            <div className="mt-2 text-[13px] leading-6 text-app-muted">
              这里先放账号信息，改密码接口下一步再补。
            </div>

            <div className="mt-5 rounded-2xl border border-app-border/80 bg-white/60 px-4 py-4">
              <div className="text-[13px] font-medium uppercase tracking-[0.14em] text-app-muted">Username</div>
              <div className="mt-2 text-[16px] font-medium text-app-text">{username}</div>
            </div>

            <div className="mt-4 rounded-2xl border border-dashed border-app-border px-4 py-4">
              <div className="text-[15px] font-medium text-app-text">Change password</div>
              <div className="mt-2 text-[13px] leading-6 text-app-muted">
                当前前后端还没有接上改密码表单，这里先把入口位置预留好，后面可以直接补 API。
              </div>
              <button
                className="mt-4 inline-flex h-10 items-center rounded-xl border border-app-border bg-app-panel-soft px-4 text-[14px] text-app-muted/75"
                disabled
                type="button"
              >
                即将支持
              </button>
            </div>
          </section>
          </div>
        </div>
      </div>
    </div>
  );
}
