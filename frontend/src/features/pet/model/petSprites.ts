export type PetAnimationKey =
  | "click"
  | "angry"
  | "drink"
  | "eat"
  | "emotion"
  | "happy"
  | "hurt"
  | "idle"
  | "pickup"
  | "pickupHold"
  | "praise"
  | "putdown"
  | "sad"
  | "sleep"
  | "surprised"
  | "walk";

export type PetAnimationPhase = "action" | "locomotion" | "pose";

export interface PetVisualAnchor {
  footOffset: number;
  uiCenterX: number;
  uiTop: number;
}

export interface PetAnimationDefinition {
  anchor: PetVisualAnchor;
  frameCenterXs?: number[];
  frameFootOffsets?: number[];
  frameScales?: number[];
  frameMs: number;
  frames: string[];
  phase: PetAnimationPhase;
  playMode: "hold" | "loop" | "once";
  visualScale?: number;
}

const PET_FRAME_URLS = import.meta.glob("../assets/fox/frames/**/*.png", {
  eager: true,
  import: "default",
  query: "?url",
}) as Record<string, string>;

type PetFrameFolderKey = PetAnimationKey;

function getFrameUrl(animation: PetFrameFolderKey, index: number) {
  const frameName = `${animation}-${String(index).padStart(2, "0")}.png`;
  const frameKey = `../assets/fox/frames/${animation}/${frameName}`;
  const frameUrl = PET_FRAME_URLS[frameKey];

  if (!frameUrl) {
    throw new Error(`Missing pet frame: ${frameKey}`);
  }

  return frameUrl;
}

function createFramePaths(animation: PetFrameFolderKey, frameCount: number) {
  return Array.from(
    { length: frameCount },
    (_, index) => getFrameUrl(animation, index + 1),
  );
}

function createPingPongFramePaths(animation: PetFrameFolderKey, frameCount: number) {
  const forwardFrames = createFramePaths(animation, frameCount);
  if (forwardFrames.length <= 2) {
    return forwardFrames;
  }

  return [...forwardFrames, ...forwardFrames.slice(1, -1).reverse()];
}

function createSelectedFramePaths(animation: PetFrameFolderKey, frameIndexes: number[]) {
  return frameIndexes.map((index) => getFrameUrl(animation, index));
}

// 这些锚点来自 256px PNG 透明边界换算到 144px 渲染盒后的坐标。
// 后续新增动画时，先补锚点，再接行为逻辑，避免靠 CSS 偏移一处处修。
export const PET_UI_CENTER_X = 72;
const STANDING_ANCHOR: PetVisualAnchor = { footOffset: 13, uiCenterX: PET_UI_CENTER_X, uiTop: 64 };
const SLEEP_ANCHOR: PetVisualAnchor = { footOffset: 13, uiCenterX: PET_UI_CENTER_X, uiTop: 76 };
const FIXED_BODY_CENTER_XS = [PET_UI_CENTER_X];

