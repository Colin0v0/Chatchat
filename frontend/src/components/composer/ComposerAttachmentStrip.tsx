import { FileText, X } from "lucide-react";

import type { ComposerAttachmentDraft } from "../../app/useComposerAttachments";

interface ComposerAttachmentStripProps {
  attachments: ComposerAttachmentDraft[];
  onRemove: (attachmentId: string) => void;
}

function formatFileSize(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${size} B`;
}

export function ComposerAttachmentStrip({ attachments, onRemove }: ComposerAttachmentStripProps) {
  if (attachments.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2 border-b border-app-border px-4 py-3">
      {attachments.map((attachment) => (
        <div
          className="relative min-w-0 overflow-hidden rounded-[10px] border border-app-border bg-app-panel-soft"
          key={attachment.id}
        >
          {attachment.kind === "image" && attachment.previewUrl ? (
            <div className="relative h-20 w-20 overflow-hidden bg-app-panel-soft">
              <img
                alt={attachment.file.name}
                className="h-full w-full object-cover"
                src={attachment.previewUrl}
              />
            </div>
          ) : (
            <div className="flex min-w-[220px] max-w-[280px] items-center gap-3 px-3 py-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-app-panel-strong text-app-muted">
                <FileText className="size-4" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-[14px] font-medium text-app-text">
                  {attachment.file.name}
                </div>
                <div className="mt-0.5 text-[12px] text-app-muted">
                  {formatFileSize(attachment.file.size)}
                </div>
              </div>
            </div>
          )}

          <button
            aria-label="Remove attachment"
            className="absolute top-1.5 right-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-[rgba(18,16,14,0.72)] text-white transition hover:bg-[rgba(18,16,14,0.82)]"
            onClick={() => onRemove(attachment.id)}
            type="button"
          >
            <X className="size-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
