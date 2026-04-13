import { useMemo, useState } from "react";

import type { ModelOption } from "../types";

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
  onCreate: (payload: { topic: string; proModelId: string; conModelId: string }) => void | Promise<void>;
}) {
  const [topic, setTopic] = useState("");
  const [proModelId, setProModelId] = useState(defaultProModelId);
  const [conModelId, setConModelId] = useState(defaultConModelId);
  const [submitting, setSubmitting] = useState(false);

  const normalizedModels = useMemo(() => (models.length > 0 ? models : []), [models]);
  const submitDisabled = submitting || !topic.trim() || !proModelId || !conModelId;

  async function handleSubmit() {
    if (submitDisabled) {
      return;
    }

    setSubmitting(true);
    try {
      await onCreate({ topic: topic.trim(), proModelId, conModelId });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col pb-1">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto pt-6">
        <div className="mx-auto w-full max-w-[920px] px-4 md:px-6">
          <div className="rounded-[28px] border border-app-border bg-app-panel px-7 py-7 shadow-[0_24px_80px_rgba(34,24,16,0.08)]">
            <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">新建辩论</div>
            <div className="mt-3 text-[14px] leading-7 text-app-muted">
              默认关闭知识库/联网；MVP 先支持双人正反方、半自动推进。
            </div>

            <div className="mt-6">
              <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">辩题</label>
              <input
                className="mt-2 w-full rounded-2xl border border-app-border bg-app-panel-strong px-4 py-3 text-[16px] text-app-text outline-none transition focus:border-app-border-strong"
                onChange={(event) => setTopic(event.target.value)}
                placeholder="例如：上班摸鱼对不对"
                value={topic}
              />
            </div>

            <div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2">
              <div>
                <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">正方模型</label>
                <select
                  className="mt-2 w-full rounded-2xl border border-app-border bg-app-panel-strong px-4 py-3 text-[15px] text-app-text outline-none transition focus:border-app-border-strong"
                  onChange={(event) => setProModelId(event.target.value)}
                  value={proModelId}
                >
                  {normalizedModels.map((model) => (
                    <option key={`pro-${model.id}`} value={model.id}>
                      {model.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[13px] font-semibold tracking-[0.12em] text-app-muted uppercase">反方模型</label>
                <select
                  className="mt-2 w-full rounded-2xl border border-app-border bg-app-panel-strong px-4 py-3 text-[15px] text-app-text outline-none transition focus:border-app-border-strong"
                  onChange={(event) => setConModelId(event.target.value)}
                  value={conModelId}
                >
                  {normalizedModels.map((model) => (
                    <option key={`con-${model.id}`} value={model.id}>
                      {model.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-7 flex justify-end gap-3">
              <button
                className="rounded-xl px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                onClick={onCancel}
                type="button"
              >
                取消
              </button>
              <button
                className="rounded-xl bg-app-accent-soft px-4 py-2.5 text-[15px] font-medium text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-60"
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

