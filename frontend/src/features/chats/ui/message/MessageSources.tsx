import type { MessageSource } from "../../../../types";
import { MessageSourceItem } from "./MessageSourceItem";
import { groupSources } from "./sourceUtils";

interface MessageSourcesProps {
  sources: MessageSource[];
}

export function MessageSources({ sources }: MessageSourcesProps) {
  if (sources.length === 0) {
    return null;
  }

  const groups = groupSources(sources);
  return (
    <section className="mt-4 space-y-3 text-[12px] leading-5 text-app-muted/90">
      <div className="font-medium tracking-[0.03em] text-app-muted/80">Sources</div>
      {groups.map((group) => (
        <div className="space-y-2" key={group.key}>
          <div className="text-[12px] font-medium tracking-[0.04em] text-app-muted/70">{group.label}</div>
          <div className="space-y-2">
            {group.items.map((source, index) => (
              <MessageSourceItem
                key={`${group.key}-${source.url || source.path}-${source.heading}-${index}`}
                source={source}
              />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
