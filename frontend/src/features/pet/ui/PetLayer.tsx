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
const PET_HOME_RIGHT = 34;
const PET_HOME_BOTTOM = 86;
// 狐狸自己散步时，每次间隔和距离都随机，避免看起来像固定巡逻。
const RANDOM_WALK_MIN_DELAY_MS = 9000;
const RANDOM_WALK_MAX_DELAY_MS = 22000;
const RANDOM_WALK_MIN_DISTANCE = 64;
const RANDOM_WALK_MAX_DISTANCE = 260;

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
  if (!composerElement) {
    return PET_HOME_BOTTOM;
  }

  const rect = composerElement.getBoundingClientRect();
  // 非拖拽巡逻只改变横向位置：狐狸始终踩在同一条输入框上沿/地面线上，不再忽上忽下。
  return clampPetPosition({
    bottom: window.innerHeight - rect.top,
    left: PAGE_EDGE_PADDING,
  }).bottom;
}

function createAnchor(name: PetAnchorName, position: PetPosition): AnchorPoint {
  return {
    name,
    position: clampPetPosition(position),
  };
}

function pointFromElement(name: PetAnchorName, element: Element, walkingBottom: number): AnchorPoint {
  const rect = element.getBoundingClientRect();

  if (name === "composerTop") {
    return createAnchor(
      name,
      {
        // 站在输入框上沿，靠右一点像在看用户输入。
        bottom: walkingBottom,
        left: rect.right - PET_SIZE - 18,
      },
    );
  }

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

function staticHomePosition(): AnchorPoint {
  return {
    name: "homeCorner",
    position: {
      bottom: PET_HOME_BOTTOM,
      left: PAGE_EDGE_PADDING,
    },
  };
}

function collectAnchors() {
  const anchors = new Map<PetAnchorName, AnchorPoint>();
  const walkingBottom = resolveWalkingBottom();
  anchors.set("homeCorner", homeAnchor(walkingBottom));

  for (const name of ["composerTop", "messageArea", "sidebarEdge", "topBar"] as PetAnchorName[]) {
    const element = document.querySelector(`[data-pet-anchor="${name}"]`);
    if (element) {
      anchors.set(name, pointFromElement(name, element, walkingBottom));
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
    typeof window === "undefined" ? new Map<PetAnchorName, AnchorPoint>() : collectAnchors(),
  );
  const [selectedAnchor, setSelectedAnchor] = useState<PetAnchorName>(() =>
    typeof window !== "undefined" && document.querySelector('[data-pet-anchor="composerTop"]')
      ? "composerTop"
      : "homeCorner",
  );
  const [randomTarget, setRandomTarget] = useState<PetPosition | null>(null);
  const randomWalkTimerRef = useRef<number | null>(null);
  const targetPositionRef = useRef<PetPosition>(staticHomePosition().position);

  const refreshAnchors = useCallback(() => {
    setAnchors(collectAnchors());
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
    if (draftActive && anchors.has("composerTop")) {
      setRandomTarget(null);
      setSelectedAnchor("composerTop");
      return;
    }

    if (isStreaming && anchors.has("messageArea")) {
      setRandomTarget(null);
      setSelectedAnchor("messageArea");
      return;
    }
  }, [anchors, draftActive, isStreaming]);

  const targetPosition = useMemo(() => {
    if (randomTarget) {
      return clampPetPosition(randomTarget);
    }

    return anchors.get(selectedAnchor)?.position ?? anchors.get("homeCorner")?.position ?? staticHomePosition().position;
  }, [anchors, randomTarget, selectedAnchor]);

  useEffect(() => {
    targetPositionRef.current = targetPosition;
  }, [targetPosition]);

  useEffect(() => {
    // 无输入和无回复时才让狐狸自由走动，写作/流式回复会把它拉回锚点。
    if (!preferences.autoWalk) {
      setRandomTarget(null);
      return;
    }

    if (draftActive || isStreaming) {
      return;
    }

    function scheduleRandomWalk() {
      randomWalkTimerRef.current = window.setTimeout(() => {
        setRandomTarget(createRandomWalkPosition(targetPositionRef.current, resolveWalkingBottom()));
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
  }, [activeSection, draftActive, isStreaming, preferences.autoWalk, sidebarOpen]);

  const handleDragEnd = useCallback((position: PetPosition) => {
    const nextAnchors = collectAnchors();
    setRandomTarget(clampPetPosition(position));
    setAnchors(nextAnchors);
    setSelectedAnchor(pickNearestAnchor(position, nextAnchors).name);
  }, []);

  return (
      <PetOverlay
        activitySignal={activitySignal}
        context={context}
        onDragEnd={handleDragEnd}
        preferences={preferences}
        targetPosition={targetPosition}
      />
  );
}
