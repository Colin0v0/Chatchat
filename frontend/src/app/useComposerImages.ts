import { useCallback, useEffect, useRef, useState } from "react";

export interface ComposerImageDraft {
  id: string;
  file: File;
  previewUrl: string;
}

function revokePreviewUrls(images: ComposerImageDraft[]) {
  images.forEach((image) => URL.revokeObjectURL(image.previewUrl));
}

export function useComposerImages() {
  const [draftImages, setDraftImages] = useState<ComposerImageDraft[]>([]);
  const draftImagesRef = useRef<ComposerImageDraft[]>([]);

  useEffect(() => {
    draftImagesRef.current = draftImages;
  }, [draftImages]);

  const addImages = useCallback((files: FileList | File[]) => {
    const nextFiles = Array.from(files).filter((file) => file.type.startsWith("image/"));
    if (nextFiles.length === 0) {
      return;
    }

    setDraftImages((current) => [
      ...current,
      ...nextFiles.map((file) => ({
        id: crypto.randomUUID(),
        file,
        previewUrl: URL.createObjectURL(file),
      })),
    ]);
  }, []);

  const removeImage = useCallback((imageId: string) => {
    setDraftImages((current) => {
      const target = current.find((item) => item.id === imageId);
      if (target) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return current.filter((item) => item.id !== imageId);
    });
  }, []);

  const clearImages = useCallback(() => {
    setDraftImages((current) => {
      revokePreviewUrls(current);
      return [];
    });
  }, []);

  useEffect(() => {
    return () => {
      revokePreviewUrls(draftImagesRef.current);
    };
  }, []);

  return {
    addImages,
    clearImages,
    draftImages,
    removeImage,
  };
}
