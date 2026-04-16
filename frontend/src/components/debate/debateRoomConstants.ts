import type {
  DebateAskTarget,
  DebateStageScoreKey,
  DebateTurn,
  DebateWinner,
} from "../../types";

export const STAGE_LABEL: Record<DebateTurn["stage"], string> = {
  opening: "立论",
  rebuttal: "驳论",
  free_debate: "自由辩论",
  closing: "总结",
  judge_decision: "裁判阶段",
};

export const WINNER_LABEL: Record<DebateWinner, string> = {
  pro: "正方",
  con: "反方",
  draw: "平局",
};

export const ASK_TARGET_OPTIONS: Array<{ value: DebateAskTarget; label: string }> = [
  { value: "all", label: "双方" },
  { value: "pro", label: "正方" },
  { value: "con", label: "反方" },
];

export const FLOW_STEPS: Array<{ stage: DebateSessionDetail["stage"]; label: string }> = [
  { stage: "opening", label: "立论" },
  { stage: "rebuttal", label: "驳论" },
  { stage: "free_debate", label: "自由辩论" },
  { stage: "closing", label: "总结" },
  { stage: "judge_decision", label: "裁决" },
];

export const JUDGE_STAGE_SCORE_LABEL: Record<DebateStageScoreKey, string> = {
  opening: "立论",
  rebuttal: "驳论",
  free_debate: "自由辩论",
  closing: "总结",
};

export const JUDGE_STAGE_SCORE_KEYS: DebateStageScoreKey[] = [
  "opening",
  "rebuttal",
  "free_debate",
  "closing",
];
