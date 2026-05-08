import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { PetOverlay } from "./PetOverlay";
import type { PetCompanionContext } from "../api/petChat";
import { PET_ANIMATIONS, PET_MAX_FOOT_OFFSET } from "../model/petSprites";
import type { PetPreferences } from "../model/usePetPreferences";
import type { PetSignal } from "../model/petSignals";

type PetAnchorName = "composerTop" | "homeCorner" | "messageArea" | "sidebarEdge" | "topBar";

type PetPosition = {
  bottom: number;
  left: number;
};

type AnchorPoint = {
  name: PetAnchorName;
  position: PetPosition;
};

type CaretClientPosition = {
  left: number;
  top: number;
};

type PetLayerProps = {
  activitySignal?: PetSignal | null;
  activeSection: string;
  context: PetCompanionContext;
  draftActive: boolean;
  isStreaming: boolean;
  preferences: PetPreferences;
  sidebarOpen: boolean;
};

const PET_SIZE = 144;
const PET_DEFAULT_FOOT_OFFSET = PET_ANIMATIONS.idle.anchor.footOffset;
const PAGE_EDGE_PADDING = 12;
const PET_MIN_BOTTOM = PET_DEFAULT_FOOT_OFFSET + PAGE_EDGE_PADDING;
const PET_HOME_RIGHT = 96;
const PET_HOME_BOTTOM = 86;
const PET_COMPOSER_SIDE_PADDING = 18;
const PET_COMPOSER_MIN_RETURN_X = 72;
const RANDOM_WALK_MIN_DELAY_MS = 9000;
const RANDOM_WALK_MAX_DELAY_MS = 22000;
const RANDOM_WALK_MIN_DISTANCE = 64;
const RANDOM_WALK_MAX_DISTANCE = 260;
const COMPOSER_CARET_TARGET_DELAY_MS = 420;
const COMPOSER_CARET_TARGET_MIN_SHIFT = 48;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function randomBetween(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function resolveRandomWalkDelayMs() {
  return Math.round(randomBetween(RANDOM_WALK_MIN_DELAY_MS, RANDOM_WALK_MAX_DELAY_MS));
}

function resolveStageLeftBoundary() {
  const sidebarElement = document.querySelector('[data-pet-anchor="sidebarEdge"]');
  if (!sidebarElement) {
    return PAGE_EDGE_PADDING;
  }

  const rect = sidebarElement.getBoundingClientRect();
  // 桌面侧边栏就是宠物的左侧“墙”，宠物盒子要整体站在墙右侧。
  return rect.right > PAGE_EDGE_PADDING ? rect.right + PAGE_EDGE_PADDING : PAGE_EDGE_PADDING;
}

function clampPetPosition(position: PetPosition): PetPosition {
  const minLeft = resolveStageLeftBoundary();
  const maxLeft = Math.max(minLeft, window.innerWidth - PET_SIZE - PAGE_EDGE_PADDING);
  const maxBottom = Math.max(
    PET_DEFAULT_FOOT_OFFSET + PAGE_EDGE_PADDING,
    window.innerHeight + PET_MAX_FOOT_OFFSET - PET_SIZE - PAGE_EDGE_PADDING,
  );

  return {
    bottom: clamp(position.bottom, PET_DEFAULT_FOOT_OFFSET + PAGE_EDGE_PADDING, maxBottom),
    left: clamp(position.left, minLeft, maxLeft),
  };
}

function resolveWalkingBottom() {
  const composerElement = document.querySelector('[data-pet-anchor="composerTop"]');
  if (composerElement) {
    const rect = composerElement.getBoundingClientRect();
    // 中文注释：狐狸脚点贴住输入框上沿，看起来像站在对话框边上。
    return clampPetPosition({
      bottom: window.innerHeight - rect.top,
      left: PAGE_EDGE_PADDING,
    }).bottom;
  }

  return PET_HOME_BOTTOM;
}

function createAnchor(name: PetAnchorName, position: PetPosition): AnchorPoint {
  return {
    name,
    position: clampPetPosition(position),
  };
}

function readComposerCaretClientPosition(): CaretClientPosition | null {
  const textarea = document.querySelector<HTMLTextAreaElement>('[data-pet-caret-source="chat-composer"]');
  if (!textarea) {
    return null;
  }

  const computed = window.getComputedStyle(textarea);
  const rect = textarea.getBoundingClientRect();
  const caretIndex = textarea.selectionEnd ?? textarea.value.length;
  const mirror = document.createElement("div");
  const marker = document.createElement("span");

  mirror.style.position = "fixed";
  mirror.style.left = "0";
  mirror.style.top = "0";
  mirror.style.visibility = "hidden";
  mirror.style.pointerEvents = "none";
  mirror.style.whiteSpace = "pre-wrap";
  mirror.style.overflowWrap = "break-word";
  mirror.style.wordBreak = computed.wordBreak;
  mirror.style.boxSizing = "border-box";
  mirror.style.width = `${rect.width}px`;
  mirror.style.font = computed.font;
  mirror.style.letterSpacing = computed.letterSpacing;
  mirror.style.lineHeight = computed.lineHeight;
  mirror.style.padding = computed.padding;
  mirror.style.border = computed.border;
  mirror.style.tabSize = computed.tabSize;

  // 中文注释：用同样字体和宽度的隐藏镜像，把 textarea caret 的屏幕坐标量出来。
  mirror.textContent = textarea.value.slice(0, caretIndex);
  marker.textContent = "\u200b";
  mirror.append(marker);
  document.body.append(mirror);

  const mirrorRect = mirror.getBoundingClientRect();
  const markerRect = marker.getBoundingClientRect();
  const position = {
    left: rect.left + markerRect.left - mirrorRect.left - textarea.scrollLeft,
    top: rect.top + markerRect.top - mirrorRect.top - textarea.scrollTop,
  };
  mirror.remove();
  return position;
}

function resolveComposerLeft(element: Element, walkingBottom: number, referencePosition: PetPosition) {
  const rect = element.getBoundingClientRect();
  const minLeft = rect.left + PET_COMPOSER_SIDE_PADDING;
  const maxLeft = Math.max(minLeft, rect.right - PET_SIZE - PET_COMPOSER_SIDE_PADDING);
  const nearestLeft = clamp(referencePosition.left, minLeft, maxLeft);
  const verticalDistance = Math.abs(walkingBottom - referencePosition.bottom);
  const horizontalDistance = Math.abs(nearestLeft - referencePosition.left);

  if (verticalDistance > 24 && horizontalDistance < 24) {
    const leftCandidate = Math.max(minLeft, nearestLeft - PET_COMPOSER_MIN_RETURN_X);
    const rightCandidate = Math.min(maxLeft, nearestLeft + PET_COMPOSER_MIN_RETURN_X);

    if (leftCandidate === nearestLeft) {
      return rightCandidate;
    }

    if (rightCandidate === nearestLeft) {
      return leftCandidate;
    }

    // 中文注释：当前位置正对输入框时，给它一个最近的横向步幅，避免看起来原地直上直下。
    return nearestLeft - minLeft < maxLeft - nearestLeft ? rightCandidate : leftCandidate;
  }

  return nearestLeft;
}

function resolveComposerCaretPosition(element: Element, walkingBottom: number): PetPosition | null {
  const rect = element.getBoundingClientRect();
  const minLeft = rect.left + PET_COMPOSER_SIDE_PADDING;
  const maxLeft = Math.max(minLeft, rect.right - PET_SIZE - PET_COMPOSER_SIDE_PADDING);
  const caretPosition = readComposerCaretClientPosition();
  if (!caretPosition) {
    return null;
  }

  return clampPetPosition({
    // 中文注释：目标是“站到当前输入位置附近”，不是每个字符都硬对齐。
    bottom: walkingBottom,
    left: clamp(caretPosition.left - PET_SIZE / 2, minLeft, maxLeft),
  });
}

function shouldCommitComposerTarget(current: PetPosition | null, next: PetPosition) {
  if (!current) {
    return true;
  }

  return Math.hypot(next.left - current.left, next.bottom - current.bottom) >= COMPOSER_CARET_TARGET_MIN_SHIFT;
}

function pointFromComposer(
  element: Element,
  walkingBottom: number,
  referencePosition: PetPosition,
): AnchorPoint {
  const left = resolveComposerLeft(element, walkingBottom, referencePosition);

  return createAnchor(
    "composerTop",
    {
      // 中文注释：普通回框按最近站位走；输入中会由延迟后的 caret 目标接管。
      bottom: walkingBottom,
      left,
    },
  );
}

function pointFromElement(name: PetAnchorName, element: Element, walkingBottom: number): AnchorPoint {
  const rect = element.getBoundingClientRect();

  if (name === "sidebarEdge") {
    return createAnchor(
      name,
      {
        bottom: walkingBottom,
        // 侧边栏边缘不是站位中心，狐狸要完整落在内容区这一侧。
        left: rect.right + PAGE_EDGE_PADDING,
      },
    );
  }

  if (name === "topBar") {
    return createAnchor(
      name,
      {
        bottom: walkingBottom,
        left: rect.left + 120,
      },
    );
  }

  return createAnchor(
    name,
    {
      bottom: walkingBottom,
      left: rect.left + Math.max(24, rect.width * 0.12),
    },
  );
}

function homeAnchor(walkingBottom: number): AnchorPoint {
  return createAnchor(
    "homeCorner",
    {
      bottom: walkingBottom,
      left: window.innerWidth - PET_SIZE - PET_HOME_RIGHT,
    },
  );
}

function createRandomWalkPosition(origin: PetPosition, walkingBottom: number): PetPosition {
  const minLeft = resolveStageLeftBoundary();
  const maxLeft = Math.max(minLeft, window.innerWidth - PET_SIZE - PAGE_EDGE_PADDING);
  const leftRoom = origin.left - minLeft;
  const rightRoom = maxLeft - origin.left;
  const canWalkLeft = leftRoom >= RANDOM_WALK_MIN_DISTANCE;
  const canWalkRight = rightRoom >= RANDOM_WALK_MIN_DISTANCE;

  if (!canWalkLeft && !canWalkRight) {
    // 空间过窄时只在安全范围内重新落点，保证不会撞到边界。
    return clampPetPosition({
      bottom: walkingBottom,
      left: randomBetween(minLeft, maxLeft),
    });
  }

  const direction = canWalkLeft && canWalkRight
    ? Math.random() < 0.5 ? -1 : 1
    : canWalkLeft ? -1 : 1;
  const room = direction === -1 ? leftRoom : rightRoom;
  const maxDistance = Math.min(RANDOM_WALK_MAX_DISTANCE, room);
  const minDistance = Math.min(RANDOM_WALK_MIN_DISTANCE, maxDistance);

  return clampPetPosition({
    bottom: walkingBottom,
    left: origin.left + direction * randomBetween(minDistance, maxDistance),
  });
}

function createGlobalWalkPosition(origin: PetPosition): PetPosition {
  const horizontalMin = origin.left < window.innerWidth / 2
    ? window.innerWidth / 2
    : PAGE_EDGE_PADDING;
  const horizontalMax = origin.left < window.innerWidth / 2
    ? window.innerWidth - PET_SIZE - PAGE_EDGE_PADDING
    : Math.max(PAGE_EDGE_PADDING, window.innerWidth / 2 - PET_SIZE);
  const verticalMin = origin.bottom < window.innerHeight / 2
    ? window.innerHeight / 2
    : PET_MIN_BOTTOM;
  const verticalMax = origin.bottom < window.innerHeight / 2
    ? window.innerHeight - PET_SIZE - PAGE_EDGE_PADDING
    : Math.max(PET_MIN_BOTTOM, window.innerHeight / 2);

  return clampPetPosition({
    // 中文注释：全局走动直接选屏幕另一片区域，不沿用输入框脚线，也不围着旧锚点打转。
    bottom: randomBetween(Math.min(verticalMin, verticalMax), Math.max(verticalMin, verticalMax)),
    left: randomBetween(Math.min(horizontalMin, horizontalMax), Math.max(horizontalMin, horizontalMax)),
  });
}

function staticHomePosition(): AnchorPoint {
  return {
    name: "homeCorner",
    position: {
      bottom: PET_HOME_BOTTOM,
      left: PAGE_EDGE_PADDING,
    },
  };
}

function collectAnchors(referencePosition: PetPosition) {
  const anchors = new Map<PetAnchorName, AnchorPoint>();
  const walkingBottom = resolveWalkingBottom();
  anchors.set("homeCorner", homeAnchor(walkingBottom));

  for (const name of ["composerTop", "sidebarEdge", "topBar"] as PetAnchorName[]) {
    const element = document.querySelector(`[data-pet-anchor="${name}"]`);
    if (element) {
      anchors.set(
        name,
        name === "composerTop"
          ? pointFromComposer(element, walkingBottom, referencePosition)
          : pointFromElement(name, element, walkingBottom),
      );
    }
  }

  return anchors;
}

function distance(left: PetPosition, right: PetPosition) {
  return Math.hypot(left.left - right.left, left.bottom - right.bottom);
}

function pickNearestAnchor(position: PetPosition, anchors: Map<PetAnchorName, AnchorPoint>) {
  return Array.from(anchors.values()).reduce((nearest, anchor) =>
    distance(anchor.position, position) < distance(nearest.position, position) ? anchor : nearest,
  );
}

export function PetLayer({
  activitySignal,
  activeSection,
  context,
  draftActive,
  isStreaming,
  preferences,
  sidebarOpen,
}: PetLayerProps) {
  const [anchors, setAnchors] = useState(() =>
    typeof window === "undefined"
      ? new Map<PetAnchorName, AnchorPoint>()
      : collectAnchors(staticHomePosition().position),
  );
  const [selectedAnchor, setSelectedAnchor] = useState<PetAnchorName>(() =>
    typeof window !== "undefined" && document.querySelector('[data-pet-anchor="composerTop"]')
      ? "composerTop"
      : "homeCorner",
  );
  const [activityHoldTarget, setActivityHoldTarget] = useState<PetPosition | null>(null);
  const [composerDraftTarget, setComposerDraftTarget] = useState<PetPosition | null>(null);
  const [randomTarget, setRandomTarget] = useState<PetPosition | null>(null);
  const activityHoldSignalIdRef = useRef<number | null>(null);
  const activityHoldReleaseTimerRef = useRef<number | null>(null);
  const composerCaretTimerRef = useRef<number | null>(null);
  const previousDraftActiveRef = useRef(draftActive);
  const randomWalkTimerRef = useRef<number | null>(null);
  const petPositionRef = useRef<PetPosition>(staticHomePosition().position);

  const refreshAnchors = useCallback(() => {
    setAnchors(collectAnchors(petPositionRef.current));
  }, []);

  useEffect(() => {
    refreshAnchors();
    const frame = window.requestAnimationFrame(refreshAnchors);
    window.addEventListener("resize", refreshAnchors);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("resize", refreshAnchors);
    };
  }, [activeSection, refreshAnchors, sidebarOpen]);

  useEffect(() => {
    // 中文注释：切换走动模式时先清掉旧模式留下的随机目标，再交给新模式重新选锚点。
    setRandomTarget(null);
    if (randomWalkTimerRef.current !== null) {
      window.clearTimeout(randomWalkTimerRef.current);
      randomWalkTimerRef.current = null;
    }
  }, [preferences.walkMode]);

  useEffect(() => {
    const textarea = document.querySelector<HTMLTextAreaElement>('[data-pet-caret-source="chat-composer"]');
    if (!draftActive) {
      if (composerCaretTimerRef.current !== null) {
        window.clearTimeout(composerCaretTimerRef.current);
        composerCaretTimerRef.current = null;
      }

      setComposerDraftTarget(null);
      return;
    }

    if (!textarea) {
      return;
    }

    const commitComposerTarget = () => {
      const composerElement = document.querySelector('[data-pet-anchor="composerTop"]');
      if (!composerElement) {
        return;
      }

      const nextTarget = resolveComposerCaretPosition(composerElement, resolveWalkingBottom());
      if (!nextTarget) {
        return;
      }

      setComposerDraftTarget((current) => {
        if (!shouldCommitComposerTarget(current, nextTarget)) {
          return current;
        }

        return nextTarget;
      });
      refreshAnchors();
    };

    const scheduleComposerTarget = () => {
      if (composerCaretTimerRef.current !== null) {
        window.clearTimeout(composerCaretTimerRef.current);
      }

      // 中文注释：输入先沉淀一小会儿，再让狐狸把新位置当目的地慢慢走过去。
      composerCaretTimerRef.current = window.setTimeout(() => {
        composerCaretTimerRef.current = null;
        commitComposerTarget();
      }, COMPOSER_CARET_TARGET_DELAY_MS);
    };

    const events = ["click", "compositionupdate", "focus", "input", "keyup", "scroll", "select"] as const;
    events.forEach((eventName) => textarea.addEventListener(eventName, scheduleComposerTarget));
    scheduleComposerTarget();

    return () => {
      if (composerCaretTimerRef.current !== null) {
        window.clearTimeout(composerCaretTimerRef.current);
        composerCaretTimerRef.current = null;
      }
      events.forEach((eventName) => textarea.removeEventListener(eventName, scheduleComposerTarget));
    };
  }, [activeSection, draftActive, refreshAnchors]);

  useEffect(() => {
    const signal = activitySignal;
    if (!signal || activityHoldSignalIdRef.current === signal.id) {
      return;
    }

    activityHoldSignalIdRef.current = signal.id;
    if (signal.type === "send") {
      setRandomTarget(null);
      // 中文注释：主聊天事件优先锁当前位置，避免全局/固定/普通模式先吸回锚点再做动作。
      setActivityHoldTarget(clampPetPosition(petPositionRef.current));
    }
  }, [activitySignal]);

  useEffect(() => {
    const draftBecameActive = draftActive && !previousDraftActiveRef.current;
    previousDraftActiveRef.current = draftActive;
    if (!draftBecameActive || activityHoldTarget === null) {
      return;
    }

    if (activityHoldReleaseTimerRef.current !== null) {
      window.clearTimeout(activityHoldReleaseTimerRef.current);
      activityHoldReleaseTimerRef.current = null;
    }

    // 中文注释：动作还没结束时开始写新草稿，输入位置要接管目的地，不能继续被发送动作的原地锁压住。
    setActivityHoldTarget(null);
  }, [activityHoldTarget, draftActive]);

  useEffect(() => {
    if (activityHoldReleaseTimerRef.current !== null) {
      window.clearTimeout(activityHoldReleaseTimerRef.current);
      activityHoldReleaseTimerRef.current = null;
    }

    if (activityHoldTarget === null || draftActive || isStreaming) {
      return;
    }

    activityHoldReleaseTimerRef.current = window.setTimeout(() => {
      activityHoldReleaseTimerRef.current = null;
      setActivityHoldTarget(null);
    }, 1400);

    return () => {
      if (activityHoldReleaseTimerRef.current !== null) {
        window.clearTimeout(activityHoldReleaseTimerRef.current);
        activityHoldReleaseTimerRef.current = null;
      }
    };
  }, [activityHoldTarget, draftActive, isStreaming]);

  useEffect(() => {
    if (activityHoldTarget !== null) {
      return;
    }

    if (draftActive && anchors.has("composerTop")) {
      setRandomTarget(null);
      setSelectedAnchor("composerTop");
      return;
    }

    if (preferences.walkMode === "off") {
      setRandomTarget(null);
      setSelectedAnchor("homeCorner");
      return;
    }

    if (isStreaming) {
      setRandomTarget(null);
      // 中文注释：写作和流式回复期间，安全角落优先级最高，避免狐狸贴着输入框触发动作。
      setSelectedAnchor("homeCorner");
      return;
    }

    if (preferences.walkMode === "global") {
      setSelectedAnchor("homeCorner");
      // 中文注释：刚切到全局时立刻给一个全屏目标，别等计时器，也别继承 composerTop 旧锚点。
      setRandomTarget((current) => current ?? createGlobalWalkPosition(petPositionRef.current));
      return;
    }

    if (activeSection === "chats" && anchors.has("composerTop")) {
      setRandomTarget(null);
      setSelectedAnchor("composerTop");
      return;
    }
  }, [activeSection, activityHoldTarget, anchors, draftActive, isStreaming, preferences.walkMode]);

  const targetPosition = useMemo(() => {
    if (activityHoldTarget) {
      return clampPetPosition(activityHoldTarget);
    }

    if (preferences.walkMode === "off") {
      // 中文注释：不走动模式是真正固定在当前位置，不再被 composer/homeCorner 锚点拉走。
      return clampPetPosition(petPositionRef.current);
    }

    if (draftActive) {
      return composerDraftTarget ? clampPetPosition(composerDraftTarget) : clampPetPosition(petPositionRef.current);
    }

    if (randomTarget) {
      return clampPetPosition(randomTarget);
    }

    if (preferences.walkMode === "global" && !draftActive && !isStreaming) {
      // 中文注释：全局模式没有随机目标时保持当前位置，禁止回落到对话框锚点。
      return clampPetPosition(petPositionRef.current);
    }

    if (selectedAnchor === "composerTop") {
      const composerElement = document.querySelector('[data-pet-anchor="composerTop"]');
      if (composerElement) {
        return pointFromComposer(
          composerElement,
          resolveWalkingBottom(),
          petPositionRef.current,
        ).position;
      }
    }

    return anchors.get(selectedAnchor)?.position ?? anchors.get("homeCorner")?.position ?? staticHomePosition().position;
  }, [
    activityHoldTarget,
    anchors,
    composerDraftTarget,
    draftActive,
    isStreaming,
    preferences.walkMode,
    randomTarget,
    selectedAnchor,
  ]);

  useEffect(() => {
    // 无输入和无回复时才让狐狸自由走动，写作/流式回复会把它拉回锚点。
    if (
      preferences.walkMode === "off"
      || (activeSection === "chats" && preferences.walkMode === "normal")
    ) {
      setRandomTarget(null);
      return;
    }

    if (activityHoldTarget !== null || draftActive || isStreaming) {
      return;
    }

    function scheduleRandomWalk() {
      randomWalkTimerRef.current = window.setTimeout(() => {
        setRandomTarget(
          preferences.walkMode === "global"
            ? createGlobalWalkPosition(petPositionRef.current)
            : createRandomWalkPosition(petPositionRef.current, resolveWalkingBottom()),
        );
        scheduleRandomWalk();
      }, resolveRandomWalkDelayMs());
    }

    scheduleRandomWalk();
    return () => {
      if (randomWalkTimerRef.current !== null) {
        window.clearTimeout(randomWalkTimerRef.current);
        randomWalkTimerRef.current = null;
      }
    };
  }, [activeSection, activityHoldTarget, draftActive, isStreaming, preferences.walkMode, sidebarOpen]);

  const handleDragEnd = useCallback((position: PetPosition) => {
    petPositionRef.current = position;
    const nextAnchors = collectAnchors(position);
    setRandomTarget(clampPetPosition(position));
    setAnchors(nextAnchors);
    setSelectedAnchor(preferences.walkMode === "global" ? "homeCorner" : pickNearestAnchor(position, nextAnchors).name);
  }, [preferences.walkMode]);

  const handlePositionChange = useCallback((position: PetPosition) => {
    petPositionRef.current = position;
  }, []);

  return (
      <PetOverlay
        activitySignal={activitySignal}
        context={context}
        onPositionChange={handlePositionChange}
        onDragEnd={handleDragEnd}
        preferences={preferences}
        targetPosition={targetPosition}
      />
  );
}
