import type { MessageAttachment, ModelOption } from "../../../types";

export type BattleSideId = "a" | "b";
export type BattleVote = "a" | "b" | "both_good" | "both_bad";
export type BattleSideStatus = "streaming" | "done" | "error";

export interface BattleSideState {
  id: BattleSideId;
  model: ModelOption;
  content: string;
  reasoning: string;
  status: BattleSideStatus;
  error: string | null;
  startedAt: number;
  finishedAt: number | null;
}

export interface BattleRound {
  id: string;
  prompt: string;
  createdAt: string;
  revealed: boolean;
  vote: BattleVote | null;
  sides: {
    a: BattleSideState;
    b: BattleSideState;
  };
  attachments: MessageAttachment[];
}

export interface BattleSessionDetail {
  id: number;
  title: string;
  created_at: string;
  updated_at: string | null;
  rounds: BattleRound[];
}
