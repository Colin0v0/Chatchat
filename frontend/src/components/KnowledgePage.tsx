import { FileUp, RefreshCw, Trash2 } from "lucide-react";
import { useRef } from "react";

import type { KnowledgeDocument, KnowledgeStatus } from "../types";
import { WorkspacePage } from "./WorkspacePage";

function StatChip({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-app-border bg-app-panel-strong px-3 py-1.5 text-[13px] text-app-muted">
      {children}
    </span>
  );
}

function EmptyState({ children }: { children: string }) {
  return (
    <div className="rounded-xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
      {children}
    </div>
  );
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "未记录";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatBytes(value: number): string {
  if (value >= 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${Math.round(value / 1024)} KB`;
  }
  return `${value} B`;
}

function KnowledgeCard({
  document,
  onDelete,
  onReindex,
  onSelect,
  selected,
}: {
  document: KnowledgeDocument;
  onDelete: (documentId: number) => void;
  onReindex: (documentId: number) => void;
  onSelect: (documentId: number) => void;
  selected: boolean;
}) {
  const statusLabel =
    document.status === "ready"
      ? "可用"
      : document.status === "indexing"
        ? "索引中"
        : document.status === "failed"
          ? "失败"
          : "待处理";
  const normalizedExtension = document.extension.replace(/^\./, "").toLowerCase();
  const formatLabel =
    !normalizedExtension || normalizedExtension === "md" || normalizedExtension === "markdown"
      ? "Markdown"
      : normalizedExtension.toUpperCase();

  return (
    <div className="rounded-xl border border-app-border bg-app-panel-strong p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <label className="mt-0.5 flex shrink-0 items-center">
            <input
              checked={selected}
              className="h-4 w-4 rounded border-app-border text-app-accent-strong focus:ring-app-accent-strong"
              onChange={() => onSelect(document.id)}
              type="checkbox"
            />
          </label>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-app-accent-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-accent-strong">
                {formatLabel}
              </span>
              <span className="rounded-full border border-app-border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-muted">
                {statusLabel}
              </span>
            </div>
            <div className="mt-3 truncate text-[16px] font-semibold tracking-[-0.02em] text-app-text">
              {document.title}
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-[12px] text-app-muted">
              <span>{formatBytes(document.size_bytes)}</span>
              <span>{document.chunk_count} 分块</span>
              <span>{formatTimestamp(document.updated_at)}</span>
            </div>
            {document.error_message ? (
              <div className="mt-3 text-[13px] leading-6 text-[#9d3d32]">{document.error_message}</div>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-app-border bg-app-panel text-app-muted transition hover:text-app-text"
            onClick={() => onReindex(document.id)}
            type="button"
          >
            <RefreshCw className="size-4" />
          </button>
          <button
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-app-border bg-app-panel text-app-muted transition hover:text-app-text"
            onClick={() => onDelete(document.id)}
            type="button"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function KnowledgePage({
  knowledge,
}: {
  knowledge: {
    documents: KnowledgeDocument[];
    status: KnowledgeStatus;
    error: string | null;
    isLoading: boolean;
    isSaving: boolean;
    isUpdating: boolean;
    isAllSelected: boolean;
    onDelete: (documentId: number) => void;
    onDeleteSelected: () => void;
    onRefresh: () => void;
    onReindex: (documentId: number) => void;
    onSelectAll: () => void;
    onSelectOne: (documentId: number) => void;
    onUpdate: () => void;
    onUploadMany: (files: File[]) => void;
    selectedDocumentIds: number[];
    updateResult: {
      started: boolean;
      scheduled_documents: number;
      indexing_documents: number;
      ready_documents: number;
      failed_documents: number;
      chunk_count: number;
    } | null;
  };
}) {
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const knowledgeProgress =
    knowledge.updateResult && knowledge.updateResult.scheduled_documents > 0
      ? Math.max(
          0,
          Math.min(
            100,
            Math.round(
              ((knowledge.updateResult.scheduled_documents - knowledge.status.indexing_document_count) /
                knowledge.updateResult.scheduled_documents) *
                100,
            ),
          ),
        )
      : null;

  return (
    <WorkspacePage
      headerPlacement="content"
      actions={
        <>
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel-strong px-4 py-2.5 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-50"
            disabled={knowledge.isSaving}
            onClick={() => uploadInputRef.current?.click()}
            type="button"
          >
            <FileUp className="size-4" />
            上传 Markdown
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text disabled:cursor-not-allowed disabled:opacity-50"
            disabled={knowledge.selectedDocumentIds.length === 0 || knowledge.isSaving}
            onClick={knowledge.onDeleteSelected}
            type="button"
          >
            <Trash2 className="size-4" />
            删除{knowledge.selectedDocumentIds.length > 0 ? ` (${knowledge.selectedDocumentIds.length})` : ""}
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text disabled:cursor-not-allowed disabled:opacity-50"
            disabled={knowledge.isUpdating}
            onClick={knowledge.onUpdate}
            type="button"
          >
            <RefreshCw className={`size-4 ${knowledge.isUpdating ? "animate-spin" : ""}`} />
            {knowledge.isUpdating ? "更新中..." : "更新知识库"}
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={knowledge.onRefresh}
            type="button"
          >
            <RefreshCw className={`size-4 ${knowledge.isLoading ? "animate-spin" : ""}`} />
            刷新
          </button>
        </>
      }
      title="Knowledge"
    >
      <input
        accept=".md,text/markdown"
        className="hidden"
        multiple
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length > 0) {
            knowledge.onUploadMany(files);
          }
          event.currentTarget.value = "";
        }}
        ref={uploadInputRef}
        type="file"
      />

      <div className="flex flex-wrap gap-2">
        <StatChip>{`文档 ${knowledge.status.document_count}/${knowledge.status.max_documents_per_user || 0}`}</StatChip>
        <StatChip>{`待更新 ${knowledge.status.pending_document_count}`}</StatChip>
        <StatChip>{`索引中 ${knowledge.status.indexing_document_count}`}</StatChip>
        <StatChip>{`可用 ${knowledge.status.ready_document_count}`}</StatChip>
        <StatChip>{`失败 ${knowledge.status.failed_document_count}`}</StatChip>
        <StatChip>{`分块 ${knowledge.status.chunk_count}`}</StatChip>
        <StatChip>{`空间 ${formatBytes(knowledge.status.total_size_bytes)}`}</StatChip>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-app-border bg-app-panel-strong px-4 py-4">
          <div className="text-[14px] font-medium text-app-text">支持格式</div>
          <div className="mt-2 text-[14px] leading-6 text-app-muted">当前接入的是 Markdown 文档上传和索引。</div>
        </div>
        <div className="rounded-xl border border-app-border bg-app-panel-strong px-4 py-4">
          <div className="text-[14px] font-medium text-app-text">单文件上限</div>
          <div className="mt-2 text-[14px] leading-6 text-app-muted">{formatBytes(knowledge.status.max_file_size_bytes)}</div>
        </div>
        <div className="rounded-xl border border-app-border bg-app-panel-strong px-4 py-4">
          <div className="text-[14px] font-medium text-app-text">总空间上限</div>
          <div className="mt-2 text-[14px] leading-6 text-app-muted">{formatBytes(knowledge.status.max_total_size_bytes)}</div>
        </div>
      </div>

      {knowledgeProgress != null ? (
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex min-w-[180px] items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-app-panel-strong">
              <div className="h-full rounded-full bg-app-accent transition-[width] duration-300" style={{ width: `${knowledgeProgress}%` }} />
            </div>
            <div className="w-10 text-right text-[12px] font-medium text-app-muted">{knowledgeProgress}%</div>
          </div>
        </div>
      ) : null}

      {knowledge.error ? <div className="text-[13px] leading-6 text-[#9d3d32]">{knowledge.error}</div> : null}

      {knowledge.updateResult ? (
        <button
          className="w-full rounded-xl border border-app-border bg-app-panel-strong px-4 py-3 text-left text-[13px] text-app-muted transition hover:bg-app-panel disabled:cursor-not-allowed disabled:opacity-60"
          disabled={knowledge.isUpdating}
          onClick={knowledge.onUpdate}
          type="button"
        >
          {knowledge.updateResult.started ? "已提交知识库更新" : "知识库状态"}: 排队{" "}
          {knowledge.updateResult.scheduled_documents} / 索引中 {knowledge.updateResult.indexing_documents} / 可用{" "}
          {knowledge.updateResult.ready_documents} / 失败 {knowledge.updateResult.failed_documents} / 分块{" "}
          {knowledge.updateResult.chunk_count}
        </button>
      ) : null}

      <div>
        <div className="mb-3 flex items-center gap-3">
          <div className="text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">知识文档</div>
          {knowledge.documents.length > 0 ? (
            <label className="inline-flex items-center">
              <input
                aria-label="全选知识库文档"
                checked={knowledge.isAllSelected}
                className="h-4 w-4 rounded border-app-border text-app-accent-strong focus:ring-app-accent-strong"
                onChange={knowledge.onSelectAll}
                type="checkbox"
              />
            </label>
          ) : null}
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          {knowledge.documents.map((document) => (
            <KnowledgeCard
              document={document}
              key={document.id}
              onDelete={knowledge.onDelete}
              onReindex={knowledge.onReindex}
              onSelect={knowledge.onSelectOne}
              selected={knowledge.selectedDocumentIds.includes(document.id)}
            />
          ))}
          {knowledge.documents.length === 0 ? (
            <EmptyState>先上传 `.md` 文档，再点“更新知识库”完成切分和索引。</EmptyState>
          ) : null}
        </div>
      </div>
    </WorkspacePage>
  );
}
