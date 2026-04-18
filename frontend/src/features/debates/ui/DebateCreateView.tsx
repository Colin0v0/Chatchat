import { useMemo, useState } from "react";

import { INITIAL_CHAT_MODEL } from "../../chats/lib/constants";
import { ModelSelect } from "../../models/ui/ModelSelect";
import type { ModelOption } from "../../../types";

const DEFAULT_STAGE_DURATION_SECONDS = {
  opening: 10,
  rebuttal: 10,
  free_debate: 60,
  closing: 15,
};

export function DebateCreateView({
  defaultProModelId,
  defaultConModelId,
  models,
  onCancel,
  onCreate,
}: {
  defaultProModelId: string;
  defaultConModelId: string;
  models: ModelOption[];
  onCancel: () => void;
  onCreate: (payload: {
    topic: string;
    proModelId: string;
    conModelId: string;
    judgeModelId: string;
    proStyle: string;
    conStyle: string;
    openingDurationSec: number;
    rebuttalDurationSec: number;
    freeDebateDurationSec: number;
    closingDurationSec: number;
  }) => void | Promise<void>;
}) {
  const [topic, setTopic] = useState("");
  const [proModelId, setProModelId] = useState(defaultProModelId);
  const [conModelId, setConModelId] = useState(defaultConModelId);
  const [judgeModelId, setJudgeModelId] = useState(INITIAL_CHAT_MODEL);
  const [proStyle, setProStyle] = useState("");
  const [conStyle, setConStyle] = useState("");
  const [openingDurationInput, setOpeningDurationInput] = useState(
    String(DEFAULT_STAGE_DURATION_SECONDS.opening),
  );
  const [rebuttalDurationInput, setRebuttalDurationInput] = useState(
    String(DEFAULT_STAGE_DURATION_SECONDS.rebuttal),
  );
  const [freeDebateDurationInput, setFreeDebateDurationInput] = useState(
    String(DEFAULT_STAGE_DURATION_SECONDS.free_debate),
  );
  const [closingDurationInput, setClosingDurationInput] = useState(
    String(DEFAULT_STAGE_DURATION_SECONDS.closing),
  );
  const [submitting, setSubmitting] = useState(false);

  const normalizedModels = useMemo(() => (models.length > 0 ? models : []), [models]);
  const submitDisabled = submitting || !topic.trim() || !proModelId || !conModelId;

  async function handleSubmit() {
    if (submitDisabled) {
      return;
    }

    const openingDurationSec = normalizeStageDuration(
      openingDurationInput,
      5,
      DEFAULT_STAGE_DURATION_SECONDS.opening,
    );
    const rebuttalDurationSec = normalizeStageDuration(
      rebuttalDurationInput,
      5,
      DEFAULT_STAGE_DURATION_SECONDS.rebuttal,
    );
    const freeDebateDurationSec = normalizeStageDuration(
      freeDebateDurationInput,
      10,
      DEFAULT_STAGE_DURATION_SECONDS.free_debate,
    );
    const closingDurationSec = normalizeStageDuration(
      closingDurationInput,
      5,
      DEFAULT_STAGE_DURATION_SECONDS.closing,
    );

    setOpeningDurationInput(String(openingDurationSec));
    setRebuttalDurationInput(String(rebuttalDurationSec));
    setFreeDebateDurationInput(String(freeDebateDurationSec));
    setClosingDurationInput(String(closingDurationSec));

    setSubmitting(true);
    try {
      await onCreate({
        topic: topic.trim(),
        proModelId,
        conModelId,
        judgeModelId,
        proStyle: proStyle.trim(),
        conStyle: conStyle.trim(),
        openingDurationSec,
        rebuttalDurationSec,
        freeDebateDurationSec,
        closingDurationSec,
      });
    } finally {
      setSubmitting(false);
    }
  }

  function normalizeStageDuration(value: string, min: number, fallback: number) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }
    return Math.max(min, Math.round(parsed));
  }

  function syncStageDuration(
    value: string,
    min: number,
    fallback: number,
    apply: (next: string) => void,
  ) {
    apply(String(normalizeStageDuration(value, min, fallback)));
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col pb-1">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto pt-6">
        <div className="mx-auto w-full max-w-[920px] px-4 md:px-6">
          <div className="rounded-[8px] border border-app-border bg-app-panel px-6 py-6">
            <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">新建辩论</div>

            {/* 辩题 */}
            <div className="mt-4">
              <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">辩题</label>
              <input
                className="mt-2 w-full rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3 text-[16px] text-app-text outline-none transition focus:border-app-border-strong"
                onChange={(event) => setTopic(event.target.value)}
                placeholder="例如：上班摸鱼对不对"
                value={topic}
              />
            </div>

            {/* 模型选择 */}
            <div className="mt-4 grid grid-cols-1 gap-5 md:grid-cols-2">
              <div>
                <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">正方模型</label>
                <div className="mt-2">
                  <ModelSelect
                    fullWidth
                    label="正方模型"
                    menuPlacement="bottom"
                    model={proModelId}
                    models={normalizedModels}
                    onChange={setProModelId}
                  />
                </div>
              </div>

              <div>
                <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">反方模型</label>
                <div className="mt-2">
                  <ModelSelect
                    fullWidth
                    label="反方模型"
                    menuPlacement="bottom"
                    model={conModelId}
                    models={normalizedModels}
                    onChange={setConModelId}
                  />
                </div>
              </div>
            </div>

            <div className="mt-4">
              <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">
                AI 裁判模型
              </label>
              <div className="mt-2">
                <ModelSelect
                  fullWidth
                  label="AI 裁判模型"
                  menuPlacement="bottom"
                  model={judgeModelId}
                  models={normalizedModels}
                  onChange={setJudgeModelId}
                />
              </div>
            </div>

            <div className="mt-4">
              <div className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">阶段时长</div>
              <div className="mt-2 grid grid-cols-2 gap-4 md:gap-5">
                <div className="min-w-0">
                  <label className="text-[13px] font-semibold text-app-text">立论</label>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      className="w-full rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3 text-[15px] text-app-text outline-none transition focus:border-app-border-strong"
                      inputMode="numeric"
                      min={5}
                      onBlur={(event) =>
                        syncStageDuration(
                          event.target.value,
                          5,
                          DEFAULT_STAGE_DURATION_SECONDS.opening,
                          setOpeningDurationInput,
                        )
                      }
                      onChange={(event) => setOpeningDurationInput(event.target.value)}
                      type="number"
                      value={openingDurationInput}
                    />
                    <span className="text-[13px] text-app-muted">s</span>
                  </div>
                </div>

                <div className="min-w-0">
                  <label className="text-[13px] font-semibold text-app-text">驳论</label>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      className="w-full rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3 text-[15px] text-app-text outline-none transition focus:border-app-border-strong"
                      inputMode="numeric"
                      min={5}
                      onBlur={(event) =>
                        syncStageDuration(
                          event.target.value,
                          5,
                          DEFAULT_STAGE_DURATION_SECONDS.rebuttal,
                          setRebuttalDurationInput,
                        )
                      }
                      onChange={(event) => setRebuttalDurationInput(event.target.value)}
                      type="number"
                      value={rebuttalDurationInput}
                    />
                    <span className="text-[13px] text-app-muted">s</span>
                  </div>
                </div>

                <div className="min-w-0">
                  <label className="text-[13px] font-semibold text-app-text">自由辩论</label>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      className="w-full rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3 text-[15px] text-app-text outline-none transition focus:border-app-border-strong"
                      inputMode="numeric"
                      min={10}
                      onBlur={(event) =>
                        syncStageDuration(
                          event.target.value,
                          10,
                          DEFAULT_STAGE_DURATION_SECONDS.free_debate,
                          setFreeDebateDurationInput,
                        )
                      }
                      onChange={(event) => setFreeDebateDurationInput(event.target.value)}
                      type="number"
                      value={freeDebateDurationInput}
                    />
                    <span className="text-[13px] text-app-muted">s</span>
                  </div>
                </div>

                <div className="min-w-0">
                  <label className="text-[13px] font-semibold text-app-text">总结陈词</label>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      className="w-full rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3 text-[15px] text-app-text outline-none transition focus:border-app-border-strong"
                      inputMode="numeric"
                      min={5}
                      onBlur={(event) =>
                        syncStageDuration(
                          event.target.value,
                          5,
                          DEFAULT_STAGE_DURATION_SECONDS.closing,
                          setClosingDurationInput,
                        )
                      }
                      onChange={(event) => setClosingDurationInput(event.target.value)}
                      type="number"
                      value={closingDurationInput}
                    />
                    <span className="text-[13px] text-app-muted">s</span>
                  </div>
                </div>
              </div>
            </div>

            {/* 双方提示词 / 语气风格 */}
            <div className="mt-4 grid grid-cols-1 gap-5 md:grid-cols-2">
              <div>
                <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">
                  正方提示词
                </label>
                <textarea
                  className="mt-2 min-h-[120px] w-full resize-none rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3 text-[14px] leading-[1.6] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong"
                  onChange={(event) => setProStyle(event.target.value)}
                  placeholder="例如：犀利强硬、逻辑严密，善用数据和类比"
                  value={proStyle}
                />
              </div>

              <div>
                <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">
                  反方提示词
                </label>
                <textarea
                  className="mt-2 min-h-[120px] w-full resize-none rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3 text-[14px] leading-[1.6] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong"
                  onChange={(event) => setConStyle(event.target.value)}
                  placeholder="例如：温和理性、引经据典，擅长揭示对方前提漏洞"
                  value={conStyle}
                />
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-3">
              <button
                className="rounded-[8px] px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                onClick={onCancel}
                type="button"
              >
                取消
              </button>
              <button
                className="rounded-[8px] bg-app-accent-soft px-4 py-2.5 text-[15px] font-medium text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-60"
                disabled={submitDisabled}
                onClick={() => void handleSubmit()}
                type="button"
              >
                {submitting ? "创建中..." : "创建辩论"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
