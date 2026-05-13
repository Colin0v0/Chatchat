import {
  Brain,
  Check,
  ChevronDown,
  History,
  Image as ImageIcon,
  PawPrint,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  Volume2,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import { changePassword } from "../../auth/api/session";
import type { GeneralPreferences } from "../model/useGeneralPreferences";
import { ModelSelect } from "../../models/ui/ModelSelect";
import type {
  PetPreferences,
  PetProactiveLevel,
  PetReplyLength,
  PetTone,
  PetWalkMode,
} from "../../pet/model/usePetPreferences";
import {
  IMAGE_OUTPUT_FORMAT_OPTIONS,
  IMAGE_QUALITY_OPTIONS,
  IMAGE_SIZE_OPTIONS,
  imageOutputFormatChoiceForValue,
  imageQualityChoiceForValue,
  imageSizeChoiceForValue,
} from "../../chats/lib/imageSizeOptions";
import { CLOUD_VOICE_OPTIONS, type CloudVoiceOption } from "../model/cloudVoices";
import { useSpeechPreferences, type SpeechPlaybackProvider } from "../model/useSpeechPreferences";
import type { MemorySettings, ModelOption } from "../../../types";

type SettingsTab = "general" | "account" | "memory" | "pet" | "voice" | "image";
type ImageSelectKind = "size" | "quality" | "format";
type PetSelectKind = "proactiveLevel" | "replyLength" | "tone" | "walkMode";
type SpeechLanguage = "zh" | "en";
type VoiceSelectKind = "cloud" | SpeechLanguage;
type PasswordMessage = { tone: "error" | "success"; text: string };
type SettingsTabConfig = { icon: LucideIcon; id: SettingsTab; label: string };

const MIN_PASSWORD_LENGTH = 8;
const PASSWORD_INPUT_CLASS =
  "h-9 w-full rounded-[8px] border border-app-border/85 bg-app-panel px-3 text-[14px] text-app-text outline-none transition-colors placeholder:text-app-muted/45 focus:border-app-border-strong focus:bg-app-panel-strong";
const PET_PROACTIVE_OPTIONS: Array<{ label: string; value: PetProactiveLevel }> = [
  { label: "少", value: "low" },
  { label: "正常", value: "normal" },
  { label: "多", value: "high" },
];
const PET_REPLY_LENGTH_OPTIONS: Array<{ label: string; value: PetReplyLength }> = [
  { label: "很短", value: "tiny" },
  { label: "短", value: "short" },
  { label: "正常", value: "normal" },
];
const PET_TONE_OPTIONS: Array<{ label: string; value: PetTone }> = [
  { label: "安静", value: "calm" },
  { label: "黏人", value: "clingy" },
  { label: "吐槽", value: "wry" },
  { label: "元气", value: "bright" },
];
const PET_WALK_MODE_OPTIONS: Array<{ label: string; value: PetWalkMode }> = [
  { label: "普通", value: "normal" },
  { label: "全局走动", value: "global" },
  { label: "不走动", value: "off" },
];

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
    <div className="grid min-h-[61px] items-center gap-2 border-b border-app-border/70 py-4 last:border-b-0 md:min-h-[61px] md:grid-cols-[100px_minmax(0,1fr)] md:gap-5 md:py-3">
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
            ? "bg-app-panel-soft/70 text-app-text"
            : "text-app-muted hover:bg-app-panel-soft/45 hover:text-app-text",
      ].join(" ")}
      onClick={onClick}
      role="option"
      type="button"
    >
      <span className="min-w-0 truncate">{label}</span>
      {selected ? <Check className="size-4 shrink-0" /> : null}
    </button>
  );
}

