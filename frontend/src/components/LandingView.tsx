import { useEffect, useMemo, useState } from "react";

import type { ComposerImageDraft } from "../app/useComposerImages";
import type { ModelOption } from "../types";
import { ChatComposer } from "./ChatComposer";

const BASE_TYPEWRITER_MS = 42;
const ENDING_SLOWDOWN_MS = 56;
const PUNCTUATION_PAUSE_MS = 180;
const PUNCTUATION = new Set(["£¬", "¡£", "£¿", "£¡", "£º", "£»", ",", ".", "?", "!", ":", ";"]);

interface LandingViewProps {
  draft: string;
  draftImages: ComposerImageDraft[];
  imageUploadAvailable: boolean;
  isStreaming: boolean;
  model: string;
  models: ModelOption[];
  ragEnabled: boolean;
  webEnabled: boolean;
  thinkingEnabled: boolean;
  thinkingAvailable: boolean;
  shouldAnimate: boolean;
  title: string;
  onAnimationComplete: () => void;
  onChangeDraft: (value: string) => void;
  onModelChange: (value: string) => void;
  onRemoveDraftImage: (imageId: string) => void;
  onSelectImages: (files: FileList | File[]) => void;
  onSend: () => void;
  onStop: () => void;
  onToggleRag: () => void;
  onToggleWeb: () => void;
  onToggleThinking: () => void;
}

function getTypewriterDelay(title: string, index: number) {
  const progress = index / Math.max(title.length - 1, 1);
  const slowdown = ENDING_SLOWDOWN_MS * progress;
  const nextChar = title[index] ?? "";
  return BASE_TYPEWRITER_MS + slowdown + (PUNCTUATION.has(nextChar) ? PUNCTUATION_PAUSE_MS : 0);
}

export function LandingView({
  draft,
  draftImages,
  imageUploadAvailable,
  isStreaming,
  model,
  models,
  ragEnabled,
  webEnabled,
  thinkingEnabled,
  thinkingAvailable,
  shouldAnimate,
  title,
  onAnimationComplete,
  onChangeDraft,
  onModelChange,
  onRemoveDraftImage,
  onSelectImages,
  onSend,
  onStop,
  onToggleRag,
  onToggleWeb,
  onToggleThinking,
}: LandingViewProps) {
  const [visibleCount, setVisibleCount] = useState(() => (shouldAnimate ? 0 : title.length));

  useEffect(() => {
    if (!shouldAnimate) {
      setVisibleCount(title.length);
      return;
    }

    setVisibleCount(0);
  }, [shouldAnimate, title]);

  useEffect(() => {
    if (!shouldAnimate) {
      return;
    }

    if (visibleCount >= title.length) {
      onAnimationComplete();
      return;
    }

    const timer = window.setTimeout(() => {
      setVisibleCount((current) => current + 1);
    }, getTypewriterDelay(title, visibleCount));

    return () => window.clearTimeout(timer);
  }, [onAnimationComplete, shouldAnimate, title, visibleCount]);

  const visibleTitle = useMemo(() => title.slice(0, visibleCount), [title, visibleCount]);
  const showCaret = shouldAnimate && visibleCount < title.length;

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden px-4 pb-2 pt-6 md:px-6 md:pb-2 md:pt-8">
      <div className="mx-auto flex min-h-0 h-full w-full max-w-[920px] flex-col">
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <h1 className="text-center text-[36px] font-semibold leading-none tracking-[-0.06em] md:text-[56px]">
            <span>{visibleTitle}</span>
            {showCaret ? (
              <span className="ml-1 inline-block h-[0.92em] w-[0.08em] translate-y-[0.06em] animate-pulse bg-current align-baseline" />
            ) : null}
          </h1>
        </div>

        <div className="shrink-0 pt-3">
          <ChatComposer
            centered={false}
            imageUploadAvailable={imageUploadAvailable}
            images={draftImages}
            isStreaming={isStreaming}
            model={model}
            models={models}
            onChange={onChangeDraft}
            onModelChange={onModelChange}
            onRemoveImage={onRemoveDraftImage}
            onSelectImages={onSelectImages}
            onStop={onStop}
            onSubmit={onSend}
            onToggleRag={onToggleRag}
            onToggleThinking={onToggleThinking}
            onToggleWeb={onToggleWeb}
            ragEnabled={ragEnabled}
            thinkingAvailable={thinkingAvailable}
            thinkingEnabled={thinkingEnabled}
            value={draft}
            webEnabled={webEnabled}
          />
        </div>
      </div>
    </section>
  );
}
