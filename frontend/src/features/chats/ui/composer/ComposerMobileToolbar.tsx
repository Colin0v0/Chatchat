import { BookOpen, Check, Globe, Image, Paperclip, Plus, Scale, Swords } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ReasoningProfileSelect } from "../../../models/ui/ReasoningProfileSelect";
import type { ComposerMode, ModelOption, ReasoningProfileValue, ToolMode } from "../../../../types";

interface ComposerMobileToolbarProps {
  attachmentUploadAvailable: boolean;
  attachmentsPresent: boolean;
  isStreaming: boolean;
  composerMode: ComposerMode;
  onComposerModeChange: (value: ComposerMode) => void;
  onAddAttachment: () => void;
  onNewDebate: () => void;
  onNewBattle: () => void;
  onReasoningProfileChange: (value: ReasoningProfileValue) => void;
  reasoningProfile: ReasoningProfileValue;
  selectedModelOption: ModelOption | null;
  showImageModeOption: boolean;
  showNewDebateOption: boolean;
  showNewBattleOption: boolean;
  showReasoningProfile: boolean;
  toolMode: ToolMode;
  onToggleRag: () => void;
  onToggleWeb: () => void;
}

interface MobileMenuActionProps {
  active?: boolean;
  disabled?: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}

function MobileMenuAction({
  active = false,
  disabled = false,
  icon,
  label,
  onClick,
}: MobileMenuActionProps) {
  const disabledClassName = active
    ? "cursor-default bg-app-panel-strong text-[#5f564a] opacity-85"
    : "cursor-not-allowed bg-app-panel-strong text-app-muted/45";

  return (
    <button
      aria-pressed={active}
      className={`flex h-10 w-full items-center justify-between gap-3 px-3 text-left text-[14px] font-medium tracking-[-0.02em] transition-colors ${
        disabled
          ? disabledClassName
          : "bg-app-panel-strong text-[#5f564a] hover:bg-app-panel-soft"
      }`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <span className="flex items-center gap-3">
        <span className="flex size-4 items-center justify-center">{icon}</span>
        <span className="whitespace-nowrap">{label}</span>
      </span>
      {active ? <Check className="size-4 shrink-0 text-[#5b4128]" /> : null}
    </button>
  );
}

export function ComposerMobileToolbar({
  attachmentUploadAvailable,
  attachmentsPresent,
  isStreaming,
  composerMode,
  onComposerModeChange,
  onAddAttachment,
  onNewDebate,
  onNewBattle,
  onReasoningProfileChange,
  reasoningProfile,
  selectedModelOption,
  showImageModeOption,
  showNewDebateOption,
  showNewBattleOption,
  showReasoningProfile,
  toolMode,
  onToggleRag,
  onToggleWeb,
}: ComposerMobileToolbarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const imageMode = composerMode === "image";
  const addDisabled = isStreaming || imageMode || !attachmentUploadAvailable;
  const ragEnabled = !imageMode && toolMode === "knowledge";
  const webEnabled = !imageMode && toolMode === "search";

  const handleToggleImageMode = () => {
    onComposerModeChange(imageMode ? "chat" : "image");
  };

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, []);

  return (
    <div className="md:hidden">
      <div className="flex items-center gap-1.5">
        <div className="relative shrink-0" ref={menuRef}>
          <button
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            aria-label="Open tools"
            className="flex h-10 w-10 items-center justify-center rounded-[8px] border border-app-border bg-app-panel-strong text-[#5f564a] transition-colors hover:bg-app-panel-soft hover:text-app-text"
            onClick={() => setMenuOpen((value) => !value)}
            type="button"
          >
            <Plus className={`size-4 transition-transform ${menuOpen ? "rotate-45" : ""}`} />
          </button>

          {menuOpen ? (
            <div className="absolute bottom-[calc(100%+10px)] left-0 z-20 w-[min(220px,calc(100vw-5rem))] overflow-hidden rounded-lg border border-app-border bg-app-panel-strong">
              <MobileMenuAction
                disabled={addDisabled}
                icon={<Paperclip className="size-4" />}
                label="上传照片和文件"
                onClick={() => {
                  onAddAttachment();
                  // 移动端会先切到系统文件选择器；返回页面时保留上拉菜单，避免用户感知成菜单闪退。
                }}
              />
              {showImageModeOption ? (
                <MobileMenuAction
                  active={imageMode}
                  disabled={isStreaming}
                  icon={<Image className="size-4" />}
                  label="创建图片"
                  onClick={() => {
                    handleToggleImageMode();
                    setMenuOpen(false);
                  }}
                />
              ) : null}
              {showNewDebateOption ? (
                <MobileMenuAction
                  disabled={isStreaming}
                  icon={<Scale className="size-4" />}
                  label="新建辩论"
                  onClick={() => {
                    onNewDebate();
                    setMenuOpen(false);
                  }}
                />
              ) : null}
              {showNewBattleOption ? (
                <MobileMenuAction
                  disabled={isStreaming}
                  icon={<Swords className="size-4" />}
                  label="模型对战"
                  onClick={() => {
                    onNewBattle();
                    setMenuOpen(false);
                  }}
                />
              ) : null}
              <MobileMenuAction
                active={ragEnabled}
                disabled={isStreaming || imageMode}
                icon={<BookOpen className="size-4" />}
                label="知识库"
                onClick={() => {
                  onToggleRag();
                  setMenuOpen(false);
                }}
              />
              <MobileMenuAction
                active={webEnabled}
                disabled={isStreaming || imageMode}
                icon={<Globe className="size-4" />}
                label="网页搜索"
                onClick={() => {
                  onToggleWeb();
                  setMenuOpen(false);
                }}
              />
            </div>
          ) : null}
        </div>
        {!imageMode && showReasoningProfile && selectedModelOption ? (
          <div className="min-w-0">
            <ReasoningProfileSelect
              compact
              label="Reasoning"
              menuPlacement="top"
              modelOption={selectedModelOption}
              onChange={onReasoningProfileChange}
              triggerContent="label_only"
              value={reasoningProfile}
            />
          </div>
        ) : null}
      </div>
      {attachmentsPresent ? <div className="sr-only">Attachments ready</div> : null}
    </div>
  );
}
