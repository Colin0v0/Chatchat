import type { PointerEvent, RefObject } from "react";
import { useEffect, useRef, useState } from "react";

import { requestPetChatReply, type PetCompanionContext } from "../api/petChat";
import { fetchPetState, savePetState, type PetStateApiResponse } from "../api/petState";
import {
  resolvePetBehaviorSnapshot,
  type PetBehaviorSnapshot,
  type PetMotiveKey,
} from "./petBehavior";
import {
  PET_ANIMATIONS,
  PET_MAX_FOOT_OFFSET,
  PET_UI_CENTER_X,
  resolvePetFrameCenterX,
  resolvePetFrameFootOffset,
  resolvePetFrameScale,
  type PetAnimationKey,
} from "./petSprites";
import type { PetPreferences, PetProactiveLevel } from "./usePetPreferences";
import type { PetSignal } from "./petSignals";

type PetStats = {
  energy: number;
  hunger: number;
  mood: number;
  thirst: number;
  updatedAt: number;
};

type PetPosition = {
  bottom: number;
  left: number;
};

type StageSize = {
  height: number;
  width: number;
};

type DesktopPetOptions = {
  activitySignal?: PetSignal | null;
  context: PetCompanionContext;
  movementPaused: boolean;
  onDragEnd: (position: PetPosition) => void;
  preferences: PetPreferences;
  targetPosition: PetPosition;
  visualRef: RefObject<HTMLDivElement | null>;
};

type PetMode = "awake" | "sleeping";

type PetStateSnapshot = {
  mode: PetMode;
  position: PetPosition;
  stats: PetStats;
};

type DragState = {
  bottom: number;
  left: number;
  moved: boolean;
  pointerId: number;
  startedAt: number;
  startX: number;
  startY: number;
};

type PetChatMessage = {
  id: number;
  role: "pet" | "user";
  text: string;
};

const PET_SIZE = 144;
const DEFAULT_PET_FOOT_OFFSET = PET_ANIMATIONS.idle.anchor.footOffset;
const PAGE_EDGE_PADDING = 12;
const PET_MIN_BOTTOM = DEFAULT_PET_FOOT_OFFSET + PAGE_EDGE_PADDING;
const MIN_WALK_DISTANCE = 36;
const WALK_SPEED_PX_PER_MS = 0.095;
const AWAKE_STATS_TICK_MS = 60000;
const SLEEP_STATS_TICK_MS = 5000;
const LOW_STAT_ENTER_THRESHOLD = 20;
const LOW_STAT_RECOVER_THRESHOLD = 25;
// 中文注释：精力进入“困到发软”这档后就应该自己睡，不要让文案阈值和行为阈值分家。
const AUTO_SLEEP_THRESHOLD = LOW_STAT_ENTER_THRESHOLD;
const PET_CHAT_HISTORY_LIMIT = 8;
const DRAG_EXIT_PADDING = 8;
const LONG_DRAG_REACTION_MS = 6500;
const LOW_STAT_REACTION_INTERVALS: Record<PetProactiveLevel, number> = {
  high: 60000,
  low: 300000,
  normal: 120000,
};
const AMBIENT_BEHAVIOR_INTERVALS: Record<PetProactiveLevel, number> = {
  high: 45000,
  low: 180000,
  normal: 90000,
};
const AMBIENT_MOTIVE_ANIMATIONS: Record<PetMotiveKey, PetAnimationKey | null> = {
  curious: "emotion",
  hungry: "click",
  lonely: "emotion",
  resting: null,
  settled: null,
  sleepy: "emotion",
  thirsty: "click",
  unwell: null,
};
const INITIAL_STATS: PetStats = {
  energy: 78,
  hunger: 76,
  mood: 82,
  thirst: 74,
  updatedAt: Date.now(),
};
const INITIAL_MODE: PetMode = "awake";
const INITIAL_CHAT_MESSAGES: PetChatMessage[] = [
  { id: 1, role: "pet", text: "我是小狐～有话要跟你说呢！" },
];
const CARE_NEGATION_WORDS = ["不要", "不用", "不想", "不能", "别", "不", "没", "没有", "无需"];
const FEED_INTENT_PHRASES = ["喂一下", "喂点", "喂它", "喂狐狸", "给它吃", "给狐狸吃", "吃饭", "想吃", "零食", "食物"];
const DRINK_INTENT_PHRASES = ["喝水", "添水", "给它水", "给狐狸水", "渴了", "口渴", "想喝水"];
const SLEEP_INTENT_PHRASES = ["睡觉", "休息", "晚安", "哄睡", "困了", "想睡"];
const PRAISE_INTENT_PHRASES = ["夸一下", "夸它", "夸狐狸", "乖", "棒", "可爱", "喜欢"];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function normalizeStats(stats: PetStats): PetStats {
  return {
    energy: clamp(Math.round(stats.energy), 0, 100),
    hunger: clamp(Math.round(stats.hunger), 0, 100),
    mood: clamp(Math.round(stats.mood), 0, 100),
    thirst: clamp(Math.round(stats.thirst), 0, 100),
    updatedAt: stats.updatedAt,
  };
}

