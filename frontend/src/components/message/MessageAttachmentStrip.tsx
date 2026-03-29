import { FileText } from "lucide-react";

import type { MessageAttachment } from "../../types";
import { toApiUrl } from "../../lib/api";

interface MessageAttachmentStripProps {
  attachments: MessageAttachment[];
  align?: "start" | "end";
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

export function MessageAttachmentStrip({
  attachments,
  align = "start",
}: MessageAttachmentStripProps) {
  if (attachments.length === 0) {
    return null;
  }

  const imageAttachments = attachments.filter((attachment) => attachment.kind === "image");
  const fileAttachments = attachments.filter((attachment) => attachment.kind === "file");

  return (
    <div className={`mb-2 flex flex-col gap-2 ${align === "end" ? "items-end" : "items-start"}`}>
      {imageAttachments.length > 0 ? (
        <div
          className={`grid gap-2 ${imageAttachments.length === 1 ? "grid-cols-1" : "grid-cols-2"} max-w-[360px]`}
        >
          {imageAttachments.map((attachment) => (
            <a
              className="block overflow-hidden rounded-[12px] bg-app-panel-soft"
              href={toApiUrl(attachment.url)}
              key={attachment.id}
              rel="noreferrer"
              target="_blank"
            >
              <img
                alt={attachment.original_name}
                className="h-full max-h-[260px] w-full object-cover"
                src={toApiUrl(attachment.url)}
              />
            </a>
          ))}
        </div>
      ) : null}

      {fileAttachments.map((attachment) => (
        <a
          className="flex max-w-[360px] items-center gap-3 rounded-[18px] bg-app-panel-soft px-3 py-2.5 text-left transition hover:text-app-accent-strong"
          href={toApiUrl(attachment.url)}
          key={attachment.id}
          rel="noreferrer"
          target="_blank"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-app-panel-strong text-app-muted">
            <FileText className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-[14px] font-medium text-app-text">
              {attachment.original_name}
            </div>
            <div className="mt-0.5 text-[12px] text-app-muted">
              {(attachment.extension || attachment.mime_type || "file").replace(/^\./, "").toUpperCase()}
              {" · "}
              {formatFileSize(attachment.size_bytes)}
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}
