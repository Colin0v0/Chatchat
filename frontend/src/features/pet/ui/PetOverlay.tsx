import { Apple, Droplets, Heart, MessageCircle, Moon, Send, X } from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import { useDesktopPet } from "../model/useDesktopPet";
import type { PetCompanionContext } from "../api/petChat";
import type { PetNeedKey, PetNeedSnapshot, PetNeedTone } from "../model/petBehavior";
import type { PetPreferences } from "../model/usePetPreferences";
import type { PetSignal } from "../model/petSignals";

type PetPosition = {
  bottom: number;
  left: number;
};

type PetOverlayProps = {
  activitySignal?: PetSignal | null;
  context: PetCompanionContext;
  onDragEnd: (position: PetPosition) => void;
  preferences: PetPreferences;
  targetPosition: PetPosition;
};

type PetActionButtonProps = {
  active?: boolean;
  children: ReactNode;
  label: string;
  onClick: () => void;
};

type PetStatBarProps = {
  need: PetNeedSnapshot;
};

type ViewportSize = {
  height: number;
  width: number;
};

const PET_BOX_SIZE = 144;
const QUICKBAR_WIDTH = 92;
const QUICKBAR_HEIGHT = 38;
const CARE_WIDTH = 292;
// 照顾面板只保留状态行和照顾入口，避免像系统说明卡一样打断宠物感。
const CARE_HEIGHT = 236;
const PANEL_GAP = 8;
const PAGE_EDGE_PADDING = 12;
const CHAT_WIDTH = 266;
const CHAT_HEIGHT = 238;
const QUICKBAR_AUTO_CLOSE_MS = 5000;
const PET_NEED_COLORS: Record<PetNeedKey, string> = {
  energy: "bg-[#6b9fbd]",
  hunger: "bg-[#d98645]",
  mood: "bg-[#d96c81]",
  thirst: "bg-[#58a8c8]",
};
const PET_NEED_TONE_CLASSES: Record<PetNeedTone, string> = {
  critical: "text-app-danger",
  good: "text-app-muted",
  low: "text-[#9a6315]",
  soft: "text-app-muted",
};

