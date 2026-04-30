import { useCallback, useEffect, useMemo, useState } from "react";

import type {
  MemoryCollection,
  MemoryItem,
  MemoryKind,
  MemoryScope,
  MemoryUpsertPayload,
} from "../../../types";
import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import {
  createMemory,
  deleteMemory,
  fetchMemories,
  updateMemory,
} from "../api/memories";

type EditableScope = Exclude<MemoryScope, "working">;

type MemoryEditorState = {
  id: number | null;
  scope: EditableScope;
  kind: MemoryKind;
  title: string;
  detail: string;
  tagsText: string;
  confidenceText: string;
  pinned: boolean;
  active: boolean;
  conversation_id: number | null;
};

function createEmptyCollection(): MemoryCollection {
  return {
    documents: [],
    active_items: {
      global_items: [],
      conversation_items: [],
      working_items: [],
    },
  };
}

function createEditor(
  conversationId: number | null,
  scope: EditableScope,
  memory?: MemoryItem,
): MemoryEditorState {
  if (memory) {
    return {
      id: memory.id,
      scope: memory.scope === "global" ? "global" : "conversation",
      kind: memory.kind,
      title: memory.title,
      detail: memory.detail,
      tagsText: memory.tags.join(", "),
      confidenceText: String(memory.confidence),
      pinned: memory.pinned,
      active: memory.active,
      conversation_id: memory.conversation_id,
    };
  }

  return {
    id: null,
    scope,
    kind: "fact",
    title: "",
    detail: "",
    tagsText: "",
    confidenceText: "0.7",
    pinned: false,
    active: true,
    conversation_id: scope === "conversation" ? conversationId : null,
  };
}

function parseTags(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toPayload(editor: MemoryEditorState): MemoryUpsertPayload {
  const confidence = Number(editor.confidenceText);
  return {
    scope: editor.scope,
    kind: editor.kind,
    title: editor.title.trim(),
    detail: editor.detail.trim(),
    tags: parseTags(editor.tagsText),
    confidence: Number.isFinite(confidence) ? Math.max(0, Math.min(1, confidence)) : 0.7,
    pinned: editor.pinned,
    active: editor.active,
    conversation_id: editor.scope === "conversation" ? editor.conversation_id : null,
  };
}

export function useMemoryManager({
  activeConversationId,
  enabled,
}: {
  activeConversationId: number | null;
  enabled: boolean;
}) {
  const [collection, setCollection] = useState<MemoryCollection>(createEmptyCollection);
  const [editor, setEditor] = useState<MemoryEditorState | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadGuard = useLatestRequestGuard();

  const loadMemories = useCallback(async () => {
    const requestId = loadGuard.begin();
    setIsLoading(true);
    setError(null);
    try {
      const nextCollection = await fetchMemories(activeConversationId);
      if (!loadGuard.isCurrent(requestId)) {
        return;
      }
      setCollection(nextCollection);
    } catch (loadError) {
      if (loadGuard.isCurrent(requestId)) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load memory workspace.");
      }
    } finally {
      if (loadGuard.isCurrent(requestId)) {
        setIsLoading(false);
      }
    }
  }, [activeConversationId, loadGuard]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void loadMemories();
  }, [enabled, loadMemories]);

  useEffect(() => {
    if (!editor || editor.scope !== "conversation") {
      return;
    }
    setEditor((current) =>
      current
        ? {
            ...current,
            conversation_id: activeConversationId,
          }
        : current,
    );
  }, [activeConversationId, editor]);

  const startCreate = useCallback(
    (scope: EditableScope) => {
      setEditor(createEditor(activeConversationId, scope));
    },
    [activeConversationId],
  );

  const startEdit = useCallback(
    (memory: MemoryItem) => {
      if (memory.scope === "working") {
        return;
      }
      setEditor(createEditor(activeConversationId, memory.scope === "global" ? "global" : "conversation", memory));
    },
    [activeConversationId],
  );

  const cancelEditing = useCallback(() => {
    setEditor(null);
  }, []);

  const saveEditing = useCallback(async () => {
    if (!editor) {
      return;
    }

    const payload = toPayload(editor);
    if (!payload.title) {
      setError("Memory title cannot be empty.");
      return;
    }
    if (payload.scope === "conversation" && payload.conversation_id == null) {
      setError("Select a conversation before creating conversation memory.");
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      if (editor.id == null) {
        await createMemory(payload);
      } else {
        await updateMemory(editor.id, payload);
      }
      setEditor(null);
      await loadMemories();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save memory.");
    } finally {
      setIsSaving(false);
    }
  }, [editor, loadMemories]);

  const removeMemory = useCallback(
    async (memoryId: number) => {
      setIsSaving(true);
      setError(null);
      try {
        await deleteMemory(memoryId);
        if (editor?.id === memoryId) {
          setEditor(null);
        }
        await loadMemories();
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Failed to delete memory.");
      } finally {
        setIsSaving(false);
      }
    },
    [editor?.id, loadMemories],
  );

  const hasMemories =
    collection.documents.length > 0 ||
    collection.active_items.global_items.length > 0 ||
    collection.active_items.conversation_items.length > 0 ||
    collection.active_items.working_items.length > 0;

  return useMemo(
    () => ({
      collection,
      editor,
      error,
      hasMemories,
      isLoading,
      isSaving,
      onCancelEditing: cancelEditing,
      onChangeEditor: (patch: Record<string, unknown>) =>
        setEditor((current) => (current ? { ...current, ...patch } : current)),
      onCreateGlobalMemory: () => startCreate("global"),
      onDeleteMemory: (memoryId: number) => void removeMemory(memoryId),
      onEditMemory: (memory: MemoryItem) => startEdit(memory),
      onRefresh: () => void loadMemories(),
      onSaveEditing: () => void saveEditing(),
    }),
    [
      cancelEditing,
      collection,
      editor,
      error,
      hasMemories,
      isLoading,
      isSaving,
      loadMemories,
      removeMemory,
      saveEditing,
      startCreate,
      startEdit,
    ],
  );
}
