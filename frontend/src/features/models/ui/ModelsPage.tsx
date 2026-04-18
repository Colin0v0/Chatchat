import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

import { providerBadgeLabel, reasoningDisplayLabel } from "../lib/modelCapabilities";
import type { ModelOption } from "../../../types";
import { ModelProviderIcon } from "./model-icons/ModelProviderIcon";
import { WorkspacePage } from "../../../shared/ui/WorkspacePage";

const MODEL_TABLE_COLUMNS = "grid-cols-[minmax(320px,2.8fr)_150px_220px_140px_120px]";

function providerLabel(model: ModelOption): string {
  return providerBadgeLabel(model) || model.provider_name || model.provider_family || "未知";
}

function supportsImage(model: ModelOption): boolean {
  return (
    Boolean(model.capabilities?.input.image)
    || model.native_multimodal_mode === "local"
    || model.native_multimodal_mode === "codex"
    || model.native_multimodal_mode === "gemini"
    || model.native_multimodal_mode === "claude"
  );
}

function supportsPdf(model: ModelOption): boolean {
  return Boolean(model.capabilities?.input.pdf);
}

function supportsFiles(model: ModelOption): boolean {
  return (
    model.supports_attachment_upload
    || Boolean(model.capabilities?.input.other_file)
    || Boolean(model.capabilities?.transport.file_upload)
  );
}

function supportsReasoning(model: ModelOption): boolean {
  return (
    model.supports_thinking
    || model.supports_thinking_trace
    || Boolean(model.capabilities?.reasoning.visible_trace)
    || Boolean(model.capabilities?.reasoning.summary_only)
  );
}

function supportsTools(model: ModelOption): boolean {
  return Boolean(model.capabilities?.tools.function_calling);
}

function inputLabel(model: ModelOption): string {
  const labels = ["文本"];
  if (supportsImage(model)) {
    labels.push("图片");
  }
  if (supportsPdf(model)) {
    labels.push("PDF");
  }
  if (supportsFiles(model)) {
    labels.push("文件");
  }
  return labels.join(" / ");
}

function reasoningLabel(model: ModelOption): string {
  return reasoningDisplayLabel(model) ?? "关闭";
}

function EmptyState() {
  return (
    <div className="rounded-2xl border border-dashed border-app-border px-4 py-12 text-[14px] text-app-muted">
      当前没有可展示的模型。
    </div>
  );
}

export function ModelsPage({
  models,
  onSelectModel,
  selectedModel,
}: {
  models: ModelOption[];
  onSelectModel?: (modelId: string) => void;
  selectedModel: string;
}) {
  const [copiedModelId, setCopiedModelId] = useState<string | null>(null);
  const sortedModels = [...models].sort((left, right) => left.label.localeCompare(right.label));

  useEffect(() => {
    if (!copiedModelId) {
      return;
    }

    const timeoutId = window.setTimeout(() => setCopiedModelId(null), 1400);
    return () => window.clearTimeout(timeoutId);
  }, [copiedModelId]);

  return (
    <WorkspacePage
      headerPlacement="content"
      title="Models"
    >
      {sortedModels.length === 0 ? <EmptyState /> : null}

      {sortedModels.length > 0 ? (
        <section>
          <div className="app-scrollbar overflow-x-auto">
            <div className="min-w-[900px]">
              <div className={`grid ${MODEL_TABLE_COLUMNS} gap-4 border-b border-app-border pb-3 text-[13px] text-app-muted`}>
                <div>模型</div>
                <div>厂商</div>
                <div>输入</div>
                <div>推理</div>
                <div>工具调用</div>
              </div>

              <div className="divide-y divide-app-border">
                {sortedModels.map((model) => {
                  const active = model.id === selectedModel;
                  const copied = copiedModelId === model.id;
                  return (
                    <div
                      className={`grid ${MODEL_TABLE_COLUMNS} items-center gap-4 py-5 text-[15px] transition-colors hover:bg-app-panel-soft`}
                      key={model.id}
                      onClick={() => {
                        if (!active) {
                          onSelectModel?.(model.id);
                        }
                      }}
                    >
                      <div className="min-w-0">
                        <div className="flex min-w-0 items-center gap-1">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center">
                            <ModelProviderIcon model={model} />
                          </span>
                          <div className="min-w-0">
                            <div className="flex min-w-0 items-center gap-2">
                              <span className="truncate font-medium text-app-text">{model.label}</span>
                              {model.reasoning_model ? (
                                <span className="rounded-full bg-app-accent-soft px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] text-app-accent-strong">
                                  双模型
                                </span>
                              ) : null}
                              <button
                                aria-label={`复制 ${model.label} 模型 ID`}
                                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                                onClick={async (event) => {
                                  event.stopPropagation();
                                  try {
                                    await navigator.clipboard.writeText(model.id);
                                    setCopiedModelId(model.id);
                                  } catch {
                                    setCopiedModelId(null);
                                  }
                                }}
                                type="button"
                              >
                                {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="text-app-text">{providerLabel(model)}</div>
                      <div className="text-app-text">{inputLabel(model)}</div>
                      <div className="text-app-text">{reasoningLabel(model)}</div>
                      <div className="text-app-text">{supportsTools(model) ? "支持" : "关闭"}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </WorkspacePage>
  );
}