export const PET_ANIMATIONS = {
  // 中文注释：新 raw 动作帧的可见像素高度不一致；visualScale 只放大画面，不改脚底锚点。
  // 中文注释：frameCenterXs / frameFootOffsets 就是逐帧注册点；业界常见做法是让身体按同一参考点对齐，而不是跟整张图的外轮廓跑。
  angry: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: FIXED_BODY_CENTER_XS,
    frameFootOffsets: [12, 13, 13, 13],
    frameMs: 160,
    frames: createSelectedFramePaths("angry", [1, 2, 3, 4]),
    phase: "action",
    playMode: "once",
    visualScale: 1.18,
  },
  // 中文注释：click 现在只保留新 raw 里头身比例更稳的 5 帧。
  click: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: [72, 72, 73, 72, 72],
    frameFootOffsets: [13, 14, 14, 13, 13],
    frameMs: 140,
    frames: createSelectedFramePaths("click", [1, 2, 3, 4, 5]),
    phase: "action",
    playMode: "once",
    visualScale: 1.12,
  },
  // 中文注释：喝水第 2 帧本体会缩一点，第 3 帧又稍微放开；按帧补比例，避免观感上一会大一会小。
  drink: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: [72, 71, 72],
    frameFootOffsets: [13, 12, 12],
    frameScales: [1, 1.045, 0.992],
    frameMs: 220,
    frames: createSelectedFramePaths("drink", [1, 2, 3]),
    phase: "action",
    playMode: "once",
    visualScale: 1.18,
  },
  eat: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: [71, 72, 72, 72, 71],
    frameFootOffsets: [13, 12, 12, 13, 14],
    frameMs: 220,
    frames: createSelectedFramePaths("eat", [1, 2, 3, 4, 5]),
    phase: "action",
    playMode: "once",
    visualScale: 1.18,
  },
  emotion: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: FIXED_BODY_CENTER_XS,
    frameFootOffsets: [12, 14, 13, 13],
    frameMs: 170,
    frames: createPingPongFramePaths("emotion", 4),
    phase: "action",
    playMode: "once",
    visualScale: 1.12,
  },
  happy: { anchor: STANDING_ANCHOR, frameCenterXs: FIXED_BODY_CENTER_XS, frameMs: 130, frames: createSelectedFramePaths("happy", [1]), phase: "action", playMode: "once", visualScale: 1.12 },
  hurt: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: FIXED_BODY_CENTER_XS,
    frameFootOffsets: [12, 12, 13, 13, 13, 13],
    frameMs: 200,
    frames: createSelectedFramePaths("hurt", [1, 2, 3, 4, 5, 6]),
    phase: "action",
    playMode: "once",
    visualScale: 1.06,
  },
  // idle 这组素材每帧都很接近，待机先留成稳定单帧，避免站姿自己抖来抖去。
  idle: { anchor: STANDING_ANCHOR, frameMs: 240, frames: createSelectedFramePaths("idle", [1]), phase: "pose", playMode: "hold" },
  // 中文注释：被拎起的素材可见高度略小，单独放大一点，拖拽坐标仍然按脚底锚点计算。
  pickup: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: [71, 72, 72, 72],
    frameFootOffsets: [13, 12, 14, 13],
    frameMs: 120,
    frames: createSelectedFramePaths("pickup", [1, 2, 3, 4]),
    phase: "action",
    playMode: "once",
    visualScale: 1.25,
  },
  pickupHold: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: FIXED_BODY_CENTER_XS,
    frameFootOffsets: [14, 13, 14, 13],
    frameMs: 180,
    frames: createSelectedFramePaths("pickup", [3, 4, 3, 4]),
    phase: "action",
    playMode: "loop",
    visualScale: 1.25,
  },
  // 中文注释：夸奖帧旁边会冒爱心，主体其实没偏；注册点固定，避免爱心出现时把狐狸推着横跳。
  praise: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: FIXED_BODY_CENTER_XS,
    frameFootOffsets: [13, 13, 13, 14, 13, 13],
    frameMs: 160,
    frames: createPingPongFramePaths("praise", 4),
    phase: "action",
    playMode: "once",
    visualScale: 1.08,
  },
  // 中文注释：putdown-04 是从 raw 第 7 格导出的抬头桥接帧，用来缓冲低趴到站姿的跳变。
  putdown: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: [72, 72, 73, 72],
    frameFootOffsets: [13, 12, 12, 14],
    frameMs: 135,
    frames: createSelectedFramePaths("putdown", [1, 2, 3, 4]),
    phase: "action",
    playMode: "once",
    visualScale: 1.25,
  },
  // 中文注释：低状态固定为一帧流泪姿态，不做循环，避免委屈态自己抖动。
  sad: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: FIXED_BODY_CENTER_XS,
    frameFootOffsets: [13],
    frameMs: 280,
    frames: createSelectedFramePaths("sad", [1]),
    phase: "pose",
    playMode: "hold",
    visualScale: 1.12,
  },
  // 中文注释：睡觉是趴姿，原图高度天然更矮；这里补足横向趴着时的体量感。
  // 中文注释：sleep-05/06 会把头和耳朵抬到旧 zzz 区域，循环时像突然上窜；睡眠循环只取稳定趴姿帧。
  sleep: { anchor: SLEEP_ANCHOR, frameCenterXs: FIXED_BODY_CENTER_XS, frameMs: 460, frames: createSelectedFramePaths("sleep", [1, 2, 3, 4, 3, 2]), phase: "pose", playMode: "loop", visualScale: 1.25 },
  surprised: {
    anchor: STANDING_ANCHOR,
    frameCenterXs: FIXED_BODY_CENTER_XS,
    frameFootOffsets: [13, 13, 12, 13],
    frameMs: 150,
    frames: createPingPongFramePaths("surprised", 4),
    phase: "action",
    playMode: "once",
    visualScale: 1.1,
  },
  // 走路用完整的 7 帧，配合位移动画一起跑，节奏更像真的在挪步。
  walk: { anchor: STANDING_ANCHOR, frameMs: 90, frames: createPingPongFramePaths("walk", 7), phase: "locomotion", playMode: "loop" },
} satisfies Record<PetAnimationKey, PetAnimationDefinition>;

export function resolvePetFrameCenterX(animation: PetAnimationKey, frameIndex: number) {
  const definition: PetAnimationDefinition = PET_ANIMATIONS[animation];
  return definition.frameCenterXs?.[Math.min(frameIndex, definition.frameCenterXs.length - 1)]
    ?? definition.anchor.uiCenterX;
}

export function resolvePetFrameFootOffset(animation: PetAnimationKey, frameIndex: number) {
  const definition: PetAnimationDefinition = PET_ANIMATIONS[animation];
  return definition.frameFootOffsets?.[Math.min(frameIndex, definition.frameFootOffsets.length - 1)]
    ?? definition.anchor.footOffset;
}

export function resolvePetFrameScale(animation: PetAnimationKey, frameIndex: number) {
  const definition: PetAnimationDefinition = PET_ANIMATIONS[animation];
  const baseScale = definition.visualScale ?? 1;
  const frameScale = definition.frameScales?.[Math.min(frameIndex, definition.frameScales.length - 1)] ?? 1;
  return baseScale * frameScale;
}

export const PET_MAX_FOOT_OFFSET = Math.max(
  ...Object.values(PET_ANIMATIONS).map((animation) => animation.anchor.footOffset),
);
