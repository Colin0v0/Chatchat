export type PetAnimationKey =
  | "click"
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
  frameMs: number;
  frames: string[];
  phase: PetAnimationPhase;
  playMode: "hold" | "loop" | "once";
}

const PET_FRAME_URLS = import.meta.glob("../assets/fox/frames/**/*.png", {
  eager: true,
  import: "default",
  query: "?url",
}) as Record<string, string>;

type PetFrameFolderKey = PetAnimationKey | "trip";

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
const STANDING_ANCHOR: PetVisualAnchor = { footOffset: 13, uiCenterX: 72, uiTop: 64 };
const SLEEP_ANCHOR: PetVisualAnchor = { footOffset: 13, uiCenterX: 72, uiTop: 76 };
const LOW_NEED_ANCHOR: PetVisualAnchor = { footOffset: 60, uiCenterX: 70, uiTop: 42 };

export const PET_ANIMATIONS = {
  click: { anchor: STANDING_ANCHOR, frameMs: 180, frames: createPingPongFramePaths("click", 3), phase: "action", playMode: "once" },
  drink: { anchor: STANDING_ANCHOR, frameMs: 240, frames: createSelectedFramePaths("drink", [1, 2, 1, 2, 1]), phase: "action", playMode: "once" },
  eat: { anchor: STANDING_ANCHOR, frameMs: 240, frames: createSelectedFramePaths("eat", [1, 2, 1, 2, 1]), phase: "action", playMode: "once" },
  emotion: { anchor: STANDING_ANCHOR, frameMs: 180, frames: createPingPongFramePaths("emotion", 5), phase: "action", playMode: "once" },
  happy: { anchor: STANDING_ANCHOR, frameMs: 130, frames: createPingPongFramePaths("happy", 10), phase: "action", playMode: "once" },
  hurt: { anchor: STANDING_ANCHOR, frameMs: 220, frames: createPingPongFramePaths("hurt", 2), phase: "action", playMode: "once" },
  // idle 这组素材每帧五官和身体重心不完全一致，循环起来会像原地走路；待机先用稳定单帧。
  idle: { anchor: STANDING_ANCHOR, frameMs: 240, frames: createSelectedFramePaths("idle", [1]), phase: "pose", playMode: "hold" },
  pickup: { anchor: STANDING_ANCHOR, frameMs: 120, frames: createFramePaths("pickup", 4), phase: "action", playMode: "once" },
  pickupHold: { anchor: STANDING_ANCHOR, frameMs: 180, frames: createSelectedFramePaths("pickup", [3, 4, 3, 4]), phase: "action", playMode: "loop" },
  praise: { anchor: STANDING_ANCHOR, frameMs: 180, frames: createSelectedFramePaths("praise", [1, 2, 3, 4]), phase: "action", playMode: "once" },
  putdown: { anchor: STANDING_ANCHOR, frameMs: 160, frames: createPingPongFramePaths("putdown", 2), phase: "action", playMode: "once" },
  // 低状态要持续趴着；trip-05 是头抬起来的委屈帧，比一次性摔倒动作更适合常驻。
  sad: { anchor: LOW_NEED_ANCHOR, frameMs: 240, frames: createSelectedFramePaths("trip", [5]), phase: "pose", playMode: "hold" },
  sleep: { anchor: SLEEP_ANCHOR, frameMs: 520, frames: createSelectedFramePaths("sleep", [1]), phase: "pose", playMode: "hold" },
  surprised: { anchor: STANDING_ANCHOR, frameMs: 150, frames: createPingPongFramePaths("surprised", 5), phase: "action", playMode: "once" },
  // 走路尽量用更稳的前三帧来回摆，后面几帧表情变化太大，眼睛会显得一直在跳。
  walk: { anchor: STANDING_ANCHOR, frameMs: 180, frames: createPingPongFramePaths("walk", 3), phase: "locomotion", playMode: "loop" },
} satisfies Record<PetAnimationKey, PetAnimationDefinition>;

export const PET_MAX_FOOT_OFFSET = Math.max(
  ...Object.values(PET_ANIMATIONS).map((animation) => animation.anchor.footOffset),
);