function PetActionButton({ active = false, children, label, onClick }: PetActionButtonProps) {
  const buttonClassName = `group/action flex h-8 w-8 items-center justify-center rounded-full border shadow-[0_5px_14px_rgba(34,24,16,0.12)] backdrop-blur transition focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong ${
    active
      ? "border-[#f0c45f] bg-[#fff2c2] text-[#9a6315] ring-2 ring-[#f0c45f]/35 hover:-translate-y-1 hover:bg-[#ffe5a3] hover:shadow-[0_8px_18px_rgba(171,111,28,0.22)]"
      : "border-app-border bg-app-panel-strong/95 text-app-accent-strong hover:-translate-y-0.5 hover:bg-app-panel-soft"
  }`;

  return (
    <button
      aria-label={label}
      aria-pressed={active}
      className={buttonClassName}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}

function PetCareActionButton({ active = false, children, label, onClick }: PetActionButtonProps) {
  const buttonClassName = `group/action flex h-8 w-8 items-center justify-center rounded-full border shadow-[0_5px_14px_rgba(34,24,16,0.12)] transition focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong ${
    active
      ? "border-[#f0c45f] bg-[#fff2c2] text-[#9a6315] ring-2 ring-[#f0c45f]/35 hover:bg-[#ffe5a3]"
      : "border-app-border bg-app-panel-strong text-app-accent-strong hover:bg-app-panel-soft"
  }`;

  return (
    <div className="flex min-w-0 flex-col items-center gap-1">
      <button
        aria-label={label}
        aria-pressed={active}
        className={buttonClassName}
        onClick={onClick}
        title={label}
        type="button"
      >
        {children}
      </button>
      <span className="max-w-full truncate text-[11px] leading-none text-app-muted">{label}</span>
    </div>
  );
}

function PetStatBar({ need }: PetStatBarProps) {
  return (
    <div className="grid grid-cols-[42px_minmax(0,1fr)_58px] items-center gap-2 text-[12px] text-app-muted">
      <span>{need.label}</span>
      <div
        aria-label={`${need.label} ${need.value}%`}
        className="h-1.5 overflow-hidden rounded-full bg-[rgba(95,84,72,0.16)]"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={need.value}
      >
        <div className={`h-full rounded-full ${PET_NEED_COLORS[need.key]}`} style={{ width: `${need.value}%` }} />
      </div>
      <span className={`text-right ${PET_NEED_TONE_CLASSES[need.tone]}`}>{need.stateLabel}</span>
    </div>
  );
}

function readViewportSize(): ViewportSize {
  return {
    height: window.innerHeight,
    width: window.innerWidth,
  };
}

export function PetOverlay({ activitySignal, context, onDragEnd, preferences, targetPosition }: PetOverlayProps) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const petVisualRef = useRef<HTMLDivElement | null>(null);
  const [careOpen, setCareOpen] = useState(false);
  const [chatDraft, setChatDraft] = useState("");
  const [controlsOpen, setControlsOpen] = useState(false);
  const controlsAutoCloseTimerRef = useRef<number | null>(null);
  const controlsToggleFrameRef = useRef<number | null>(null);
  const [viewportSize, setViewportSize] = useState<ViewportSize>(() => readViewportSize());
  const pet = useDesktopPet(stageRef, {
    activitySignal,
    context,
    movementPaused: careOpen || controlsOpen,
    onDragEnd,
    preferences,
    targetPosition,
    visualRef: petVisualRef,
  });

  useEffect(() => {
    function handleResize() {
      setViewportSize(readViewportSize());
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    return () => {
      if (controlsAutoCloseTimerRef.current !== null) {
        window.clearTimeout(controlsAutoCloseTimerRef.current);
      }

      if (controlsToggleFrameRef.current !== null) {
        window.cancelAnimationFrame(controlsToggleFrameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (controlsAutoCloseTimerRef.current !== null) {
      window.clearTimeout(controlsAutoCloseTimerRef.current);
      controlsAutoCloseTimerRef.current = null;
    }

    if (!controlsOpen || careOpen || pet.chat.opened) {
      return;
    }

    // 头顶入口只是临时操作区；不操作时自动收起，狐狸也能继续自己散步。
    controlsAutoCloseTimerRef.current = window.setTimeout(() => {
      controlsAutoCloseTimerRef.current = null;
      setControlsOpen(false);
    }, QUICKBAR_AUTO_CLOSE_MS);
  }, [careOpen, controlsOpen, pet.chat.opened]);

  function handleChatSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void pet.chat.submit(chatDraft);
    setChatDraft("");
  }

  function openCarePanel() {
    pet.chat.close();
    setControlsOpen(false);
    setCareOpen(true);
  }

  function closeCarePanel() {
    setCareOpen(false);
  }

  function openChatPanel() {
    setCareOpen(false);
    setControlsOpen(false);
    pet.chat.open();
  }

  const floatingPanelOpen = careOpen || pet.chat.opened;
  // 头顶操作改成“点狐狸才展开”，避免 hover 反复抢焦点、遮挡气泡和面板。
  const quickbarVisible = controlsOpen && !pet.isDragging && !floatingPanelOpen;
  const petTop = viewportSize.height - (pet.position.bottom - pet.visualFootOffset) - PET_BOX_SIZE;
  const visualTop = petTop + pet.visualTopOffset;
  const quickbarFitsAbove = visualTop >= QUICKBAR_HEIGHT + PANEL_GAP + PAGE_EDGE_PADDING;
  const quickbarTop = quickbarFitsAbove ? pet.visualTopOffset - QUICKBAR_HEIGHT - PANEL_GAP : PET_BOX_SIZE + PANEL_GAP;
  const quickbarLeft = Math.min(
    viewportSize.width - QUICKBAR_WIDTH - PAGE_EDGE_PADDING - pet.position.left,
    Math.max(PAGE_EDGE_PADDING - pet.position.left, pet.visualCenterX - QUICKBAR_WIDTH / 2),
  );
  const careFitsAbove = visualTop >= CARE_HEIGHT + PANEL_GAP + PAGE_EDGE_PADDING;
  const careTop = careFitsAbove ? pet.visualTopOffset - CARE_HEIGHT - PANEL_GAP : PET_BOX_SIZE + PANEL_GAP;
  const careLeft = Math.min(
    viewportSize.width - CARE_WIDTH - PAGE_EDGE_PADDING - pet.position.left,
    Math.max(PAGE_EDGE_PADDING - pet.position.left, pet.visualCenterX - CARE_WIDTH / 2),
  );
  const chatFitsAbove = visualTop >= CHAT_HEIGHT + PANEL_GAP + PAGE_EDGE_PADDING;
  const chatTop = chatFitsAbove ? pet.visualTopOffset - CHAT_HEIGHT - PANEL_GAP : PET_BOX_SIZE + PANEL_GAP;
  const chatLeft = Math.min(
    viewportSize.width - CHAT_WIDTH - PAGE_EDGE_PADDING - pet.position.left,
    Math.max(PAGE_EDGE_PADDING - pet.position.left, pet.visualCenterX - CHAT_WIDTH / 2),
  );
  const quickbarClassName = `pointer-events-auto absolute z-30 flex items-center justify-center gap-2 transition-all duration-200 ${
    quickbarVisible
      ? "translate-y-0 scale-100 opacity-100"
      : "pointer-events-none -translate-y-1 scale-95 opacity-0"
  }`;

  return (
    <div ref={stageRef} className="pointer-events-none fixed inset-0 z-20 overflow-visible">
      <div
        ref={petVisualRef}
        className="group pointer-events-auto absolute select-none"
        style={{
          bottom: pet.position.bottom - pet.visualFootOffset,
          height: PET_BOX_SIZE,
          left: pet.position.left,
          transition: pet.isDragging
            ? "none"
            : `left ${pet.moveDurationMs}ms linear, bottom ${pet.moveDurationMs}ms linear`,
          width: PET_BOX_SIZE,
        }}
      >
        <div
          className={quickbarClassName}
          style={{
            height: QUICKBAR_HEIGHT,
            left: quickbarLeft,
            top: quickbarTop,
            width: QUICKBAR_WIDTH,
          }}
        >
          <PetActionButton label="照顾" onClick={openCarePanel}>
            <Heart className="size-3.5" />
          </PetActionButton>
          <PetActionButton label="聊天" onClick={openChatPanel}>
            <MessageCircle className="size-3.5" />
          </PetActionButton>
        </div>

        {careOpen ? (
          <div
            className="pointer-events-auto absolute z-40 flex flex-col overflow-hidden rounded-[8px] border border-app-border bg-app-panel-strong/96 shadow-[0_12px_30px_rgba(34,24,16,0.16)] backdrop-blur"
            style={{
              height: CARE_HEIGHT,
              left: careLeft,
              top: careTop,
              width: CARE_WIDTH,
            }}
          >
            <div className="flex h-9 items-center justify-between border-b border-app-border px-4">
              <div className="text-[13px] font-semibold text-app-text">照顾</div>
              <button
                aria-label="关闭照顾面板"
                className="flex h-7 w-7 items-center justify-center rounded-full text-app-muted transition hover:bg-app-panel-soft hover:text-app-text focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
                onClick={closeCarePanel}
                type="button"
              >
                <X className="size-3.5" />
              </button>
            </div>

            <div className="flex min-h-0 flex-1 flex-col justify-center gap-2.5 px-4 py-3">
              {pet.behavior.needs.map((need) => (
                <PetStatBar key={need.key} need={need} />
              ))}
            </div>

            <div className="grid h-[58px] shrink-0 grid-cols-4 place-items-center gap-2 border-t border-app-border px-4 py-2">
              <PetCareActionButton label="喂一点" onClick={pet.actions.feed}>
                <Apple className="size-3.5" />
              </PetCareActionButton>
              <PetCareActionButton label="添水" onClick={pet.actions.drink}>
                <Droplets className="size-3.5" />
              </PetCareActionButton>
              <PetCareActionButton
                active={pet.isSleeping}
                label={pet.isSleeping ? "叫醒" : "哄睡"}
                onClick={pet.actions.rest}
              >
                <Moon
                  className={`size-3.5 transition duration-200 ${
                    pet.isSleeping
                      ? "fill-[#f6c95b]/35 group-hover/action:-rotate-12 group-hover/action:scale-110"
                      : "group-hover/action:-rotate-6 group-hover/action:scale-110"
                  }`}
                />
              </PetCareActionButton>
              <PetCareActionButton label="夸一下" onClick={pet.actions.praise}>
                <Heart className="size-3.5" />
              </PetCareActionButton>
            </div>
          </div>
        ) : null}

        {pet.chat.opened ? (
          <div
            className="pointer-events-auto absolute z-40 flex flex-col rounded-[8px] border border-app-border bg-app-panel-strong/96 shadow-[0_12px_30px_rgba(34,24,16,0.16)] backdrop-blur"
            style={{
              height: CHAT_HEIGHT,
              left: chatLeft,
              top: chatTop,
              width: CHAT_WIDTH,
            }}
          >
            <div className="flex h-9 items-center justify-between border-b border-app-border px-3">
              <div className="text-[13px] font-semibold text-app-text">狐狸</div>
              <button
                aria-label="关闭聊天"
                className="flex h-7 w-7 items-center justify-center rounded-full text-app-muted transition hover:bg-app-panel-soft hover:text-app-text focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
                onClick={pet.chat.close}
                type="button"
              >
                <X className="size-3.5" />
              </button>
            </div>

            <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-3 py-2">
              {pet.chat.messages.map((message) => (
                <div
                  className={`max-w-[88%] rounded-[8px] px-2.5 py-1.5 text-[12px] leading-5 ${
                    message.role === "user"
                      ? "ml-auto bg-app-accent-strong text-app-panel-strong"
                      : "mr-auto bg-app-panel-soft text-app-text"
                  }`}
                  key={message.id}
                >
                  {message.text}
                </div>
              ))}
              {pet.chat.pending ? (
                <div className="mr-auto rounded-[8px] bg-app-panel-soft px-2.5 py-1.5 text-[12px] leading-5 text-app-muted">
                  狐狸在想...
                </div>
              ) : null}
              {pet.chat.error ? (
                <div className="mr-auto rounded-[8px] border border-app-border px-2.5 py-1.5 text-[12px] leading-5 text-app-muted">
                  {pet.chat.error}
                </div>
              ) : null}
            </div>

            <form className="flex items-center gap-1.5 border-t border-app-border p-2" onSubmit={handleChatSubmit}>
              <input
                aria-label="给狐狸发消息"
                className="min-w-0 flex-1 rounded-full border border-app-border bg-app-panel px-3 py-1.5 text-[12px] text-app-text placeholder:text-app-muted focus:border-app-border-strong"
                maxLength={80}
                disabled={pet.chat.pending}
                onChange={(event) => setChatDraft(event.target.value)}
                placeholder="跟狐狸说点什么"
                value={chatDraft}
              />
              <button
                aria-label="发送"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-app-accent-strong text-app-panel-strong transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-45 focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
                disabled={pet.chat.pending || !chatDraft.trim()}
                type="submit"
              >
                <Send className="size-3.5" />
              </button>
            </form>
          </div>
        ) : null}

        <button
          aria-label="桌面宠物"
          className="pointer-events-auto relative flex h-full w-full touch-none items-center justify-center overflow-visible bg-transparent transition-transform duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
          onClick={(event) => {
            event.currentTarget.blur();
            if (pet.handlers.click({ playReaction: false })) {
              // pointerDown 会先把走路中的狐狸钉住；等一帧再展开，避免首次点击按上一帧位置算浮层。
              if (controlsToggleFrameRef.current !== null) {
                window.cancelAnimationFrame(controlsToggleFrameRef.current);
              }
              controlsToggleFrameRef.current = window.requestAnimationFrame(() => {
                controlsToggleFrameRef.current = null;
                setControlsOpen((current) => !current);
              });
            }
          }}
          onPointerCancel={pet.handlers.pointerCancel}
          onPointerDown={pet.handlers.pointerDown}
          onPointerMove={pet.handlers.pointerMove}
          onPointerUp={pet.handlers.pointerUp}
          type="button"
        >
          <img
            alt=""
            className={`h-full w-full object-contain ${
              pet.facing === -1 ? "scale-x-[-1]" : ""
            }`}
            draggable={false}
            src={pet.framePath}
          />
        </button>
      </div>
    </div>
  );
}
