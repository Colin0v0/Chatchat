import type {
  ChatMessage,
  ConversationDetail,
  DebateJudgeAnalysis,
  DebateSessionDetail,
  DebateStage,
} from "../types";

const DEBATE_STAGE_LABEL: Record<DebateStage, string> = {
  opening: "立论",
  rebuttal: "驳论",
  free_debate: "自由辩论",
  closing: "总结陈词",
  judge_decision: "裁判阶段",
};

const WINNER_LABEL = {
  pro: "正方",
  con: "反方",
  draw: "平局",
} as const;

function formatDate(value: string | null | undefined) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString("zh-CN", { hour12: false });
}

function toSafeFilename(input: string, fallback: string) {
  const normalized = input.trim().replace(/[<>:"/\\|?*\u0000-\u001F]/g, "_");
  return normalized || fallback;
}

function section(title: string, body: string) {
  if (!body.trim()) {
    return "";
  }
  return `## ${title}\n\n${body.trim()}\n`;
}

function listBlock(items: string[]) {
  if (!items.length) {
    return "- 无";
  }
  return items.map((item) => `- ${item}`).join("\n");
}

function parseJudgeAnalysis(scoringJson: Record<string, unknown> | undefined | null): DebateJudgeAnalysis {
  const analysis =
    scoringJson?.analysis && typeof scoringJson.analysis === "object"
      ? (scoringJson.analysis as Record<string, unknown>)
      : {};

  const read = (...values: unknown[]) => {
    for (const value of values) {
      if (typeof value === "string" && value.trim()) {
        return value.trim();
      }
    }
    return "";
  };

  return {
    pro_review: read(analysis.pro_review, analysis.pro),
    con_review: read(analysis.con_review, analysis.con),
    shared_feedback: read(analysis.shared_feedback, analysis.both),
    key_decision: read(analysis.key_decision, analysis.key_point),
    final_vote: read(analysis.final_vote, analysis.vote),
  };
}

function buildConversationMessageMarkdown(message: ChatMessage, index: number) {
  const roleLabel =
    message.role === "user" ? "用户" : message.role === "assistant" ? "助手" : "系统";
  const createdAt = formatDate(message.created_at);
  const metaLine = createdAt ? `\n\n- 时间：${createdAt}` : "";
  const attachmentLine =
    message.attachments && message.attachments.length > 0
      ? `\n- 附件：${message.attachments.map((item) => item.original_name).join("、")}`
      : "";
  const sourceLine =
    message.sources && message.sources.length > 0
      ? `\n- 来源：${message.sources
          .map((item) => item.title || item.path || item.url || "")
          .filter(Boolean)
          .join("、")}`
      : "";
  const reasoningBlock =
    message.reasoning && message.reasoning.trim()
      ? `\n\n> 思考过程\n>\n${message.reasoning
          .trim()
          .split("\n")
          .map((line) => `> ${line}`)
          .join("\n")}`
      : "";
  const content = message.content?.trim() || "[空]";

  return `## ${index + 1}. ${roleLabel}${metaLine}${attachmentLine}${sourceLine}\n\n${content}${reasoningBlock}\n`;
}

export function buildConversationMarkdown(conversation: ConversationDetail) {
  const header = [
    `# ${conversation.title || "未命名聊天"}`,
    "",
    `- 导出时间：${formatDate(new Date().toISOString())}`,
    `- 模型：${conversation.model || "未知"}`,
    `- 消息数：${conversation.messages.length}`,
    "",
  ].join("\n");

  const messages = conversation.messages
    .map((message, index) => buildConversationMessageMarkdown(message, index))
    .join("\n");

  return `${header}${messages}`.trimEnd() + "\n";
}

function buildDebateTurnMarkdown(
  session: DebateSessionDetail,
  stage: DebateStage,
) {
  const participantMap = new Map(session.participants.map((participant) => [participant.id, participant]));
  const stageTurns = session.turns
    .filter((turn) => turn.stage === stage)
    .sort((left, right) => left.turn_index - right.turn_index);

  if (!stageTurns.length) {
    return "暂无记录。";
  }

  return stageTurns
    .map((turn) => {
      if (turn.kind === "judge_question") {
        return `### 裁判追问\n\n${turn.content.trim() || "[空]"}`;
      }

      const participant =
        turn.speaker_participant_id != null
          ? participantMap.get(turn.speaker_participant_id) ?? null
          : null;
      const sideLabel = participant?.side === "con" ? "反方" : "正方";
      const modelLabel = participant?.model_id || "未知模型";
      const timeLabel =
        typeof turn.elapsed_ms === "number" && Number.isFinite(turn.elapsed_ms)
          ? `\n- 用时：${(turn.elapsed_ms / 1000).toFixed(1)}s`
          : "";
      const truncatedLabel = turn.truncated ? "\n- 状态：超时截断" : "";

      return `### ${sideLabel} · ${modelLabel}${timeLabel}${truncatedLabel}\n\n${turn.content.trim() || "[空]"}`;
    })
    .join("\n\n");
}

function buildDebateStageScoreTable(scoringJson: Record<string, unknown> | undefined | null) {
  const stageScores =
    scoringJson?.stage_scores && typeof scoringJson.stage_scores === "object"
      ? (scoringJson.stage_scores as Record<string, unknown>)
      : {};

  const rows = (["opening", "rebuttal", "free_debate", "closing"] as const)
    .map((key) => {
      const entry =
        stageScores[key] && typeof stageScores[key] === "object"
          ? (stageScores[key] as Record<string, unknown>)
          : {};
      const pro = typeof entry.pro === "number" ? entry.pro : "-";
      const con = typeof entry.con === "number" ? entry.con : "-";
      return `| ${DEBATE_STAGE_LABEL[key]} | ${pro} | ${con} |`;
    })
    .join("\n");

  return `| 阶段 | 正方 | 反方 |\n| --- | --- | --- |\n${rows}`;
}

export function buildDebateMarkdown(session: DebateSessionDetail) {
  const participantMap = Object.fromEntries(session.participants.map((item) => [item.side, item.model_id]));
  const stageTimes = session.stage_time_limits_ms ?? {};
  const judgeDecision = session.judge_decision;
  const scoringJson = judgeDecision?.scoring_json;
  const analysis = parseJudgeAnalysis(scoringJson);
  const analysisMarkdown =
    typeof scoringJson?.analysis_markdown === "string" ? scoringJson.analysis_markdown.trim() : "";
  const winner = judgeDecision?.winner_side ? WINNER_LABEL[judgeDecision.winner_side] : "";

  const header = [
    `# ${session.topic || "未命名辩论"}`,
    "",
    `- 导出时间：${formatDate(new Date().toISOString())}`,
    `- 状态：${session.status}`,
    `- 当前阶段：${DEBATE_STAGE_LABEL[session.stage]}`,
    `- 正方模型：${participantMap.pro || "未知"}`,
    `- 反方模型：${participantMap.con || "未知"}`,
    `- 立论时长：${Math.round((stageTimes.opening ?? 0) / 1000)}s`,
    `- 驳论时长：${Math.round((stageTimes.rebuttal ?? 0) / 1000)}s`,
    `- 自由辩论时长：${Math.round((stageTimes.free_debate ?? 0) / 1000)}s`,
    `- 总结陈词时长：${Math.round((stageTimes.closing ?? 0) / 1000)}s`,
    session.created_at ? `- 创建时间：${formatDate(session.created_at)}` : "",
    session.finished_at ? `- 结束时间：${formatDate(session.finished_at)}` : "",
    "",
  ]
    .filter(Boolean)
    .join("\n");

  const transcript = (["opening", "rebuttal", "free_debate", "closing"] as const)
    .map((stage) => section(DEBATE_STAGE_LABEL[stage], buildDebateTurnMarkdown(session, stage)))
    .join("\n");

  const summaryBlock = section("结果总结", session.summary || "暂无。");
  const judgeBlocks = judgeDecision
    ? [
        "## AI评委",
        "",
        winner ? `- 获胜方：${winner}` : "",
        typeof scoringJson?.pro_score === "number" ? `- 正方总分：${scoringJson.pro_score}` : "",
        typeof scoringJson?.con_score === "number" ? `- 反方总分：${scoringJson.con_score}` : "",
        judgeDecision.judge_comment ? `- 裁决摘要：${judgeDecision.judge_comment}` : "",
        "",
        "### 阶段判分",
        "",
        buildDebateStageScoreTable(scoringJson),
        "",
        analysisMarkdown,
        analysisMarkdown ? "" : analysis.pro_review ? `### 正方评价\n\n${analysis.pro_review}\n` : "",
        analysisMarkdown ? "" : analysis.con_review ? `### 反方评价\n\n${analysis.con_review}\n` : "",
        analysisMarkdown ? "" : analysis.shared_feedback ? `### 双方共同表现\n\n${analysis.shared_feedback}\n` : "",
        analysisMarkdown ? "" : analysis.key_decision ? `### 关键胜负手\n\n${analysis.key_decision}\n` : "",
        analysisMarkdown ? "" : analysis.final_vote ? `### 最终投票\n\n${analysis.final_vote}\n` : "",
      ]
        .filter(Boolean)
        .join("\n")
    : "";

  return `${header}${transcript}\n${summaryBlock}\n${judgeBlocks}`.trimEnd() + "\n";
}

export function downloadMarkdown(filenameBase: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${toSafeFilename(filenameBase, "export")}.md`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
