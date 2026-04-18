import { useEffect, useMemo, useState } from "react";

import type { ComposerAttachmentDraft } from "../model/useComposerAttachments";
import type { ModelOption, ReasoningProfileValue, ToolMode } from "../../../types";
import { ChatComposer } from "./ChatComposer";

const BASE_TYPEWRITER_MS = 42;
const ENDING_SLOWDOWN_MS = 56;
const PUNCTUATION_PAUSE_MS = 180;
const PUNCTUATION = new Set(["，", "。", "？", "！", "：", "；", ",", ".", "?", "!", ":", ";"]);

interface LandingViewProps {
  draft: string;
  draftAttachments: ComposerAttachmentDraft[];
  attachmentUploadAvailable: boolean;
  isRecording: boolean;
  isStreaming: boolean;
  isTranscribing: boolean;
  model: string;
  models: ModelOption[];
  reasoningProfile: ReasoningProfileValue;
  toolMode: ToolMode;
  submitBlocked: boolean;
  submitBlockedReason: string | null;
  shouldAnimate: boolean;
  title: string;
  onAnimationComplete: () => void;
  onChangeDraft: (value: string) => void;
  onModelChange: (value: string) => void;
  onReasoningProfileChange: (value: ReasoningProfileValue) => void;
  onRemoveDraftAttachment: (attachmentId: string) => void;
  onSelectAttachments: (files: FileList | File[]) => void;
  onSend: () => void;
  onStop: () => void;
  onToggleRecording: () => void;
  onToggleRag: () => void;
  onToggleWeb: () => void;
}

function getTypewriterDelay(title: string, index: number) {
  const progress = index / Math.max(title.length - 1, 1);
  const slowdown = ENDING_SLOWDOWN_MS * progress;
  const nextChar = title[index] ?? "";
  return BASE_TYPEWRITER_MS + slowdown + (PUNCTUATION.has(nextChar) ? PUNCTUATION_PAUSE_MS : 0);
}

export function LandingView({
  draft,
  draftAttachments,
  attachmentUploadAvailable,
  isRecording,
  isStreaming,
  isTranscribing,
  model,
  models,
  reasoningProfile,
  toolMode,
  submitBlocked,
  submitBlockedReason,
  shouldAnimate,
  title,
  onAnimationComplete,
  onChangeDraft,
  onModelChange,
  onReasoningProfileChange,
  onRemoveDraftAttachment,
  onSelectAttachments,
  onSend,
  onStop,
  onToggleRecording,
  onToggleRag,
  onToggleWeb,
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
    <section className="flex min-h-0 flex-1 flex-col pb-1">
      <div className="flex min-h-0 flex-1 overflow-hidden pt-4">
        <div className="mx-auto flex min-h-0 w-full max-w-[920px] items-center justify-center px-4 md:px-6">
          <h1 className="text-center text-[36px] font-semibold leading-none tracking-[-0.06em] md:text-[56px]">
            <span>{visibleTitle}</span>
            {showCaret ? (
              <span className="ml-1 inline-block h-[0.92em] w-[0.08em] translate-y-[0.06em] animate-pulse bg-current align-baseline" />
            ) : null}
          </h1>
        </div>
      </div>

      <div className="mx-auto w-full max-w-[920px] px-4 pt-2 md:px-6">
        <ChatComposer
          centered={false}
          attachmentUploadAvailable={attachmentUploadAvailable}
          attachments={draftAttachments}
          isRecording={isRecording}
          isStreaming={isStreaming}
          isTranscribing={isTranscribing}
          model={model}
          models={models}
          onChange={onChangeDraft}
          onModelChange={onModelChange}
          onReasoningProfileChange={onReasoningProfileChange}
          onRemoveAttachment={onRemoveDraftAttachment}
          onSelectAttachments={onSelectAttachments}
          onStop={onStop}
          onSubmit={onSend}
          onToggleRecording={onToggleRecording}
          onToggleRag={onToggleRag}
          onToggleWeb={onToggleWeb}
          reasoningProfile={reasoningProfile}
          toolMode={toolMode}
          submitBlocked={submitBlocked}
          submitBlockedReason={submitBlockedReason}
          value={draft}
        />
      </div>
    </section>
  );
}
