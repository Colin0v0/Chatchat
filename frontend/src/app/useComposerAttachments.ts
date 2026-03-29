import { useCallback, useEffect, useRef, useState } from "react";

export interface ComposerAttachmentDraft {
  id: string;
  file: File;
  kind: "image" | "file";
  previewUrl: string | null;
}

const SUPPORTED_ATTACHMENT_EXTENSIONS = new Set([
  ".jpg",
  ".jpeg",
  ".png",
  ".webp",
  ".gif",
  ".pdf",
  ".txt",
  ".md",
  ".markdown",
  ".py",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".json",
  ".html",
  ".htm",
  ".xml",
  ".yaml",
  ".yml",
  ".csv",
  ".xlsx",
  ".docx",
]);

function fileExtension(name: string) {
  const dotIndex = name.lastIndexOf(".");
  return dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : "";
}

function isSupportedAttachment(file: File) {
  const extension = fileExtension(file.name);
  if (SUPPORTED_ATTACHMENT_EXTENSIONS.has(extension)) {
    return true;
  }

  return file.type.startsWith("image/");
}

function toDraft(file: File): ComposerAttachmentDraft {
  const kind = file.type.startsWith("image/") ? "image" : "file";
  return {
    id: crypto.randomUUID(),
    file,
    kind,
    previewUrl: kind === "image" ? URL.createObjectURL(file) : null,
  };
}

function revokePreviewUrl(attachment: ComposerAttachmentDraft) {
  if (attachment.previewUrl) {
    URL.revokeObjectURL(attachment.previewUrl);
  }
}

function revokePreviewUrls(attachments: ComposerAttachmentDraft[]) {
  attachments.forEach(revokePreviewUrl);
}

export function useComposerAttachments() {
  const [draftAttachments, setDraftAttachments] = useState<ComposerAttachmentDraft[]>([]);
  const draftAttachmentsRef = useRef<ComposerAttachmentDraft[]>([]);

  useEffect(() => {
    draftAttachmentsRef.current = draftAttachments;
  }, [draftAttachments]);

  const addAttachments = useCallback((files: FileList | File[]) => {
    const nextFiles = Array.from(files).filter(isSupportedAttachment);
    if (nextFiles.length === 0) {
      return;
    }

    setDraftAttachments((current) => [...current, ...nextFiles.map(toDraft)]);
  }, []);

  const removeAttachment = useCallback((attachmentId: string) => {
    setDraftAttachments((current) => {
      const target = current.find((item) => item.id === attachmentId);
      if (target) {
        revokePreviewUrl(target);
      }
      return current.filter((item) => item.id !== attachmentId);
    });
  }, []);

  const clearAttachments = useCallback(() => {
    setDraftAttachments((current) => {
      revokePreviewUrls(current);
      return [];
    });
  }, []);

  const replaceAttachments = useCallback((files: File[]) => {
    const nextFiles = files.filter(isSupportedAttachment);
    setDraftAttachments((current) => {
      revokePreviewUrls(current);
      return nextFiles.map(toDraft);
    });
  }, []);

  useEffect(() => {
    return () => {
      revokePreviewUrls(draftAttachmentsRef.current);
    };
  }, []);

  return {
    addAttachments,
    clearAttachments,
    draftAttachments,
    removeAttachment,
    replaceAttachments,
  };
}
