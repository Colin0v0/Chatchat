import type { PetCompanionContext } from "../api/petChat";
import type { PetPreferences } from "./usePetPreferences";

type PetMode = "awake" | "sleeping";

type PetBehaviorStats = {
  energy: number;
  hunger: number;
  mood: number;
  thirst: number;
};

export type PetMotiveKey =
  | "curious"
  | "hungry"
  | "lonely"
  | "resting"
  | "settled"
  | "sleepy"
  | "thirsty"
  | "unwell";

export type PetNeedKey = "energy" | "hunger" | "mood" | "thirst";
export type PetNeedTone = "critical" | "good" | "low" | "soft";

export type PetNeedSnapshot = {
  actionLabel: string;
  key: PetNeedKey;
  label: string;
  stateLabel: string;
  tone: PetNeedTone;
  value: number;
};

export type PetBehaviorSnapshot = {
  careHint: string;
  motive: PetMotiveKey;
  needs: PetNeedSnapshot[];
  primaryNeed: PetNeedKey;
  shouldHoldLowPose: boolean;
  title: string;
};

type ResolvePetBehaviorOptions = {
  context: PetCompanionContext;
  mode: PetMode;
  preferences: PetPreferences;
  stats: PetBehaviorStats;
};

const LOW_NEED_THRESHOLD = 20;
const SOFT_NEED_THRESHOLD = 45;
const NEED_LABELS: Record<PetNeedKey, string> = {
  energy: "精力",
  hunger: "饱食",
  mood: "心情",
  thirst: "水分",
};
const NEED_ACTION_LABELS: Record<PetNeedKey, string> = {
  energy: "哄睡",
  hunger: "喂食",
  mood: "陪伴",
  thirst: "添水",
};
const NEED_STATE_LABELS: Record<PetNeedKey, Record<PetNeedTone, string>> = {
  energy: {
    critical: "困到发软",
    good: "很精神",
    low: "开始犯困",
    soft: "还够用",
  },
  hunger: {
    critical: "饿坏了",
    good: "饱饱的",
    low: "想吃点",
    soft: "还不饿",
  },
  mood: {
    critical: "很委屈",
    good: "很安心",
    low: "想被理",
    soft: "还不错",
  },
  thirst: {
    critical: "很想喝水",
    good: "水分够",
    low: "想喝水",
    soft: "还可以",
  },
};
const MOTIVE_COPY: Record<PetMotiveKey, { careHint: string; title: string }> = {
  curious: {
    careHint: "它在看你写东西，会尽量安静一点。",
    title: "在看你忙什么",
  },
  hungry: {
    careHint: "给它喂一点，比继续看百分比更像是在照顾它。",
    title: "想吃一点",
  },
  lonely: {
    careHint: "夸一下或陪它说两句，它会更安心。",
    title: "想被理一下",
  },
  resting: {
    careHint: "睡着时精力会持续回来，饱食和水分会慢慢消耗。",
    title: "睡着了",
  },
  settled: {
    careHint: "状态挺稳，放着它自己待一会儿也没关系。",
    title: "现在挺舒服",
  },
  sleepy: {
    careHint: "让它休息一会儿，精力和心情会一点点恢复。",
    title: "开始犯困",
  },
  thirsty: {
    careHint: "添点水最有用，它喝完会安静很多。",
    title: "想喝水",
  },
  unwell: {
    careHint: "先照顾最低的那一项，它缓过来后会自己站起来。",
    title: "有点撑不住",
  },
};

function resolveNeedTone(value: number): PetNeedTone {
  if (value <= LOW_NEED_THRESHOLD) {
    return "critical";
  }

  if (value <= SOFT_NEED_THRESHOLD) {
    return "low";
  }

  if (value <= 72) {
    return "soft";
  }

  return "good";
}

function createNeedSnapshot(key: PetNeedKey, value: number): PetNeedSnapshot {
  const tone = resolveNeedTone(value);
  return {
    actionLabel: NEED_ACTION_LABELS[key],
    key,
    label: NEED_LABELS[key],
    stateLabel: NEED_STATE_LABELS[key][tone],
    tone,
    value,
  };
}

function pickPrimaryNeed(needs: PetNeedSnapshot[]) {
  return needs.reduce((lowest, need) => (need.value < lowest.value ? need : lowest));
}

function hasVisibleDraft(context: PetCompanionContext, preferences: PetPreferences) {
  // 草稿开关关闭时，行为层也不读取草稿内容，只让狐狸保持普通待机。
  return preferences.referenceDraft && context.draft.trim().length > 0;
}

function resolveMotive({ context, mode, preferences, stats }: ResolvePetBehaviorOptions): PetMotiveKey {
  if (mode === "sleeping") {
    return "resting";
  }

  if (stats.hunger <= LOW_NEED_THRESHOLD && stats.thirst <= LOW_NEED_THRESHOLD) {
    return "unwell";
  }

  if (stats.hunger <= LOW_NEED_THRESHOLD) {
    return "hungry";
  }

  if (stats.thirst <= LOW_NEED_THRESHOLD) {
    return "thirsty";
  }

  if (stats.mood <= LOW_NEED_THRESHOLD) {
    return "lonely";
  }

  if (stats.energy <= LOW_NEED_THRESHOLD) {
    return "sleepy";
  }

  if (stats.hunger <= SOFT_NEED_THRESHOLD) {
    return "hungry";
  }

  if (stats.thirst <= SOFT_NEED_THRESHOLD) {
    return "thirsty";
  }

  if (stats.mood <= SOFT_NEED_THRESHOLD) {
    return "lonely";
  }

  if (hasVisibleDraft(context, preferences)) {
    return "curious";
  }

  if (stats.energy <= SOFT_NEED_THRESHOLD) {
    return "sleepy";
  }

  return "settled";
}

export function resolvePetBehaviorSnapshot(options: ResolvePetBehaviorOptions): PetBehaviorSnapshot {
  const needs = [
    createNeedSnapshot("hunger", options.stats.hunger),
    createNeedSnapshot("thirst", options.stats.thirst),
    createNeedSnapshot("energy", options.stats.energy),
    createNeedSnapshot("mood", options.stats.mood),
  ];
  const motive = resolveMotive(options);
  const primaryNeed = pickPrimaryNeed(needs).key;

  return {
    careHint: MOTIVE_COPY[motive].careHint,
    motive,
    needs,
    primaryNeed,
    shouldHoldLowPose: options.stats.hunger <= LOW_NEED_THRESHOLD
      || options.stats.mood <= LOW_NEED_THRESHOLD
      || options.stats.thirst <= LOW_NEED_THRESHOLD,
    title: MOTIVE_COPY[motive].title,
  };
}
