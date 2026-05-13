import { Plus, RefreshCw } from "lucide-react";
import { useState } from "react";

import type { MemoryDocument, MemoryItem } from "../../../types";
import { WorkspacePage } from "../../../shared/ui/WorkspacePage";
import type { MemoryEditorState } from "../model/useMemoryManager";
import { MemoryDocumentCard, MemoryEmptyState } from "./MemoryCard";
import { MemoryEditorPanel } from "./MemoryEditorPanel";
import { MemoryInventoryPanel, type MemoryInventoryTab } from "./MemoryInventoryPanel";
import { MemoryOverview } from "./MemoryOverview";

type MemoriesPageProps = {
  activeConversationId: number | null;
  activeConversationTitle: string;
  memories: {
    collection: {
      documents: MemoryDocument[];
      active_items: {
        global_items: MemoryItem[];
        conversation_items: MemoryItem[];
        working_items: MemoryItem[];
      };
    };
    editor: MemoryEditorState;
    error: string | null;
    hasMemories: boolean;
    isLoading: boolean;
    isSaving: boolean;
    onCancelEditing: () => void;
    onChangeEditor: (patch: Record<string, unknown>) => void;
    onCreateGlobalMemory: () => void;
    onDeleteMemory: (memoryId: number) => void;
    onEditMemory: (memory: MemoryItem) => void;
    onRefresh: () => void;
    onSaveEditing: () => void;
  };
};

function DocumentsPanel({ documents }: { documents: MemoryDocument[] }) {
  return (
    <section className="min-w-0 rounded-[8px] border border-app-border bg-app-panel p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-[15px] font-semibold text-app-text">画像文档</div>
          <div className="mt-1 text-[13px] text-app-muted">由生效记忆自动整理</div>
        </div>
        <div className="rounded-[8px] bg-app-panel-strong px-2 py-1 text-[12px] font-medium text-app-muted">{documents.length}</div>
      </div>
      <div className="grid gap-3">
        {documents.map((document) => (
          <MemoryDocumentCard document={document} key={document.id} />
        ))}
        {documents.length === 0 ? <MemoryEmptyState>还没有画像文档。</MemoryEmptyState> : null}
      </div>
    </section>
  );
}

export function MemoriesPage({
  activeConversationId: _activeConversationId,
  activeConversationTitle: _activeConversationTitle,
  memories,
}: MemoriesPageProps) {
  const [activeTab, setActiveTab] = useState<MemoryInventoryTab>("global");
  const activeGlobal = memories.collection.active_items.global_items;
  const activeConversation = memories.collection.active_items.conversation_items;
  const activeWorking = memories.collection.active_items.working_items;

  return (
    <WorkspacePage
      headerPlacement="content"
      maxWidthClassName="max-w-[1400px]"
      actions={
        <div className="flex items-center justify-end gap-2">
          <button
            className="flex h-10 w-10 items-center justify-center rounded-[8px] border border-app-border bg-app-panel-strong text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={memories.onRefresh}
            title="刷新"
            type="button"
          >
            <RefreshCw className={`size-4 ${memories.isLoading ? "animate-spin" : ""}`} />
          </button>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 whitespace-nowrap rounded-[8px] bg-app-accent-soft px-4 text-[14px] font-medium text-app-accent-strong transition hover:bg-[#e7ddcf]"
            onClick={memories.onCreateGlobalMemory}
            type="button"
          >
            <Plus className="size-4" />
            新建长期记忆
          </button>
        </div>
      }
      title="Memories"
    >
      <MemoryOverview
        conversationCount={activeConversation.length}
        documentCount={memories.collection.documents.length}
        globalCount={activeGlobal.length}
        workingCount={activeWorking.length}
      />

      {memories.error ? (
        <div className="rounded-[8px] border border-[#f0d0ca] bg-[#fbefed] px-4 py-3 text-[13px] leading-6 text-[#9d3d32]">
          {memories.error}
        </div>
      ) : null}

      {memories.editor ? (
        <MemoryEditorPanel
          editor={memories.editor}
          isSaving={memories.isSaving}
          onCancel={memories.onCancelEditing}
          onChange={memories.onChangeEditor}
          onSave={memories.onSaveEditing}
        />
      ) : null}

      <section className="grid min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 rounded-[8px] border border-app-border bg-app-panel p-4">
          <MemoryInventoryPanel
            activeTab={activeTab}
            conversationItems={activeConversation}
            globalItems={activeGlobal}
            onDeleteMemory={memories.onDeleteMemory}
            onEditMemory={memories.onEditMemory}
            onTabChange={setActiveTab}
            workingItems={activeWorking}
          />
        </div>

        <div className="min-w-0">
          <DocumentsPanel documents={memories.collection.documents} />
        </div>
      </section>
    </WorkspacePage>
  );
}