function applyOfflineDecay(stats: PetStats): PetStats {
  const elapsedMinutes = Math.max(0, (Date.now() - stats.updatedAt) / 60000);

  return normalizeStats({
    // 中文注释：离线衰减按连续时间结算，最后统一归整，避免 14/15 分钟这种临界跳变。
    energy: stats.energy - elapsedMinutes / 30,
    hunger: stats.hunger - elapsedMinutes / 15,
    mood: stats.mood - elapsedMinutes / 45,
    thirst: stats.thirst - elapsedMinutes / 15,
    updatedAt: Date.now(),
  });
}

function toPetStateSnapshot(payload: PetStateApiResponse): PetStateSnapshot {
  return {
    mode: payload.sleeping ? "sleeping" : "awake",
    position: payload.position,
    // 中文注释：后端只保存真实数值和服务端更新时间，前端拿到后再结算离线衰减。
    stats: applyOfflineDecay({
      ...payload.stats,
      updatedAt: payload.updatedAt,
    }),
  };
}

function resolveBaseAnimation(mode: PetMode, lowNeedActive: boolean): PetAnimationKey {
  if (mode === "sleeping") {
    return "sleep";
  }

  if (lowNeedActive) {
    return "sad";
  }

  return "idle";
}

function applyStatsDelta(stats: PetStats, delta: Partial<Omit<PetStats, "updatedAt">>): PetStats {
  return normalizeStats({
    energy: stats.energy + (delta.energy ?? 0),
    hunger: stats.hunger + (delta.hunger ?? 0),
    mood: stats.mood + (delta.mood ?? 0),
    thirst: stats.thirst + (delta.thirst ?? 0),
    updatedAt: Date.now(),
  });
}

function hasStatsDelta(delta: Partial<Omit<PetStats, "updatedAt">>) {
  return (
    delta.energy !== undefined
    || delta.hunger !== undefined
    || delta.mood !== undefined
    || delta.thirst !== undefined
  );
}

function applyAwakeStatsTick(stats: PetStats, tickCount: number): PetStats {
  // 醒着按分钟级缓慢消耗，避免宠物状态像倒计时一样催人。
  const lowNeedPenalty = stats.hunger <= 25 || stats.thirst <= 25;
  return normalizeStats({
    energy: stats.energy - (tickCount % 3 === 0 ? 1 : 0),
    hunger: stats.hunger - 1,
    mood: stats.mood - (lowNeedPenalty ? 1 : 0),
    thirst: stats.thirst - 1,
    updatedAt: Date.now(),
  });
}

function applySleepStatsTick(stats: PetStats, tickCount: number): PetStats {
  // 睡觉是持续恢复：精力每轮都涨，心情慢一点涨，饱食和水分更慢地消耗。
  return normalizeStats({
    energy: stats.energy + 1,
    hunger: stats.hunger - (tickCount % 6 === 0 ? 1 : 0),
    mood: stats.mood + (tickCount % 3 === 0 ? 1 : 0),
    thirst: stats.thirst - (tickCount % 6 === 0 ? 1 : 0),
    updatedAt: Date.now(),
  });
}

function shouldEnterLowNeedPose(stats: PetStats) {
  return (
    stats.hunger <= LOW_STAT_ENTER_THRESHOLD
    || stats.mood <= LOW_STAT_ENTER_THRESHOLD
    || stats.thirst <= LOW_STAT_ENTER_THRESHOLD
  );
}

function hasRecoveredLowNeedStats(stats: PetStats) {
  return (
    stats.hunger >= LOW_STAT_RECOVER_THRESHOLD
    && stats.mood >= LOW_STAT_RECOVER_THRESHOLD
    && stats.thirst >= LOW_STAT_RECOVER_THRESHOLD
  );
}

function canReturnToBaseAnimation(animation: PetAnimationKey) {
  const phase = PET_ANIMATIONS[animation].phase;
  return phase === "pose" || phase === "locomotion";
}

function hasNearbyCareNegation(text: string, phraseStart: number) {
  const prefix = text.slice(Math.max(0, phraseStart - 5), phraseStart);
  return CARE_NEGATION_WORDS.some((word) => prefix.includes(word));
}

function hasCareIntent(text: string, phrases: string[]) {
  return phrases.some((phrase) => {
    let searchStart = 0;
    while (searchStart < text.length) {
      const phraseStart = text.indexOf(phrase, searchStart);
      if (phraseStart === -1) {
        return false;
      }

      if (!hasNearbyCareNegation(text, phraseStart)) {
        return true;
      }

      // 中文注释：同一句里可能先否定再提出真实意图，继续找后面的明确短语。
      searchStart = phraseStart + phrase.length;
    }

    return false;
  });
}

