import { sidebarMenuPanelClass } from "./styles";
import type { SidebarDialogState } from "./types";

interface SidebarDialogProps {
  state: SidebarDialogState;
  onCancel: () => void;
  onConfirmRename: () => void | Promise<void>;
  onConfirmDelete: () => void | Promise<void>;
  onRenameValueChange: (value: string) => void;
}

export function SidebarDialog({
  state,
  onCancel,
  onConfirmRename,
  onConfirmDelete,
  onRenameValueChange,
}: SidebarDialogProps) {
  if (!state) {
    return null;
  }

  const isRename = state.type === "rename";

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.18)] px-4" onClick={onCancel}>
      <div
        className="w-full max-w-[460px] rounded-[28px] border border-app-border bg-app-panel px-7 py-7 shadow-[0_24px_80px_rgba(34,24,16,0.18)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">
          {isRename ? "Rename chat" : "Delete chat"}
        </div>

        {isRename ? (
          <>
            <div className="mt-5 text-[14px] leading-7 text-app-muted">Give this chat a clearer title.</div>
            <input
              autoFocus
              className="mt-5 w-full rounded-2xl border border-app-border bg-app-panel-strong px-4 py-3 text-[16px] text-app-text outline-none transition focus:border-app-border-strong"
              onChange={(event) => onRenameValueChange(event.target.value)}
              value={state.value}
            />
          </>
        ) : (
          <div className="mt-5 text-[15px] leading-7 text-app-muted">
            Delete <span className="font-semibold text-app-text">{state.title}</span>? This cannot be undone.
          </div>
        )}

        <div className="mt-7 flex justify-end gap-3">
          <button
            className="rounded-xl px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button
            className={`rounded-xl px-4 py-2.5 text-[15px] font-medium transition ${
              isRename
                ? "bg-app-accent-soft text-app-accent-strong hover:bg-app-panel-soft"
                : "bg-[#f7ebe8] text-[#9d3d32] hover:bg-[#f1dfdb]"
            }`}
            onClick={isRename ? onConfirmRename : onConfirmDelete}
            type="button"
          >
            {isRename ? "Rename" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}