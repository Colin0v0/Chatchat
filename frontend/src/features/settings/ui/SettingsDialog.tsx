import { Check, ChevronDown, UserRound, Volume2, X, type LucideIcon } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import { changePassword } from "../../auth/api/session";
import { CLOUD_VOICE_OPTIONS, type CloudVoiceOption } from "../model/cloudVoices";
import { useSpeechPreferences, type SpeechPlaybackProvider } from "../model/useSpeechPreferences";

type SettingsTab = "account" | "voice";
type SpeechLanguage = "zh" | "en";
type VoiceSelectKind = "cloud" | SpeechLanguage;
type PasswordMessage = { tone: "error" | "success"; text: string };

const MIN_PASSWORD_LENGTH = 8;
const PASSWORD_INPUT_CLASS =
  "h-9 w-full rounded-[8px] border border-app-border/85 bg-app-panel px-3 text-[14px] text-app-text outline-none transition-colors placeholder:text-app-muted/45 focus:border-app-border-strong focus:bg-app-panel-strong";

function speechLanguageForVoice(voice: SpeechSynthesisVoice | null | undefined): SpeechLanguage | null {
  const lang = voice?.lang.toLowerCase() ?? "";
  if (lang.startsWith("zh")) {
    return "zh";
  }
  if (lang.startsWith("en")) {
    return "en";
  }
  return null;
}

function filterVoicesByLanguage(voices: SpeechSynthesisVoice[], language: SpeechLanguage) {
  return voices.filter((voice) => speechLanguageForVoice(voice) === language);
}

function formatVoiceLabel(voice: SpeechSynthesisVoice | null | undefined) {
  return voice ? `${voice.name} (${voice.lang})` : "跟随系统默认";
}

function formatCloudVoiceLabel(voice: CloudVoiceOption | null | undefined) {
  return voice ? voice.label : CLOUD_VOICE_OPTIONS[0]?.label ?? "";
}