function SettingSelect({
  label,
  onChange,
  onOpenChange,
  open,
  options,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  options: Array<{ label: string; value: string }>;
  value: string;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const listboxId = useId();
  const selectedOption = options.find((option) => option.value === value) ?? options[0];

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
        aria-label={`${label}：${selectedOption?.label ?? ""}`}
        className={[
          "flex h-9 w-full items-center justify-between gap-3 rounded-[8px] border px-3 text-left text-[14px] transition-colors",
          open
            ? "border-app-border-strong bg-app-panel-soft/70 text-app-text"
            : "border-app-border/85 bg-app-panel text-app-text hover:border-app-border-strong hover:bg-app-panel-soft/55",
        ].join(" ")}
        onClick={() => onOpenChange(!open)}
        type="button"
      >
        <span className="min-w-0 truncate">{selectedOption?.label ?? ""}</span>
        <ChevronDown className={`size-4 shrink-0 text-app-muted transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open ? (
        <div
          className="app-scrollbar absolute left-0 right-0 top-[calc(100%+8px)] z-20 max-h-[216px] overflow-y-auto overscroll-contain rounded-[8px] border border-app-border bg-app-panel-strong p-1.5"
          id={listboxId}
          role="listbox"
        >
          {options.map((option) => (
            <VoiceOption
              key={option.value}
              label={option.label}
              onClick={() => {
                onChange(option.value);
                onOpenChange(false);
              }}
              selected={option.value === selectedOption?.value}
            />
          ))}
        </div>
      ) : null}
    </div>
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
          className="app-scrollbar absolute left-0 right-0 top-[calc(100%+8px)] z-20 max-h-[216px] overflow-y-auto overscroll-contain rounded-[8px] border border-app-border bg-app-panel-strong p-1.5"
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
          className="app-scrollbar absolute left-0 right-0 top-[calc(100%+8px)] z-20 max-h-[216px] overflow-y-auto overscroll-contain rounded-[8px] border border-app-border bg-app-panel-strong p-1.5"
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
    <div className="grid h-9 w-full grid-cols-2 rounded-[8px] border border-app-border/85 bg-app-panel p-1 md:w-[360px]">
      {options.map((option) => {
        const selected = value === option.value;
        return (
          <button
            aria-pressed={selected}
            className={[
              "h-7 rounded-[6px] px-3 text-[14px] font-medium transition-colors",
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

const SETTINGS_TAB_CONFIG: Record<SettingsTab, SettingsTabConfig> = {
  general: { icon: Sparkles, id: "general", label: "通用" },
  account: { icon: UserRound, id: "account", label: "账户" },
  memory: { icon: Brain, id: "memory", label: "记忆" },
  pet: { icon: PawPrint, id: "pet", label: "宠物" },
  voice: { icon: Volume2, id: "voice", label: "语音" },
  image: { icon: ImageIcon, id: "image", label: "图片" },
};

const SETTINGS_TABS = Object.values(SETTINGS_TAB_CONFIG);

function MemorySettingControl({
  checked,
  icon: Icon,
  label,
  onChange,
}: {
  checked: boolean;
  icon: LucideIcon;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex w-full items-center justify-start gap-3 md:w-[360px] md:justify-between">
      <div className="flex min-w-0 items-center gap-2.5">
        <Icon className="size-4 shrink-0 text-app-muted" />
        <div className="min-w-0 text-[14px] font-medium text-app-text">{label}</div>
      </div>
      <ToggleSwitch checked={checked} label={label} onChange={onChange} />
    </div>
  );
}

function GeneralSettingsSection({
  availableModels,
  defaultModel,
  onDefaultModelChange,
  onTemperatureChange,
  temperature,
}: {
  availableModels: ModelOption[];
  defaultModel: string;
  onDefaultModelChange: (value: string) => void;
  onTemperatureChange: (value: number) => void;
  temperature: number;
}) {
  const selectedModel = availableModels.some((item) => item.id === defaultModel)
    ? defaultModel
    : availableModels[0]?.id ?? "";

  return (
    <div>
      <SettingRow label="默认模型">
        <ModelSelect
          fullWidth
          label="默认模型"
          menuPlacement="bottom"
          model={selectedModel}
          models={availableModels}
          onChange={onDefaultModelChange}
        />
      </SettingRow>
      <SettingRow label="温度">
        <div className="flex w-full items-center gap-3 md:w-[360px]">
          <input
            aria-label="默认温度"
            className="settings-range min-w-0 flex-1"
            max={1}
            min={0}
            onChange={(event) => onTemperatureChange(Number(event.target.value))}
            step={0.1}
            type="range"
            value={temperature}
          />
          <span className="w-10 text-right text-[13px] font-medium text-app-muted">
            {temperature.toFixed(1)}
          </span>
        </div>
      </SettingRow>
    </div>
  );
}

function MemorySettingsSection({
  isSaving,
  onChangeSettings,
  onClearChatHistoryIndex,
  onClearSavedMemories,
  settings,
}: {
  isSaving: boolean;
  onChangeSettings: (patch: Partial<MemorySettings>) => void;
  onClearChatHistoryIndex: () => void;
  onClearSavedMemories: () => void;
  settings: MemorySettings;
}) {
  const handleClearSaved = () => {
    if (window.confirm("确定清空已保存记忆？")) {
      onClearSavedMemories();
    }
  };
  const handleClearHistory = () => {
    if (window.confirm("确定清空历史聊天索引？")) {
      onClearChatHistoryIndex();
    }
  };

  return (
    <div>
      <SettingRow label="已保存记忆">
        <MemorySettingControl
          checked={settings.saved_memories_enabled}
          icon={Brain}
          label="回答时注入已保存记忆"
          onChange={(checked) => onChangeSettings({ saved_memories_enabled: checked })}
        />
      </SettingRow>
      <SettingRow label="历史聊天">
        <MemorySettingControl
          checked={settings.reference_chat_history_enabled}
          icon={History}
          label="参考历史聊天索引"
          onChange={(checked) => onChangeSettings({ reference_chat_history_enabled: checked })}
        />
      </SettingRow>
      <SettingRow label="自动学习">
        <MemorySettingControl
          checked={settings.memory_learning_enabled}
          icon={Sparkles}
          label="自动识别新的候选记忆"
          onChange={(checked) => onChangeSettings({ memory_learning_enabled: checked })}
        />
      </SettingRow>
      <SettingRow label="敏感信息">
        <MemorySettingControl
          checked={settings.sensitive_memory_enabled}
          icon={ShieldCheck}
          label="允许学习敏感信息"
          onChange={(checked) => onChangeSettings({ sensitive_memory_enabled: checked })}
        />
      </SettingRow>
      <SettingRow label="清理">
        <div className="grid w-full gap-2 md:w-[360px]">
          <button
            className="inline-flex h-9 items-center justify-center gap-2 rounded-[8px] border border-[#f0d0ca] bg-[#fbefed] px-3 text-[13px] font-medium text-[#9d3d32] transition hover:bg-[#f5dfdb] disabled:cursor-not-allowed disabled:opacity-55"
            disabled={isSaving}
            onClick={handleClearSaved}
            type="button"
          >
            <Trash2 className="size-4" />
            清空已保存记忆
          </button>
          <button
            className="inline-flex h-9 items-center justify-center gap-2 rounded-[8px] border border-app-border bg-app-panel px-3 text-[13px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text disabled:cursor-not-allowed disabled:opacity-55"
            disabled={isSaving}
            onClick={handleClearHistory}
            type="button"
          >
            <Trash2 className="size-4" />
            清空历史索引
          </button>
        </div>
      </SettingRow>
    </div>
  );
}

function MobileSettingsTabSelect({
  activeTab,
  onChange,
  onOpenChange,
  open,
}: {
  activeTab: SettingsTab;
  onChange: (tab: SettingsTab) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const listboxId = useId();
  const activeItem = SETTINGS_TAB_CONFIG[activeTab];
  const ActiveIcon = activeItem.icon;

  // 移动端设置分类会继续增长，用下拉承载，避免顶部标签被挤爆。
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
    <div className="relative md:hidden" ref={rootRef}>
      <button
        aria-controls={listboxId}
        aria-expanded={open}
        className={[
          "flex h-9 w-full items-center justify-between gap-3 rounded-[8px] border px-3 text-left text-[14px] font-medium transition-colors",
          open
            ? "border-app-border-strong bg-app-panel-soft/70 text-app-text"
            : "border-app-border/85 bg-app-panel text-app-text hover:border-app-border-strong hover:bg-app-panel-soft/55",
        ].join(" ")}
        onClick={() => onOpenChange(!open)}
        type="button"
      >
        <span className="flex min-w-0 items-center gap-2">
          <ActiveIcon className="size-4 shrink-0 text-app-muted" />
          <span className="truncate">{activeItem.label}</span>
        </span>
        <ChevronDown className={`size-4 shrink-0 text-app-muted transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open ? (
        <div
          className="absolute left-0 right-0 top-[calc(100%+8px)] z-20 rounded-[8px] border border-app-border bg-app-panel-strong p-1.5 shadow-[0_14px_32px_rgba(34,24,16,0.16)]"
          id={listboxId}
          role="listbox"
        >
          {SETTINGS_TABS.map((item) => {
            const Icon = item.icon;
            const selected = item.id === activeTab;
            return (
              <button
                aria-selected={selected}
                className={[
                  "flex h-9 w-full items-center justify-between gap-3 rounded-[8px] px-2.5 text-left text-[14px] font-medium transition-colors",
                  selected ? "bg-app-panel-soft/75 text-app-text" : "text-app-muted hover:bg-app-panel-soft/45 hover:text-app-text",
                ].join(" ")}
                key={item.id}
                onClick={() => {
                  onChange(item.id);
                  onOpenChange(false);
                }}
                role="option"
                type="button"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <Icon className="size-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </span>
                {selected ? <Check className="size-4 shrink-0" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export function SettingsDialog({
  imageOutputFormat,
  imageQuality,
  imageSize,
  availableModels,
  defaultModel,
  memorySettings,
  memorySettingsSaving,
  onClose,
  onImageOutputFormatChange,
  onImageQualityChange,
  onImageSizeChange,
  onDefaultModelChange,
  onMemoryChangeSettings,
  onMemoryClearChatHistoryIndex,
  onMemoryClearSavedMemories,
  onPetEnabledChange,
  onPetPreferencesChange,
  onTemperatureChange,
  open,
  petEnabled,
  petPreferences,
  temperature,
  username,
}: {
  imageOutputFormat: string;
  imageQuality: string;
  imageSize: string;
  availableModels: ModelOption[];
  defaultModel: GeneralPreferences["defaultModel"];
  memorySettings: MemorySettings;
  memorySettingsSaving: boolean;
  onClose: () => void;
  onImageOutputFormatChange: (value: string) => void;
  onImageQualityChange: (value: string) => void;
  onImageSizeChange: (value: string) => void;
  onDefaultModelChange: (value: string) => void;
  onMemoryChangeSettings: (patch: Partial<MemorySettings>) => void;
  onMemoryClearChatHistoryIndex: () => void;
  onMemoryClearSavedMemories: () => void;
  onPetEnabledChange: (enabled: boolean) => void;
  onPetPreferencesChange: (patch: Partial<PetPreferences>) => void;
  onTemperatureChange: (value: number) => void;
  open: boolean;
  petEnabled: boolean;
  petPreferences: PetPreferences;
  temperature: GeneralPreferences["temperature"];
  username: string;
}) {
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [mobileCategoryOpen, setMobileCategoryOpen] = useState(false);
  const [openImageSelect, setOpenImageSelect] = useState<ImageSelectKind | null>(null);
  const [openPetSelect, setOpenPetSelect] = useState<PetSelectKind | null>(null);
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
  const activeTitle = SETTINGS_TAB_CONFIG[activeTab].label;
  const normalizedImageSize = imageSizeChoiceForValue(imageSize).value;
  const normalizedImageQuality = imageQualityChoiceForValue(imageQuality).value;
  const normalizedImageOutputFormat = imageOutputFormatChoiceForValue(imageOutputFormat).value;

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
    if (!open || activeTab !== "pet") {
      setOpenPetSelect(null);
    }
    if (!open || activeTab !== "voice") {
      setOpenVoiceSelect(null);
    }
    if (!open || activeTab !== "image") {
      setOpenImageSelect(null);
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
    setMobileCategoryOpen(false);
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
        if (openImageSelect) {
          setOpenImageSelect(null);
          return;
        }
        if (mobileCategoryOpen) {
          setMobileCategoryOpen(false);
          return;
        }
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileCategoryOpen, onClose, open, openImageSelect, openVoiceSelect]);

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
            <div className="min-w-0 truncate text-[20px] font-semibold tracking-[-0.03em] text-app-text">
              <span className="md:hidden">设置</span>
              <span className="hidden md:inline">{activeTitle}</span>
            </div>
            <button
              aria-label="关闭设置"
              className="flex h-8 w-8 items-center justify-center rounded-[8px] text-app-muted transition-colors hover:bg-app-panel-soft hover:text-app-text"
              onClick={onClose}
              type="button"
            >
              <X className="size-4" />
            </button>
          </header>

          <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto px-4 pb-5 md:px-5">
            <div className="space-y-4 py-4">
              <MobileSettingsTabSelect
                activeTab={activeTab}
                onChange={setActiveTab}
                onOpenChange={setMobileCategoryOpen}
                open={mobileCategoryOpen}
              />

              <div>
                {activeTab === "general" ? (
                  <GeneralSettingsSection
                    availableModels={availableModels}
                    defaultModel={defaultModel}
                    onDefaultModelChange={onDefaultModelChange}
                    onTemperatureChange={onTemperatureChange}
                    temperature={temperature}
                  />
                ) : null}

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
                              ? "text-app-muted hover:text-app-text"
                              : "text-app-muted hover:text-app-text",
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
                            className="inline-flex h-8 items-center justify-center px-0 text-[14px] font-medium text-app-muted transition-colors hover:text-app-text disabled:cursor-not-allowed disabled:opacity-55 md:h-9"
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

              {activeTab === "pet" ? (
                <div>
                  <SettingRow label="桌面宠物">
                    <div className="flex w-full items-center justify-start gap-3 md:w-[360px] md:justify-between">
                      <div className="min-w-0">
                        <div className="text-[14px] font-medium text-app-text">显示狐狸宠物</div>
                        <div className="mt-1 text-[13px] leading-5 text-app-muted">
                          关闭后宠物会从页面里隐藏，但状态和偏好会保留。
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={petEnabled}
                        label="显示宠物"
                        onChange={onPetEnabledChange}
                      />
                    </div>
                  </SettingRow>
                  <SettingRow label="走动模式">
                    <div className="space-y-2">
                      <SettingSelect
                        label="走动模式"
                        onChange={(walkMode) => onPetPreferencesChange({ walkMode: walkMode as PetWalkMode })}
                        onOpenChange={(nextOpen) => setOpenPetSelect(nextOpen ? "walkMode" : null)}
                        open={openPetSelect === "walkMode"}
                        options={PET_WALK_MODE_OPTIONS}
                        value={petPreferences.walkMode}
                      />
                      <div className="max-w-[360px] text-[13px] leading-5 text-app-muted">
                        普通会贴着当前页面的输入框或底部脚线散步；全局走动会在页面里上下左右乱逛；不走动只保留拖拽和必要回位。
                      </div>
                    </div>
                  </SettingRow>
                  <SettingRow label="主动提示">
                    <SettingSelect
                      label="主动提示频率"
                      onChange={(proactiveLevel) =>
                        onPetPreferencesChange({ proactiveLevel: proactiveLevel as PetProactiveLevel })
                      }
                      onOpenChange={(nextOpen) => setOpenPetSelect(nextOpen ? "proactiveLevel" : null)}
                      open={openPetSelect === "proactiveLevel"}
                      options={PET_PROACTIVE_OPTIONS}
                      value={petPreferences.proactiveLevel}
                    />
                  </SettingRow>
                  <SettingRow label="语气">
                    <SettingSelect
                      label="狐狸语气"
                      onChange={(tone) => onPetPreferencesChange({ tone: tone as PetTone })}
                      onOpenChange={(nextOpen) => setOpenPetSelect(nextOpen ? "tone" : null)}
                      open={openPetSelect === "tone"}
                      options={PET_TONE_OPTIONS}
                      value={petPreferences.tone}
                    />
                  </SettingRow>
                  <SettingRow label="回复长度">
                    <SettingSelect
                      label="狐狸回复长度"
                      onChange={(replyLength) =>
                        onPetPreferencesChange({ replyLength: replyLength as PetReplyLength })
                      }
                      onOpenChange={(nextOpen) => setOpenPetSelect(nextOpen ? "replyLength" : null)}
                      open={openPetSelect === "replyLength"}
                      options={PET_REPLY_LENGTH_OPTIONS}
                      value={petPreferences.replyLength}
                    />
                  </SettingRow>
                  <SettingRow label="当前对话">
                    <div className="flex w-full items-center justify-start gap-3 md:w-[360px] md:justify-between">
                      <div className="min-w-0">
                        <div className="text-[14px] font-medium text-app-text">参考当前对话</div>
                        <div className="mt-1 text-[13px] leading-5 text-app-muted">
                          关闭后聊天不会读取主对话最近内容。
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={petPreferences.referenceConversation}
                        label="参考当前对话"
                        onChange={(referenceConversation) => onPetPreferencesChange({ referenceConversation })}
                      />
                    </div>
                  </SettingRow>
                  <SettingRow label="输入草稿">
                    <div className="flex w-full items-center justify-start gap-3 md:w-[360px] md:justify-between">
                      <div className="min-w-0">
                        <div className="text-[14px] font-medium text-app-text">参考输入框草稿</div>
                        <div className="mt-1 text-[13px] leading-5 text-app-muted">
                          关闭后聊天不会读取你还没发送的内容。
                        </div>
                      </div>
                      <ToggleSwitch
                        checked={petPreferences.referenceDraft}
                        label="参考输入框草稿"
                        onChange={(referenceDraft) => onPetPreferencesChange({ referenceDraft })}
                      />
                    </div>
                  </SettingRow>
                </div>
              ) : null}

              {activeTab === "memory" ? (
                <MemorySettingsSection
                  isSaving={memorySettingsSaving}
                  onChangeSettings={onMemoryChangeSettings}
                  onClearChatHistoryIndex={onMemoryClearChatHistoryIndex}
                  onClearSavedMemories={onMemoryClearSavedMemories}
                  settings={memorySettings}
                />
              ) : null}

              {activeTab === "image" ? (
                <div>
                  <>
                    <SettingRow label="尺寸">
                      <SettingSelect
                        label="图片尺寸"
                        onChange={onImageSizeChange}
                        onOpenChange={(nextOpen) => setOpenImageSelect(nextOpen ? "size" : null)}
                        open={openImageSelect === "size"}
                        options={IMAGE_SIZE_OPTIONS}
                        value={normalizedImageSize}
                      />
                    </SettingRow>
                    <SettingRow label="质量">
                      <SettingSelect
                        label="图片质量"
                        onChange={onImageQualityChange}
                        onOpenChange={(nextOpen) => setOpenImageSelect(nextOpen ? "quality" : null)}
                        open={openImageSelect === "quality"}
                        options={IMAGE_QUALITY_OPTIONS}
                        value={normalizedImageQuality}
                      />
                    </SettingRow>
                    <SettingRow label="格式">
                      <SettingSelect
                        label="图片格式"
                        onChange={onImageOutputFormatChange}
                        onOpenChange={(nextOpen) => setOpenImageSelect(nextOpen ? "format" : null)}
                        open={openImageSelect === "format"}
                        options={IMAGE_OUTPUT_FORMAT_OPTIONS}
                        value={normalizedImageOutputFormat}
                      />
                    </SettingRow>
                  </>
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
        </div>
      </section>
    </div>
  );
}