function buildPetChatContext(context: PetCompanionContext, preferences: PetPreferences): PetCompanionContext {
  // 参考主对话和草稿是隐私开关：关闭时前端就不把内容发给宠物接口。
  return {
    activeSection: context.activeSection,
    conversation: preferences.referenceConversation ? context.conversation : null,
    draft: preferences.referenceDraft ? context.draft : "",
  };
}

function clampPosition(position: PetPosition, stageSize: StageSize): PetPosition {
  const maxLeft = Math.max(PAGE_EDGE_PADDING, stageSize.width - PET_SIZE - PAGE_EDGE_PADDING);
  const maxBottom = Math.max(
    PET_MIN_BOTTOM,
    stageSize.height + PET_MAX_FOOT_OFFSET - PET_SIZE - PAGE_EDGE_PADDING,
  );
  const bottom = clamp(position.bottom, PET_MIN_BOTTOM, maxBottom);
  const left = clamp(position.left, PAGE_EDGE_PADDING, maxLeft);

  if (bottom === position.bottom && left === position.left) {
    // 中文注释：没被边界修正时复用原对象，减少拖拽/走路时的无意义重渲染链路。
    return position;
  }

  return {
    // position.bottom 表示狐狸视觉脚底的位置，渲染时会扣掉透明画布的底部体积。
    bottom,
    left,
  };
}

function resolveWalkMoveMs(distancePx: number) {
  // 中文注释：走路速度固定为同一套 px/ms，不再按距离夹上下限，否则短距离和长距离看起来快慢不一致。
  return Math.max(1, Math.round(distancePx / WALK_SPEED_PX_PER_MS));
}

function resolveAmbientBehaviorDelayMs(level: PetProactiveLevel) {
  // 主动性不固定节拍：同一个频率档也会有轻微浮动，避免像定时器报点。
  const baseDelay = AMBIENT_BEHAVIOR_INTERVALS[level];
  return Math.round(baseDelay * (0.78 + Math.random() * 0.44));
}

function isPointerOutsideViewport(event: PointerEvent<HTMLButtonElement>) {
  return (
    event.clientX < -DRAG_EXIT_PADDING
    || event.clientY < -DRAG_EXIT_PADDING
    || event.clientX > window.innerWidth + DRAG_EXIT_PADDING
    || event.clientY > window.innerHeight + DRAG_EXIT_PADDING
  );
}