function SettingRow({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="grid min-h-[60px] items-center gap-2 border-b border-app-border/70 py-4 last:border-b-0 md:min-h-[56px] md:grid-cols-[100px_minmax(0,1fr)] md:gap-5 md:py-3">
      <div className="text-[15px] font-semibold tracking-[-0.01em] text-app-text md:text-[14px] md:font-medium">{label}</div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function VoiceOption({
  disabled = false,
  label,
  onClick,
  selected,
}: {
  disabled?: boolean;
  label: string;
  onClick: () => void;
  selected: boolean;
}) {
  return (
    <button
      aria-selected={selected}
      disabled={disabled}
      className={[
        "flex w-full items-center justify-between gap-3 rounded-[8px] px-3 py-2.5 text-left text-[14px] transition-colors",
        disabled
          ? "cursor-not-allowed text-app-muted/45"
          : selected
            ? "bg-app-panel-soft text-app-text"
            : "text-app-muted hover:bg-app-panel-soft hover:text-app-text",
      ].join(" ")}
      onClick={onClick}
      role="option"
      title={label}
      type="button"
    >
      <span className="min-w-0 truncate">{label}</span>
      {selected ? <Check className="size-4 shrink-0" /> : null}
    </button>
  );
}

function VoiceSelect({
  emptyLabel,
  onChange,
  onOpenChange,
  open,
  value,
  voices,
}: {
  emptyLabel: string;
  onChange: (value: string | null) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  value: string | null;
  voices: SpeechSynthesisVoice[];
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const listboxId = useId();
  const selectedVoice = voices.find((voice) => voice.voiceURI === value) ?? null;

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        onOpenChange(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [onOpenChange]);

  return (
    <div className="relative w-full md:w-[360px]" ref={rootRef}>
      <button
        aria-controls={listboxId}
        aria-expanded={open}
        className={[
          "flex h-9 w-full items-center justify-between gap-3 rounded-[8px] border px-3 text-left text-[14px] transition-colors",
          open
            ? "border-app-border-strong bg-app-panel-soft/70 text-app-text"
            : "border-app-border/85 bg-app-panel text-app-text hover:border-app-border-strong hover:bg-app-panel-soft/55",
        ].join(" ")}
        onClick={() => onOpenChange(!open)}
        type="button"
      >
        <span className="min-w-0 truncate">{formatVoiceLabel(selectedVoice)}</span>
        <ChevronDown className={`size-4 shrink-0 text-app-muted transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open ? (
        <div
          className="app-scrollbar absolute left-0 right-0 top-[calc(100%+8px)] z-20 max-h-[216px] overflow-y-auto overscroll-contain rounded-[8px] border border-app-border bg-app-panel-strong p-1.5 shadow-[0_16px_42px_rgba(34,24,16,0.16)]"
          id={listboxId}
          role="listbox"
        >
          <VoiceOption
            label="跟随系统默认"
            onClick={() => {
              onChange(null);
              onOpenChange(false);
            }}
            selected={value === null}
          />
          {voices.length > 0 ? (
            voices.map((voice) => (
              <VoiceOption
                key={voice.voiceURI}
                label={formatVoiceLabel(voice)}
                onClick={() => {
                  onChange(voice.voiceURI);
                  onOpenChange(false);
                }}
                selected={voice.voiceURI === value}
              />
            ))
          ) : (
            <VoiceOption disabled label={emptyLabel} onClick={() => undefined} selected={false} />
          )}
        </div>
      ) : null}
    </div>
  );
}

function CloudVoiceSelect({
  onChange,
  onOpenChange,
  open,
  value,
}: {
  onChange: (value: string) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  value: string;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const listboxId = useId();
  const selectedVoice =
    CLOUD_VOICE_OPTIONS.find((voice) => voice.id === value) ?? CLOUD_VOICE_OPTIONS[0] ?? null;

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        onOpenChange(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [onOpenChange]);

  return (
    <div className="relative w-full md:w-[360px]" ref={rootRef}>
      <button
        aria-controls={listboxId}
        aria-expanded={open}
        className={[
          "flex h-9 w-full items-center justify-between gap-3 rounded-[8px] border px-3 text-left text-[14px] transition-colors",
          open
            ? "border-app-border-strong bg-app-panel-soft/70 text-app-text"
            : "border-app-border/85 bg-app-panel text-app-text hover:border-app-border-strong hover:bg-app-panel-soft/55",
        ].join(" ")}
        onClick={() => onOpenChange(!open)}
        type="button"
      >
        <span className="min-w-0 truncate">{formatCloudVoiceLabel(selectedVoice)}</span>
        <ChevronDown className={`size-4 shrink-0 text-app-muted transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open ? (
        <div
          className="app-scrollbar absolute left-0 right-0 top-[calc(100%+8px)] z-20 max-h-[216px] overflow-y-auto overscroll-contain rounded-[8px] border border-app-border bg-app-panel-strong p-1.5 shadow-[0_16px_42px_rgba(34,24,16,0.16)]"
          id={listboxId}
          role="listbox"
        >
          {CLOUD_VOICE_OPTIONS.map((voice) => (
            <VoiceOption
              key={voice.id}
              label={voice.label}
              onClick={() => {
                onChange(voice.id);
                onOpenChange(false);
              }}
              selected={voice.id === selectedVoice?.id}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PlaybackProviderControl({
  onChange,
  value,
}: {
  onChange: (value: SpeechPlaybackProvider) => void;
  value: SpeechPlaybackProvider;
}) {
  const options: Array<{ label: string; value: SpeechPlaybackProvider }> = [
    { label: "阿里云", value: "cloud" },
    { label: "本机", value: "local" },
  ];

  return (
    <div className="grid w-full grid-cols-2 rounded-[8px] border border-app-border/85 bg-app-panel p-1 md:w-[360px]">
      {options.map((option) => {
        const selected = value === option.value;
        return (
          <button
            aria-pressed={selected}
            className={[
              "h-8 rounded-[6px] px-3 text-[14px] font-medium transition-colors",
              selected
                ? "bg-app-panel-soft text-app-text shadow-[0_1px_0_rgba(25,22,18,0.04)]"
                : "text-app-muted hover:text-app-text",
            ].join(" ")}
            key={option.value}
            onClick={() => onChange(option.value)}
            type="button"
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function ToggleSwitch({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      aria-label={label}
      aria-pressed={checked}
      className={[
        "flex h-6 w-11 items-center rounded-full p-0.5 transition-colors",
        checked ? "bg-app-accent-strong" : "bg-app-border-strong",
      ].join(" ")}
      onClick={() => onChange(!checked)}
      type="button"
    >
      <span
        className={[
          "h-5 w-5 rounded-full bg-app-panel-strong shadow-[0_1px_4px_rgba(34,24,16,0.18)] transition-transform",
          checked ? "translate-x-5" : "translate-x-0",
        ].join(" ")}
      />
    </button>
  );
}

const SETTINGS_TABS: Array<{ icon: LucideIcon; id: SettingsTab; label: string }> = [
  { icon: UserRound, id: "account", label: "账户" },
  { icon: Volume2, id: "voice", label: "语音" },
];

export function SettingsDialog({
  onClose,
  open,
  username,
}: {
  onClose: () => void;
  open: boolean;
  username: string;
}) {
  const [activeTab, setActiveTab] = useState<SettingsTab>("account");
  const [openVoiceSelect, setOpenVoiceSelect] = useState<VoiceSelectKind | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMessage, setPasswordMessage] = useState<PasswordMessage | null>(null);
  const [passwordFormOpen, setPasswordFormOpen] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const passwordFormId = useId();
  const currentPasswordId = useId();
  const newPasswordId = useId();
  const confirmPasswordId = useId();
  const {
    isSupported,
    preferences,
    setAutoPlayAssistant,
    setChineseVoiceURI,
    setCloudVoice,
    setEnglishVoiceURI,
    setPlaybackProvider,
    setRate,
    voices,
  } = useSpeechPreferences();
  const chineseVoices = filterVoicesByLanguage(voices, "zh");
  const englishVoices = filterVoicesByLanguage(voices, "en");
  const activeTitle = SETTINGS_TABS.find((item) => item.id === activeTab)?.label ?? "设置";

  function validatePasswordChange(): string | null {
    if (!currentPassword) {
      return "请输入当前密码";
    }
    if (!newPassword) {
      return "请输入新密码";
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      return `新密码至少 ${MIN_PASSWORD_LENGTH} 位`;
    }
    if (newPassword !== confirmPassword) {
      return "两次输入的新密码不一致";
    }
    if (newPassword === currentPassword) {
      return "新密码不能和当前密码相同";
    }
    return null;
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const validationMessage = validatePasswordChange();
    if (validationMessage) {
      setPasswordMessage({ tone: "error", text: validationMessage });
      return;
    }

    setIsChangingPassword(true);
    setPasswordMessage(null);

    try {
      await changePassword({
        currentPassword,
        newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordFormOpen(false);
      setPasswordMessage({ tone: "success", text: "密码已更新" });
    } catch (error) {
      setPasswordMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "密码更新失败，请稍后重试",
      });
    } finally {
      setIsChangingPassword(false);
    }
  }

  useEffect(() => {
    if (!open || activeTab !== "voice") {
      setOpenVoiceSelect(null);
    }
  }, [activeTab, open]);

  useEffect(() => {
    if (open) {
      return;
    }

    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPasswordMessage(null);
    setPasswordFormOpen(false);
    setIsChangingPassword(false);
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (openVoiceSelect) {
          setOpenVoiceSelect(null);
          return;
        }
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open, openVoiceSelect]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 px-4 py-6 backdrop-blur-[2px]"
      onMouseDown={onClose}
    >
      <section
        aria-modal="true"
        className="flex h-[560px] max-h-[calc(100dvh-48px)] w-[780px] max-w-[calc(100vw-32px)] overflow-hidden rounded-[8px] border border-app-border bg-app-panel-strong shadow-[0_26px_80px_rgba(34,24,16,0.24)]"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <aside className="hidden w-[196px] shrink-0 border-r border-app-border/70 bg-app-panel-soft/45 px-2.5 py-4 md:block">
          <div className="px-3 pb-3 text-[18px] font-semibold tracking-[-0.03em] text-app-text">设置</div>
          <div className="flex flex-col gap-1">
            {SETTINGS_TABS.map((item) => {
              const Icon = item.icon;
              const active = activeTab === item.id;
              return (
                <button
                  className={[
                    "flex h-10 items-center gap-2.5 rounded-[8px] px-3 text-left text-[14px] font-medium transition-colors",
                    active ? "bg-app-panel-strong text-app-text shadow-[0_1px_0_rgba(25,22,18,0.04)]" : "text-app-muted hover:bg-app-panel-strong/80 hover:text-app-text",
                  ].join(" ")}
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  type="button"
                >
                  <Icon className="size-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex shrink-0 items-center justify-between gap-4 border-b border-app-border/70 px-5 py-4">
            <div className="text-[20px] font-semibold tracking-[-0.03em] text-app-text">{activeTitle}</div>
            <button
              aria-label="关闭设置"
              className="flex h-8 w-8 items-center justify-center rounded-[8px] text-app-muted transition-colors hover:bg-app-panel-soft hover:text-app-text"
              onClick={onClose}
              type="button"
            >
              <X className="size-4" />
            </button>
          </header>

          <div className="grid shrink-0 grid-cols-2 gap-2 border-b border-app-border/70 px-4 py-3 md:hidden">
            {SETTINGS_TABS.map((item) => {
              const active = activeTab === item.id;
              return (
                <button
                  className={[
                    "h-10 rounded-[8px] px-3 text-[14px] font-semibold transition-colors",
                    active ? "bg-app-panel-soft text-app-text" : "text-app-muted hover:bg-app-panel-soft hover:text-app-text",
                  ].join(" ")}
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  type="button"
                >
                  {item.label}
                </button>
              );
            })}
          </div>

          <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto px-4 pb-5 md:px-5">
            <div>
              {activeTab === "account" ? (
                <div>
                  <SettingRow label="用户名">
                    <div className="w-full truncate text-left text-[14px] font-medium text-app-muted">
                      {username}
                    </div>
                  </SettingRow>
                  <SettingRow label="密码">
                    <div className="flex w-full flex-col items-start gap-2">
                      <div className="flex w-full items-center justify-start gap-8 md:w-auto md:gap-8">
                        <button
                          aria-expanded={passwordFormOpen}
                          className={[
                            "inline-flex h-8 items-center justify-center px-0 text-[14px] font-medium transition-colors md:h-9",
                            passwordFormOpen
                              ? "text-app-text hover:text-app-accent-strong"
                              : "text-app-text hover:text-app-accent-strong md:text-app-accent-strong",
                          ].join(" ")}
                          onClick={() => {
                            setPasswordFormOpen((current) => !current);
                            setPasswordMessage(null);
                            setCurrentPassword("");
                            setNewPassword("");
                            setConfirmPassword("");
                          }}
                          type="button"
                        >
                          {passwordFormOpen ? "取消修改" : "修改密码"}
                        </button>
                        {passwordFormOpen ? (
                          <button
                            className="inline-flex h-8 items-center justify-center px-0 text-[14px] font-medium text-app-text transition-colors hover:text-app-accent-strong disabled:cursor-not-allowed disabled:opacity-55 md:h-9 md:text-app-accent-strong"
                            disabled={isChangingPassword}
                            form={passwordFormId}
                            type="submit"
                          >
                            {isChangingPassword ? "更新中..." : "更新密码"}
                          </button>
                        ) : null}
                      </div>
                      {!passwordFormOpen && passwordMessage ? (
                        <div
                          aria-live="polite"
                          className={[
                            "w-full rounded-[8px] border px-3 py-2 text-[13px] leading-5 md:w-auto",
                            passwordMessage.tone === "success"
                              ? "border-app-border bg-app-accent-soft/70 text-app-accent-strong"
                              : "border-app-danger/20 bg-app-panel-soft text-app-danger",
                          ].join(" ")}
                        >
                          {passwordMessage.text}
                        </div>
                      ) : null}
                    </div>
                  </SettingRow>
                  {passwordFormOpen ? (
                  <form id={passwordFormId} onSubmit={handlePasswordSubmit}>
                    <SettingRow label="当前密码">
                      <input
                        aria-label="当前密码"
                        autoComplete="current-password"
                        className={PASSWORD_INPUT_CLASS}
                        id={currentPasswordId}
                        maxLength={255}
                        onChange={(event) => {
                          setCurrentPassword(event.target.value);
                          setPasswordMessage(null);
                        }}
                        placeholder="输入当前密码"
                        type="password"
                        value={currentPassword}
                      />
                    </SettingRow>
                    <SettingRow label="新密码">
                      <input
                        aria-label="新密码"
                        autoComplete="new-password"
                        className={PASSWORD_INPUT_CLASS}
                        id={newPasswordId}
                        maxLength={255}
                        onChange={(event) => {
                          setNewPassword(event.target.value);
                          setPasswordMessage(null);
                        }}
                        placeholder={`至少 ${MIN_PASSWORD_LENGTH} 位`}
                        type="password"
                        value={newPassword}
                      />
                    </SettingRow>
                    <SettingRow label="确认新密码">
                      <input
                        aria-label="确认新密码"
                        autoComplete="new-password"
                        className={PASSWORD_INPUT_CLASS}
                        id={confirmPasswordId}
                        maxLength={255}
                        onChange={(event) => {
                          setConfirmPassword(event.target.value);
                          setPasswordMessage(null);
                        }}
                        placeholder="再次输入新密码"
                        type="password"
                        value={confirmPassword}
                      />
                    </SettingRow>
                    {passwordMessage ? (
                      <div className="grid items-start gap-2 py-4 md:grid-cols-[100px_minmax(0,1fr)] md:gap-5">
                        <div className="hidden md:block" />
                        <div
                          aria-live="polite"
                          className={[
                            "w-full max-w-[360px] rounded-[8px] border px-3 py-2 text-[13px] leading-5",
                            passwordMessage.tone === "success"
                              ? "border-app-border bg-app-accent-soft/70 text-app-accent-strong"
                              : "border-app-danger/20 bg-app-panel-soft text-app-danger",
                          ].join(" ")}
                        >
                          {passwordMessage.text}
                        </div>
                      </div>
                    ) : null}
                  </form>
                  ) : null}
                </div>
              ) : null}

              {activeTab === "voice" ? (
                <div>
                  <>
                    <SettingRow label="播放来源">
                      <PlaybackProviderControl
                        onChange={setPlaybackProvider}
                        value={preferences.playbackProvider}
                      />
                    </SettingRow>
                    {preferences.playbackProvider === "cloud" ? (
                    <SettingRow label="阿里云音色">
                      <CloudVoiceSelect
                        onChange={setCloudVoice}
                        onOpenChange={(nextOpen) => setOpenVoiceSelect(nextOpen ? "cloud" : null)}
                        open={openVoiceSelect === "cloud"}
                        value={preferences.cloudVoice}
                      />
                    </SettingRow>
                    ) : null}
                    {preferences.playbackProvider === "local" && isSupported ? (
                      <>
                      <SettingRow label="本机中文音色">
                        <VoiceSelect
                          emptyLabel="未检测到中文音色"
                          onChange={setChineseVoiceURI}
                          onOpenChange={(nextOpen) => setOpenVoiceSelect(nextOpen ? "zh" : null)}
                          open={openVoiceSelect === "zh"}
                          value={preferences.chineseVoiceURI}
                          voices={chineseVoices}
                        />
                      </SettingRow>
                      <SettingRow label="本机英文音色">
                        <VoiceSelect
                          emptyLabel="未检测到英文音色"
                          onChange={setEnglishVoiceURI}
                          onOpenChange={(nextOpen) => setOpenVoiceSelect(nextOpen ? "en" : null)}
                          open={openVoiceSelect === "en"}
                          value={preferences.englishVoiceURI}
                          voices={englishVoices}
                        />
                      </SettingRow>
                      </>
                    ) : null}
                    {preferences.playbackProvider === "local" && !isSupported ? (
                    <div className="mt-4 rounded-[8px] border border-app-border bg-app-panel-soft px-4 py-3 text-[14px] leading-6 text-app-muted">
                      当前浏览器不支持本机语音播放。
                    </div>
                    ) : null}
                    <SettingRow label="语速">
                      <div className="flex w-full items-center gap-3 md:w-[360px]">
                        <input
                          className="settings-range min-w-0 flex-1"
                          max={1.6}
                          min={0.7}
                          onChange={(event) => setRate(Number(event.target.value))}
                          step={0.1}
                          type="range"
                          value={preferences.rate}
                        />
                        <span className="w-12 text-right text-[13px] font-medium text-app-muted">
                          {preferences.rate.toFixed(1)}x
                        </span>
                      </div>
                    </SettingRow>
                    <SettingRow label="新回复自动播报">
                      <div className="flex w-full justify-start md:w-[360px] md:justify-end">
                        <ToggleSwitch
                          checked={preferences.autoPlayAssistant}
                          label="新回复自动播报"
                          onChange={setAutoPlayAssistant}
                        />
                      </div>
                    </SettingRow>
                  </>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
