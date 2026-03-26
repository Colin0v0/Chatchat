import { ChatComposer } from "./ChatComposer";
import type { ModelOption } from "../types";

interface LandingViewProps {
  draft: string;
  isStreaming: boolean;
  model: string;
  models: ModelOption[];
  ragEnabled: boolean;
  thinkingEnabled: boolean;
  thinkingAvailable: boolean;
  onChangeDraft: (value: string) => void;
  onModelChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onToggleRag: () => void;
  onToggleThinking: () => void;
}

export function LandingView({
  draft,
  isStreaming,
  model,
  models,
  ragEnabled,
  thinkingEnabled,
  thinkingAvailable,
  onChangeDraft,
  onModelChange,
  onSend,
  onStop,
  onToggleRag,
  onToggleThinking,
}: LandingViewProps) {
  return (
    <section className="flex flex-1 flex-col px-4 pb-2 pt-6 md:px-6 md:pb-2 md:pt-8">
      <div className="mx-auto flex h-full w-full max-w-[920px] flex-col">
        <div className="flex flex-1 items-center justify-center">
          <h1 className="text-center text-[36px] font-semibold leading-none tracking-[-0.06em] md:text-[56px]">
            今天想让模型帮你做什么？
          </h1>
        </div>

        <div className="pt-3">
          <ChatComposer
            centered={false}
            isStreaming={isStreaming}
            model={model}
            models={models}
            onChange={onChangeDraft}
            onModelChange={onModelChange}
            onStop={onStop}
            onSubmit={onSend}
            onToggleRag={onToggleRag}
            onToggleThinking={onToggleThinking}
            ragEnabled={ragEnabled}
            thinkingEnabled={thinkingEnabled}
            thinkingAvailable={thinkingAvailable}
            value={draft}
          />
        </div>
      </div>
    </section>
  );
}
