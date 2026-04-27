import { useEffect, type ReactNode } from "react";

interface ConfirmDialogProps {
  cancelLabel?: string;
  confirmLabel?: string;
  description: ReactNode;
  disabled?: boolean;
  intent?: "default" | "danger";
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
  open: boolean;
  title: string;
}

export function ConfirmDialog({
  cancelLabel = "取消",
  confirmLabel = "确认",
  description,
  disabled = false,
  intent = "default",
  onCancel,
  onConfirm,
  open,
  title,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onCancel();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel, open]);

  if (!open) {
    return null;
  }

  const confirmClassName =
    intent === "danger"
      ? "bg-[#f7ebe8] text-[#9d3d32] hover:bg-[#f1dfdb]"
      : "bg-app-accent-soft text-app-accent-strong hover:bg-app-panel-soft";

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.18)] px-4"
      onClick={onCancel}
    >
      <div
        aria-modal="true"
        className="w-full max-w-[440px] rounded-[8px] border border-app-border bg-app-panel px-6 py-6 shadow-[0_24px_80px_rgba(34,24,16,0.18)]"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="text-[20px] font-semibold text-app-text">{title}</div>
        <div className="mt-3 text-[14px] leading-6 text-app-muted">{description}</div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            className="h-10 rounded-[8px] px-4 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={onCancel}
            type="button"
          >
            {cancelLabel}
          </button>
          <button
            className={`h-10 rounded-[8px] px-4 text-[14px] font-medium transition disabled:cursor-not-allowed disabled:opacity-55 ${confirmClassName}`}
            disabled={disabled}
            onClick={() => void onConfirm()}
            type="button"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
