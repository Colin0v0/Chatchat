import type { MessageAttachment } from "../../types";
import { toApiUrl } from "../../lib/api";

interface MessageImageStripProps {
  attachments: MessageAttachment[];
  align?: "start" | "end";
}

export function MessageImageStrip({ attachments, align = "start" }: MessageImageStripProps) {
  if (attachments.length === 0) {
    return null;
  }

  return (
    <div className={`mb-2 flex ${align === "end" ? "justify-end" : "justify-start"}`}>
      <div className={`grid gap-2 ${attachments.length === 1 ? "grid-cols-1" : "grid-cols-2"} max-w-[360px]`}>
        {attachments.map((attachment) => (
          <a
            className="block overflow-hidden rounded-[12px] bg-app-panel-soft"
            href={toApiUrl(attachment.url)}
            key={attachment.id}
            rel="noreferrer"
            target="_blank"
          >
            <img alt={attachment.original_name} className="h-full max-h-[260px] w-full object-cover" src={toApiUrl(attachment.url)} />
          </a>
        ))}
      </div>
    </div>
  );
}
