import { useCallback, useEffect, useMemo, useState } from "react";

import type { KnowledgeDocument, KnowledgeReindexResult, KnowledgeStatus } from "../../../types";
import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import {
  createKnowledgeFolder,
  deleteKnowledgeDocument,
  deleteKnowledgeDocuments,
  deleteKnowledgeFolder,
  fetchKnowledgeDocuments,
  fetchKnowledgeFolders,
  fetchKnowledgeStatus,
  moveKnowledgeDocuments,
  reindexKnowledgeDocument,
  reindexKnowledgeDocuments,
  renameKnowledgeFolder,
  uploadKnowledgeDocuments,
} from "../api/knowledge";

function createEmptyStatus(): KnowledgeStatus {
  return {
    document_count: 0,
    pending_document_count: 0,
    indexing_document_count: 0,
    ready_document_count: 0,
    failed_document_count: 0,
    chunk_count: 0,
    total_size_bytes: 0,
    max_documents_per_user: 0,
    max_total_size_bytes: 0,
    max_file_size_bytes: 0,
  };
}

export function useKnowledgeManager({ enabled, projectId }: { enabled: boolean; projectId?: number | null }) {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [status, setStatus] = useState<KnowledgeStatus>(createEmptyStatus);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [savedFolders, setSavedFolders] = useState<string[]>([]);
  const [updateResult, setUpdateResult] = useState<KnowledgeReindexResult | null>(null);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
  const loadGuard = useLatestRequestGuard();

  const loadKnowledge = useCallback(async () => {
    const requestId = loadGuard.begin();
    setIsLoading(true);
    setError(null);
    try {
      const [nextDocuments, nextStatus, nextFolders] = await Promise.all([
        fetchKnowledgeDocuments(projectId),
        fetchKnowledgeStatus(projectId),
        fetchKnowledgeFolders(projectId),
      ]);
      if (!loadGuard.isCurrent(requestId)) {
        return;
      }
      setDocuments(nextDocuments);
      setStatus(nextStatus);
      setSavedFolders(nextFolders);
      setSelectedDocumentIds((current) =>
        current.filter((documentId) => nextDocuments.some((document) => document.id === documentId)),
      );
    } catch (loadError) {
      if (loadGuard.isCurrent(requestId)) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load knowledge documents.");
      }
    } finally {
      if (loadGuard.isCurrent(requestId)) {
        setIsLoading(false);
      }
    }
  }, [loadGuard, projectId]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void loadKnowledge();
  }, [enabled, loadKnowledge]);

  useEffect(() => {
    if (!enabled || status.indexing_document_count === 0) {
      return;
    }

    const timer = window.setInterval(() => {
      void loadKnowledge();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [enabled, loadKnowledge, status.indexing_document_count]);

  const folders = useMemo(() => {
    const unique = new Set<string>(savedFolders);
    documents.forEach((document) => {
      const folder = (document.folder ?? "").trim();
      if (folder) {
        unique.add(folder);
      }
    });
    return Array.from(unique).sort((left, right) => left.localeCompare(right, "zh-CN"));
  }, [documents, savedFolders]);

  const createFolder = useCallback(
    async (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) {
        return null;
      }
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        const folder = await createKnowledgeFolder(trimmed, projectId);
        setSavedFolders((current) =>
          Array.from(new Set([...current, folder])).sort((left, right) => left.localeCompare(right, "zh-CN")),
        );
        return folder;
      } catch (createError) {
        setError(createError instanceof Error ? createError.message : "Failed to create knowledge folder.");
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [projectId],
  );

  const removeFolder = useCallback(
    async (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) {
        return false;
      }
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        await deleteKnowledgeFolder(trimmed, projectId);
        setSavedFolders((current) => current.filter((folder) => folder !== trimmed));
        setSelectedDocumentIds([]);
        await loadKnowledge();
        return true;
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Failed to delete knowledge folder.");
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge, projectId],
  );

  const renameFolder = useCallback(
    async (name: string, newName: string) => {
      const trimmed = name.trim();
      const nextName = newName.trim();
      if (!trimmed || !nextName) {
        return null;
      }
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        const renamedFolder = await renameKnowledgeFolder(trimmed, nextName, projectId);
        setSavedFolders((current) =>
          Array.from(
            new Set(current.map((folder) => (folder === trimmed ? renamedFolder : folder)).concat(renamedFolder)),
          ).sort((left, right) => left.localeCompare(right, "zh-CN")),
        );
        await loadKnowledge();
        return renamedFolder;
      } catch (renameError) {
        setError(renameError instanceof Error ? renameError.message : String(renameError));
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge, projectId],
  );

  const uploadDocuments = useCallback(
    async (files: File[], folder = "", relativePaths: string[] = []) => {
      if (files.length === 0) {
        return;
      }
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        await uploadKnowledgeDocuments(files, { folder, projectId, relativePaths });
        await loadKnowledge();
      } catch (uploadError) {
        setError(uploadError instanceof Error ? uploadError.message : "Failed to upload knowledge documents.");
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge, projectId],
  );

  const moveSelectedDocuments = useCallback(
    async (folder: string) => {
      if (selectedDocumentIds.length === 0) {
        return;
      }
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        await moveKnowledgeDocuments(selectedDocumentIds, folder, projectId);
        setSelectedDocumentIds([]);
        await loadKnowledge();
      } catch (moveError) {
        setError(moveError instanceof Error ? moveError.message : "Failed to move knowledge documents.");
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge, projectId, selectedDocumentIds],
  );

  const reindexDocument = useCallback(
    async (documentId: number) => {
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        await reindexKnowledgeDocument(documentId, projectId);
        await loadKnowledge();
      } catch (reindexError) {
        setError(reindexError instanceof Error ? reindexError.message : "Failed to reindex knowledge document.");
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge, projectId],
  );

  const removeDocument = useCallback(
    async (documentId: number) => {
      setIsSaving(true);
      setError(null);
      setUpdateResult(null);
      try {
        await deleteKnowledgeDocument(documentId, projectId);
        await loadKnowledge();
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Failed to delete knowledge document.");
      } finally {
        setIsSaving(false);
      }
    },
    [loadKnowledge, projectId],
  );

  const removeSelectedDocuments = useCallback(async () => {
    if (selectedDocumentIds.length === 0) {
      return;
    }
    setIsSaving(true);
    setError(null);
    setUpdateResult(null);
    try {
      if (selectedDocumentIds.length === 1) {
        await deleteKnowledgeDocument(selectedDocumentIds[0], projectId);
      } else {
        await deleteKnowledgeDocuments(selectedDocumentIds, projectId);
      }
      setSelectedDocumentIds([]);
      await loadKnowledge();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete knowledge documents.");
    } finally {
      setIsSaving(false);
    }
  }, [loadKnowledge, projectId, selectedDocumentIds]);

  const updateKnowledge = useCallback(async () => {
    setIsUpdating(true);
    setError(null);
    try {
      const result = await reindexKnowledgeDocuments(projectId);
      setUpdateResult(result);
      await loadKnowledge();
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Failed to update knowledge base.");
    } finally {
      setIsUpdating(false);
    }
  }, [loadKnowledge, projectId]);

  return useMemo(
    () => ({
      documents,
      error,
      folders,
      isLoading,
      isSaving,
      isUpdating: isUpdating || status.indexing_document_count > 0,
      isAllSelected: documents.length > 0 && selectedDocumentIds.length === documents.length,
      onCreateFolder: createFolder,
      onDeleteFolder: removeFolder,
      onDelete: (documentId: number) => void removeDocument(documentId),
      onDeleteSelected: () => void removeSelectedDocuments(),
      onRefresh: () => void loadKnowledge(),
      onReindex: (documentId: number) => void reindexDocument(documentId),
      onRenameFolder: renameFolder,
      onSelectAll: () =>
        setSelectedDocumentIds((current) =>
          current.length === documents.length ? [] : documents.map((document) => document.id),
        ),
      onSelectMany: (documentIds: number[], selected: boolean) =>
        setSelectedDocumentIds((current) => {
          if (!selected) {
            const idsToRemove = new Set(documentIds);
            return current.filter((documentId) => !idsToRemove.has(documentId));
          }
          return Array.from(new Set([...current, ...documentIds]));
        }),
      onSelectOne: (documentId: number) =>
        setSelectedDocumentIds((current) =>
          current.includes(documentId)
            ? current.filter((id) => id !== documentId)
            : [...current, documentId],
        ),
      onUpdate: () => void updateKnowledge(),
      onMoveSelected: (folder: string) => void moveSelectedDocuments(folder),
      onUploadMany: (files: File[], folder?: string, relativePaths?: string[]) =>
        void uploadDocuments(files, folder, relativePaths),
      selectedDocumentIds,
      status,
      updateResult,
    }),
    [
      documents,
      error,
      folders,
      isLoading,
      isSaving,
      isUpdating,
      loadKnowledge,
      moveSelectedDocuments,
      removeDocument,
      removeFolder,
      removeSelectedDocuments,
      renameFolder,
      reindexDocument,
      createFolder,
      selectedDocumentIds,
      status,
      updateKnowledge,
      updateResult,
      uploadDocuments,
    ],
  );
}
