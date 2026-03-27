import { useEffect } from "react";

import type { RagReindexResult } from "../types";

interface SettingsDialogProps {
  open: boolean;
  isUpdating: boolean;
  updateError: string | null;
  updateResult: RagReindexResult | null;
  onClose: () => void;
  onUpdateDatabase: () => void;
}

export function SettingsDialog({
  open,
  isUpdating,
  updateError,
  updateResult,
  onClose,
  onUpdateDatabase,
}: SettingsDialogProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.18)] px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-[460px] rounded-[28px] border border-app-border bg-app-panel px-7 py-7 shadow-[0_24px_80px_rgba(34,24,16,0.18)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">Settings</div>
        <div className="mt-5 text-[14px] leading-7 text-app-muted">
          Rebuild RAG database from Obsidian markdown files. This will re-split sections and regenerate embeddings.
        </div>

        <div className="mt-6">
          <button
            className="rounded-xl bg-app-accent-soft px-4 py-2.5 text-[15px] font-medium text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isUpdating}
            onClick={onUpdateDatabase}
            type="button"
          >
            {isUpdating ? "Updating..." : "Update Database"}
          </button>
        </div>

        {updateResult ? (
          <div className="mt-4 text-[13px] leading-6 text-app-muted">
            Files: {updateResult.indexed_files} | Chunks: {updateResult.indexed_chunks} | Failed:{" "}
            {updateResult.failed_chunks}
          </div>
        ) : null}

        {updateError ? <div className="mt-3 text-[13px] leading-6 text-[#9d3d32]">{updateError}</div> : null}

        <div className="mt-6 rounded-2xl border border-app-border bg-app-panel-strong px-4 py-3 text-[13px] leading-6 text-app-muted">
          RAG 过滤语法：
          <br />
          <span className="text-app-text">folder:daily tag:project path:notes/roadmap</span>
          <br />
          直接写在问题里，例如：
          <br />
          <span className="text-app-text">folder:ai tag:agent 这个方案怎么拆</span>
        </div>

        <div className="mt-7 flex justify-end">
          <button
            className="rounded-xl px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