export function useDesktopPet(stageRef: RefObject<HTMLDivElement | null>, options: DesktopPetOptions) {
  const initialStateRef = useRef<PetStateSnapshot | null>(null);
  if (initialStateRef.current === null) {
    initialStateRef.current = { mode: INITIAL_MODE, position: options.targetPosition, stats: INITIAL_STATS };
  }

  const [stageSize, setStageSize] = useState<StageSize>({ height: 0, width: 0 });
  const [mode, setMode] = useState<PetMode>(() => initialStateRef.current!.mode);
  const [animation, setAnimation] = useState<PetAnimationKey>(() =>
    resolveBaseAnimation(
      initialStateRef.current!.mode,
      initialStateRef.current!.mode === "awake" && shouldEnterLowNeedPose(initialStateRef.current!.stats),
    ),
  );
  const [frameIndex, setFrameIndex] = useState(0);
  const [stats, setStats] = useState(() => initialStateRef.current!.stats);
  const [position, setPosition] = useState(() => initialStateRef.current!.position);
  const [facing, setFacing] = useState<1 | -1>(1);
  const [chatMessages, setChatMessages] = useState<PetChatMessage[]>(INITIAL_CHAT_MESSAGES);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatPending, setChatPending] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [petStateReady, setPetStateReady] = useState(false);
  const [lowNeedActive, setLowNeedActive] = useState(() =>
    initialStateRef.current!.mode === "awake" && shouldEnterLowNeedPose(initialStateRef.current!.stats),
  );
  const [moveDurationMs, setMoveDurationMs] = useState(0);
  const behavior = resolvePetBehaviorSnapshot({
    context: options.context,
    mode,
    preferences: options.preferences,
    stats,
  });
  const ambientBehaviorTimerRef = useRef<number | null>(null);
  const behaviorRef = useRef<PetBehaviorSnapshot>(behavior);
  const walkStartFrameRef = useRef<number | null>(null);
  const dragStateRef = useRef<DragState | null>(null);
  const wanderTimerRef = useRef<number | null>(null);
  const suppressClickRef = useRef(false);
  const activitySignalIdRef = useRef<number | null>(null);
  const chatMessageIdRef = useRef(INITIAL_CHAT_MESSAGES.length);
  const chatMessagesRef = useRef(chatMessages);
  const chatPendingRef = useRef(chatPending);
  const contextRef = useRef(options.context);
  const preferencesRef = useRef(options.preferences);
  const awakeTickCountRef = useRef(0);
  const sleepTickCountRef = useRef(0);
  const lastLowStatReactionAtRef = useRef(0);
  const animationRef = useRef(animation);
  const frameIndexRef = useRef(frameIndex);
  const lowNeedActiveRef = useRef(lowNeedActive);
  const modeRef = useRef(mode);
  const petStateLoadedRef = useRef(false);
  const petStateSaveTimerRef = useRef<number | null>(null);
  const positionRef = useRef(position);
  const statsRef = useRef(stats);
  const onDragEndRef = useRef(options.onDragEnd);

  const animationDefinition = PET_ANIMATIONS[animation];
  const activeFrameIndex = Math.min(frameIndex, animationDefinition.frames.length - 1);
  const activeAnchor = {
    ...animationDefinition.anchor,
    footOffset: resolvePetFrameFootOffset(animation, activeFrameIndex),
    uiCenterX: resolvePetFrameCenterX(animation, activeFrameIndex),
  };
  const framePath = animationDefinition.frames[activeFrameIndex];
  behaviorRef.current = behavior;

  useEffect(() => {
    animationRef.current = animation;
  }, [animation]);

  useEffect(() => {
    frameIndexRef.current = frameIndex;
  }, [frameIndex]);

  useEffect(() => {
    lowNeedActiveRef.current = lowNeedActive;
  }, [lowNeedActive]);

  useEffect(() => {
    onDragEndRef.current = options.onDragEnd;
  }, [options.onDragEnd]);

  useEffect(() => {
    contextRef.current = options.context;
  }, [options.context]);

  useEffect(() => {
    preferencesRef.current = options.preferences;
  }, [options.preferences]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    chatMessagesRef.current = chatMessages;
  }, [chatMessages]);

  useEffect(() => {
    chatPendingRef.current = chatPending;
  }, [chatPending]);

  useEffect(() => {
    if (wanderTimerRef.current !== null) {
      // 中文注释：走路时 position state 是 CSS 过渡终点，positionRef 继续代表屏幕当前点，避免后续动作拿未来坐标。
      return;
    }

    positionRef.current = position;
  }, [position]);

  useEffect(() => {
    statsRef.current = stats;
  }, [stats]);

  useEffect(() => {
    const stageNode = stageRef.current;
    if (!stageNode) {
      return;
    }

    function updateStageSize() {
      setStageSize({
        height: stageNode!.clientHeight,
        width: stageNode!.clientWidth,
      });
    }

    updateStageSize();

    // 让宠物始终跟着应用窗口尺寸变化重新贴边，避免切换窗口后卡出容器。
    const observer = new ResizeObserver(updateStageSize);
    observer.observe(stageNode);
    return () => observer.disconnect();
  }, [stageRef]);

  useEffect(() => {
    if (stageSize.width === 0 || stageSize.height === 0) {
      return;
    }

    setPosition((current) => clampPosition(current, stageSize));
  }, [stageSize.height, stageSize.width]);

  useEffect(() => {
    if (petStateLoadedRef.current || stageSize.width === 0 || stageSize.height === 0) {
      return;
    }

    let cancelled = false;

    async function loadPetState() {
      const snapshot = toPetStateSnapshot(await fetchPetState());
      if (cancelled) {
        return;
      }

      const nextPosition = clampPosition(snapshot.position, stageSize);
      const nextMode = snapshot.mode;
      const nextLowNeedActive = nextMode === "awake" && shouldEnterLowNeedPose(snapshot.stats);
      petStateLoadedRef.current = true;
      positionRef.current = nextPosition;
      statsRef.current = snapshot.stats;
      modeRef.current = nextMode;
      lowNeedActiveRef.current = nextLowNeedActive;
      setMoveDurationMs(0);
      setPosition(nextPosition);
      setStats(snapshot.stats);
      setMode(nextMode);
      setLowNeedActive(nextLowNeedActive);
      setFrameIndex(0);
      setAnimation(resolveBaseAnimation(nextMode, nextLowNeedActive));
      setPetStateReady(true);
    }

    void loadPetState().catch((error: unknown) => {
      console.error("Failed to load pet state", error);
    });

    return () => {
      cancelled = true;
    };
  }, [stageSize.height, stageSize.width]);

  useEffect(() => {
    if (
      stageSize.width === 0
      || stageSize.height === 0
      || !petStateReady
      || dragStateRef.current
      || chatOpen
      || options.movementPaused
      || (modeRef.current === "awake" && lowNeedActive)
      || wanderTimerRef.current !== null
      || animationRef.current === "pickup"
      || animationRef.current === "pickupHold"
      || animationRef.current === "putdown"
      || (animationRef.current !== "idle" && animationRef.current !== "walk")
    ) {
      return;
    }

    const nextPosition = clampPosition(options.targetPosition, stageSize);
    const deltaX = nextPosition.left - positionRef.current.left;
    const deltaBottom = nextPosition.bottom - positionRef.current.bottom;
    const distancePx = Math.hypot(deltaX, deltaBottom);
    if (distancePx < MIN_WALK_DISTANCE) {
      if (wanderTimerRef.current !== null) {
        return;
      }

      positionRef.current = nextPosition;
      setMoveDurationMs(0);
      setPosition(nextPosition);
      if (animationRef.current === "walk") {
        clearWanderTimer();
        setFrameIndex(0);
        setAnimation(resolveBaseAnimation(modeRef.current, lowNeedActiveRef.current));
      }

      return;
    }

    clearWanderTimer();
    const moveMs = resolveWalkMoveMs(distancePx);
    setMoveDurationMs(moveMs);
    setFacing(deltaX >= 0 ? 1 : -1);
    setFrameIndex(0);
    setAnimation("walk");
    walkStartFrameRef.current = window.requestAnimationFrame(() => {
      walkStartFrameRef.current = null;
      setPosition(nextPosition);
    });

    wanderTimerRef.current = window.setTimeout(() => {
      wanderTimerRef.current = null;
      positionRef.current = nextPosition;
      setPosition(nextPosition);
      setMoveDurationMs(0);
      setFrameIndex(0);
      setAnimation(resolveBaseAnimation(modeRef.current, lowNeedActiveRef.current));
    }, moveMs);
  }, [
    animation,
    chatOpen,
    options.movementPaused,
    options.targetPosition.bottom,
    options.targetPosition.left,
    stageSize.height,
    stageSize.width,
    petStateReady,
    lowNeedActive,
  ]);

  useEffect(() => {
    if (!options.movementPaused) {
      return;
    }

    stopWalkingAtCurrentPosition();
  }, [options.movementPaused]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (animationDefinition.playMode === "hold") {
        return;
      }

      const nextIndex = frameIndex + 1;
      if (nextIndex < animationDefinition.frames.length) {
        setFrameIndex(nextIndex);
        return;
      }

      if (animationDefinition.playMode === "loop") {
        setFrameIndex(0);
        return;
      }

      if (dragStateRef.current && animationRef.current === "pickup") {
        setAnimation("pickupHold");
        setFrameIndex(0);
        return;
      }

      setAnimation(resolveBaseAnimation(modeRef.current, lowNeedActiveRef.current));
      setFrameIndex(0);
    }, animationDefinition.frameMs);

    return () => window.clearTimeout(timer);
  }, [animationDefinition, frameIndex]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (modeRef.current !== "awake") {
        return;
      }

      awakeTickCountRef.current += 1;
      setStats((current) => applyAwakeStatsTick(current, awakeTickCountRef.current));
    }, AWAKE_STATS_TICK_MS);

    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (modeRef.current !== "sleeping") {
        return;
      }

      sleepTickCountRef.current += 1;
      setStats((current) => applySleepStatsTick(current, sleepTickCountRef.current));
    }, SLEEP_STATS_TICK_MS);

    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!petStateReady) {
      return;
    }

    if (petStateSaveTimerRef.current !== null) {
      window.clearTimeout(petStateSaveTimerRef.current);
    }

    // 中文注释：拖拽和走路会频繁改坐标，统一轻微防抖后写库，避免每一帧都打后端。
    petStateSaveTimerRef.current = window.setTimeout(() => {
      petStateSaveTimerRef.current = null;
      void savePetState({
        sleeping: modeRef.current === "sleeping",
        position,
        stats: {
          energy: stats.energy,
          hunger: stats.hunger,
          mood: stats.mood,
          thirst: stats.thirst,
        },
      }).catch((error: unknown) => {
        console.error("Failed to save pet state", error);
      });
    }, 700);

    return () => {
      if (petStateSaveTimerRef.current !== null) {
        window.clearTimeout(petStateSaveTimerRef.current);
        petStateSaveTimerRef.current = null;
      }
    };
  }, [mode, petStateReady, position.bottom, position.left, stats.energy, stats.hunger, stats.mood, stats.thirst]);

  useEffect(() => {
    return () => {
      if (wanderTimerRef.current !== null) {
        window.clearTimeout(wanderTimerRef.current);
      }

      if (walkStartFrameRef.current !== null) {
        window.cancelAnimationFrame(walkStartFrameRef.current);
      }

      if (ambientBehaviorTimerRef.current !== null) {
        window.clearTimeout(ambientBehaviorTimerRef.current);
      }

      if (petStateSaveTimerRef.current !== null) {
        window.clearTimeout(petStateSaveTimerRef.current);
      }
    };
  }, []);

  function clearWanderTimer() {
    if (wanderTimerRef.current !== null) {
      window.clearTimeout(wanderTimerRef.current);
      wanderTimerRef.current = null;
    }

    if (walkStartFrameRef.current !== null) {
      window.cancelAnimationFrame(walkStartFrameRef.current);
      walkStartFrameRef.current = null;
    }
  }

  function speak(_text: string) {
    // 第一版取消狐狸头顶文字气泡，只保留动作反馈和聊天面板里的回复。
  }

  function nextChatMessageId() {
    chatMessageIdRef.current += 1;
    return chatMessageIdRef.current;
  }

  function openChat() {
    stopWalkingAtCurrentPosition();
    setChatError(null);
    setChatOpen(true);
  }

  function closeChat() {
    setChatOpen(false);
  }

  async function submitChatMessage(text: string) {
    const userText = text.trim();
    if (!userText || chatPendingRef.current) {
      return;
    }

    const historyMessages = chatMessagesRef.current.slice(-PET_CHAT_HISTORY_LIMIT);
    const userMessage = { id: nextChatMessageId(), role: "user" as const, text: userText };
    setChatError(null);
    setChatPending(true);
    setChatMessages((current) => [...current, userMessage].slice(-10));

    const normalizedText = userText.toLowerCase();
    // 聊天里的明确照顾意图会直接变成一次互动；回复本身交给后端模型生成。
    if (hasCareIntent(normalizedText, FEED_INTENT_PHRASES)) {
      playAnimation("eat", { hunger: 14, mood: 2 });
    } else if (hasCareIntent(normalizedText, DRINK_INTENT_PHRASES)) {
      playAnimation("drink", { energy: 2, mood: 2, thirst: 18 });
    } else if (hasCareIntent(normalizedText, SLEEP_INTENT_PHRASES)) {
      startSleeping();
    } else if (hasCareIntent(normalizedText, PRAISE_INTENT_PHRASES)) {
      playAnimation("praise", { mood: 8 });
    }

    try {
      const { reply } = await requestPetChatReply({
        context: buildPetChatContext(contextRef.current, preferencesRef.current),
        message: userText,
        messages: historyMessages.map((message) => ({
          role: message.role,
          text: message.text,
        })),
        replyLength: preferencesRef.current.replyLength,
        sleeping: modeRef.current === "sleeping",
        stats: {
          energy: statsRef.current.energy,
          hunger: statsRef.current.hunger,
          mood: statsRef.current.mood,
          thirst: statsRef.current.thirst,
        },
        tone: preferencesRef.current.tone,
      });
      setChatMessages((current) => [
        ...current,
        { id: nextChatMessageId(), role: "pet" as const, text: reply },
      ].slice(-10));
    } catch {
      setChatError("模型请求失败");
    } finally {
      setChatPending(false);
    }
  }

  function stopWalkingAtCurrentPosition(): PetPosition | null {
    clearWanderTimer();
    setMoveDurationMs(0);
    if (animationRef.current === "walk") {
      // 普通点击会先打断位移；同时收掉 walk 循环，避免打开聊天后原地踏步。
      setAnimation(resolveBaseAnimation(modeRef.current, lowNeedActiveRef.current));
      setFrameIndex(0);
    }

    const visualNode = options.visualRef.current;
    if (!visualNode || stageSize.width === 0 || stageSize.height === 0) {
      return null;
    }

    const rect = visualNode.getBoundingClientRect();
    const currentCenterX = resolvePetFrameCenterX(animationRef.current, frameIndexRef.current);
    const currentFootOffset = resolvePetFrameFootOffset(animationRef.current, frameIndexRef.current);
    const currentPosition = clampPosition(
      {
        // 读取浏览器当前渲染位置，动作发生时先把“正在路上”的狐狸钉住。
        bottom: window.innerHeight - rect.bottom + currentFootOffset,
        left: rect.left + currentCenterX - PET_UI_CENTER_X,
      },
      stageSize,
    );
    positionRef.current = currentPosition;
    setPosition(currentPosition);
    return currentPosition;
  }

  function playAnimation(nextAnimation: PetAnimationKey, statDelta: Partial<Omit<PetStats, "updatedAt">> = {}) {
    stopWalkingAtCurrentPosition();
    clearWanderTimer();
    setMode("awake");
    if (hasStatsDelta(statDelta)) {
      setStats((current) => applyStatsDelta(current, statDelta));
    }
    setAnimation(nextAnimation);
    setFrameIndex(0);
  }

  useEffect(() => {
    const signal = options.activitySignal;
    if (!signal || activitySignalIdRef.current === signal.id) {
      return;
    }

    activitySignalIdRef.current = signal.id;
    if (modeRef.current === "sleeping") {
      // 中文注释：睡着时主聊天的发送/完成/出错都不回应，也不顺手叫醒。
      return;
    }

    // 业务事件里，发送保持安静；只在完成和出错时给明确反馈，避免用户每次发消息都被动作打断。
    if (signal.type === "send") {
      return;
    }

    if (signal.type === "complete") {
      speak("写好啦");
      playAnimation("praise", { mood: 4 });
      return;
    }

    speak("好像出错了");
    playAnimation("hurt", { mood: -3 });
  }, [options.activitySignal]);

  useEffect(() => {
    if (mode !== "awake") {
      if (lowNeedActive) {
        setLowNeedActive(false);
      }
      return;
    }

    if (lowNeedActive) {
      if (hasRecoveredLowNeedStats(stats)) {
        setLowNeedActive(false);
      }
      return;
    }

    if (shouldEnterLowNeedPose(stats)) {
      setLowNeedActive(true);
    }
  }, [lowNeedActive, mode, stats.hunger, stats.mood, stats.thirst]);

  useEffect(() => {
    if (mode !== "awake" || isDragging || chatOpen || chatPending || lowNeedActive || options.movementPaused) {
      return;
    }

    let stopped = false;

    function scheduleAmbientBehavior() {
      ambientBehaviorTimerRef.current = window.setTimeout(() => {
        ambientBehaviorTimerRef.current = null;
        if (stopped) {
          return;
        }

        const nextAnimation = AMBIENT_MOTIVE_ANIMATIONS[behaviorRef.current.motive];
        if (
          nextAnimation !== null
          && modeRef.current === "awake"
          && !dragStateRef.current
          && !lowNeedActiveRef.current
          && animationRef.current === "idle"
        ) {
          // 这是“它自己露一点状态”的轻动作，不写入头顶气泡，也不改数值。
          playAnimation(nextAnimation);
        }

        scheduleAmbientBehavior();
      }, resolveAmbientBehaviorDelayMs(preferencesRef.current.proactiveLevel));
    }

    scheduleAmbientBehavior();
    return () => {
      stopped = true;
      if (ambientBehaviorTimerRef.current !== null) {
        window.clearTimeout(ambientBehaviorTimerRef.current);
        ambientBehaviorTimerRef.current = null;
      }
    };
  }, [
    behavior.motive,
    chatOpen,
    chatPending,
    isDragging,
    lowNeedActive,
    mode,
    options.movementPaused,
    options.preferences.proactiveLevel,
  ]);

  useEffect(() => {
    if (isDragging || !canReturnToBaseAnimation(animation)) {
      return;
    }

    const nextBaseAnimation = resolveBaseAnimation(mode, lowNeedActive);
    if (animation === nextBaseAnimation) {
      return;
    }

    if (animation === "walk" && nextBaseAnimation === "idle") {
      // 正常走路由移动计时器结束；这里强行回 idle 会在 idle/walk 之间反复震荡。
      return;
    }

    if (animation === "walk") {
      // 走路是移动层，回基础姿态前先钉住当前屏幕位置，避免低状态/睡眠切换时瞬移。
      stopWalkingAtCurrentPosition();
    }

    // 基础姿态只有一个出口：awake+正常 -> idle，awake+低状态 -> sad，sleeping -> sleep。
    setFrameIndex(0);
    setAnimation(nextBaseAnimation);
  }, [animation, isDragging, lowNeedActive, mode]);

  useEffect(() => {
    if (mode !== "awake" || isDragging) {
      return;
    }

    // 中文注释：这里和状态栏保持同一套阈值，看到“困到发软”时狐狸就会主动睡下。
    if (stats.energy <= AUTO_SLEEP_THRESHOLD) {
      speak("困到不行了");
      startSleeping();
      return;
    }

    if (!lowNeedActive) {
      return;
    }

    if (!canReturnToBaseAnimation(animation)) {
      return;
    }

    const now = Date.now();
    if (now - lastLowStatReactionAtRef.current < LOW_STAT_REACTION_INTERVALS[preferencesRef.current.proactiveLevel]) {
      return;
    }

    // 低状态只偶尔露一次需求，避免数值低时每轮待机都刷屏。
    lastLowStatReactionAtRef.current = now;
    if (stats.hunger <= LOW_STAT_ENTER_THRESHOLD && stats.thirst <= LOW_STAT_ENTER_THRESHOLD) {
      speak("又饿又渴");
    } else if (stats.hunger <= LOW_STAT_ENTER_THRESHOLD) {
      speak("有点饿了");
    } else if (stats.thirst <= LOW_STAT_ENTER_THRESHOLD) {
      speak("想喝水");
    } else {
      speak("想被夸一下");
    }
  }, [animation, isDragging, lowNeedActive, mode, options.movementPaused, stats.energy, stats.hunger, stats.mood, stats.thirst]);

  function startSleeping() {
    if (modeRef.current === "sleeping") {
      setAnimation("sleep");
      setFrameIndex(0);
      return;
    }

    stopWalkingAtCurrentPosition();
    clearWanderTimer();
    awakeTickCountRef.current = 0;
    sleepTickCountRef.current = 0;
    setMode("sleeping");
    setLowNeedActive(false);
    // 入睡只切换状态，恢复由睡眠定时器持续推进，不做一次性补血。
    setAnimation(resolveBaseAnimation("sleeping", false));
    setFrameIndex(0);
  }

  function stopSleeping() {
    clearWanderTimer();
    setMoveDurationMs(0);
    awakeTickCountRef.current = 0;
    sleepTickCountRef.current = 0;
    const nextLowNeedActive = shouldEnterLowNeedPose(statsRef.current);
    setMode("awake");
    setLowNeedActive(nextLowNeedActive);
    // 月亮按钮再次点击就是“叫醒”，直接回到安静待机，不额外播放开心/惊讶动作。
    setAnimation(resolveBaseAnimation("awake", nextLowNeedActive));
    setFrameIndex(0);
  }

  function toggleRest() {
    if (modeRef.current === "sleeping") {
      speak("醒啦");
      stopSleeping();
      return;
    }

    speak("我睡会儿");
    startSleeping();
  }

  function handlePetClick(options: { playReaction?: boolean } = {}) {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return false;
    }

    if (options.playReaction === false) {
      // 点狐狸只打开操作入口，不再同时冒头顶文字。
      return true;
    }

    if (!canReturnToBaseAnimation(animationRef.current)) {
      // 中文注释：点击反应属于一次性动作，播完前不接受新的点击打断，避免刚点一下就被后续点击截断。
      return false;
    }

    speak("嗯？");
    playAnimation("click", { mood: 2 });
    return true;
  }

  function completeDrag(event: PointerEvent<HTMLButtonElement>) {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }

    dragStateRef.current = null;
    setIsDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (dragState.moved) {
      suppressClickRef.current = true;
      const landedPosition = clampPosition(positionRef.current, stageSize);
      setPosition(landedPosition);
      onDragEndRef.current(landedPosition);
      // 中文注释：拖拽拖到页面外就直接收手，保留一次完整“放下”反馈，不让拖拽态挂在指针外侧。
      if (Date.now() - dragState.startedAt >= LONG_DRAG_REACTION_MS) {
        speak("有点晕");
        playAnimation("surprised", { mood: -2 });
        return;
      }

      speak("放好啦");
      playAnimation("putdown", { mood: 1 });
    }
  }

  function handlePointerDown(event: PointerEvent<HTMLButtonElement>) {
    // 中文注释：鼠标和触摸共用 Pointer Events；真正限制滚动的区域只有狐狸的小 hitbox。
    const pinnedPosition = stopWalkingAtCurrentPosition();
    if (pinnedPosition === null) {
      return;
    }

    event.currentTarget.setPointerCapture(event.pointerId);
    setMode("awake");
    dragStateRef.current = {
      // 拿起动作必须从狐狸“当前显示的位置”开始，不能用还在走路时已经写入的目标位置。
      bottom: pinnedPosition.bottom,
      left: pinnedPosition.left,
      moved: false,
      pointerId: event.pointerId,
      startedAt: Date.now(),
      startX: event.clientX,
      startY: event.clientY,
    };
    setIsDragging(true);
  }

  function handlePointerMove(event: PointerEvent<HTMLButtonElement>) {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }

    const deltaX = event.clientX - dragState.startX;
    const deltaY = event.clientY - dragState.startY;
    const moved = Math.abs(deltaX) + Math.abs(deltaY) > 8;
    if (moved && !dragState.moved) {
      dragState.moved = true;
      setAnimation("pickup");
      setFrameIndex(0);
    }

    if (dragState.moved) {
      setFacing(deltaX >= 0 ? 1 : -1);
      const nextPosition = clampPosition(
        {
          bottom: dragState.bottom - deltaY,
          left: dragState.left + deltaX,
        },
        stageSize,
      );
      positionRef.current = nextPosition;
      setPosition(nextPosition);
    }

    if (isPointerOutsideViewport(event)) {
      // 中文注释：拖拽一旦跑出浏览器可视范围，就按松手处理，避免狐狸继续挂在外面被拖着走。
      completeDrag(event);
    }
  }

  function handlePointerUp(event: PointerEvent<HTMLButtonElement>) {
    completeDrag(event);
  }

  return {
    animation,
    actions: {
      drink: () => {
        speak("咕噜咕噜");
        playAnimation("drink", { energy: 3, mood: 2, thirst: 30 });
      },
      feed: () => {
        speak("好吃");
        playAnimation("eat", { hunger: 24, mood: 4 });
      },
      praise: () => {
        speak("嘿嘿");
        playAnimation("praise", { mood: 18 });
      },
      rest: toggleRest,
    },
    chat: {
      close: closeChat,
      error: chatError,
      messages: chatMessages,
      open: openChat,
      opened: chatOpen,
      pending: chatPending,
      submit: submitChatMessage,
    },
    behavior,
    facing,
    framePath,
    handlers: {
      click: handlePetClick,
      pointerCancel: handlePointerUp,
      pointerDown: handlePointerDown,
      pointerMove: handlePointerMove,
      pointerUp: handlePointerUp,
    },
    isDragging,
    isReady: petStateReady,
    lowNeedActive,
    sleepEffectVisible: animation === "sleep",
    isSleeping: mode === "sleeping",
    isWalking: animation === "walk" && !isDragging,
    position,
    stats,
    visualCenterX: activeAnchor.uiCenterX,
    visualFootOffset: activeAnchor.footOffset,
    visualScale: resolvePetFrameScale(animation, activeFrameIndex),
    visualTopOffset: activeAnchor.uiTop,
    moveDurationMs,
  };
}
