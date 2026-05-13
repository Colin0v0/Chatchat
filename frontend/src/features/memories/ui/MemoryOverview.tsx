interface MemoryOverviewProps {
  conversationCount: number;
  documentCount: number;
  globalCount: number;
  workingCount: number;
}

function OverviewCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3">
      <div className="text-[12px] font-medium text-app-muted">{label}</div>
      <div className="mt-2 text-[24px] font-semibold leading-none text-app-text">{value}</div>
    </div>
  );
}

export function MemoryOverview({
  conversationCount,
  documentCount,
  globalCount,
  workingCount,
}: MemoryOverviewProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <OverviewCard label="长期记忆" value={String(globalCount)} />
      <OverviewCard label="会话记忆" value={String(conversationCount)} />
      <OverviewCard label="工作记忆" value={String(workingCount)} />
      <OverviewCard label="画像文档" value={String(documentCount)} />
    </div>
  );
}
