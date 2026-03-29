import { X } from "lucide-react";

import type { ComposerImageDraft } from "../../app/useComposerImages";

interface ComposerImageStripProps {
  images: ComposerImageDraft[];
  onRemove: (imageId: string) => void;
}

export function ComposerImageStrip({ images, onRemove }: ComposerImageStripProps) {
  if (images.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2 border-b border-app-border px-4 py-3">
      {images.map((image) => (
        <div className="relative h-20 w-20 overflow-hidden rounded-[8px] bg-app-panel-soft" key={image.id}>
          <img alt={image.file.name} className="h-full w-full object-cover" src={image.previewUrl} />
          <button
            aria-label="Remove image"
            className="absolute top-1.5 right-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-[rgba(18,16,14,0.72)] text-white transition hover:bg-[rgba(18,16,14,0.82)]"
            onClick={() => onRemove(image.id)}
            type="button"
          >
            <X className="size-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
