import {
  Check,
  ChevronDown,
  FileUp,
  Folder,
  FolderOpen,
  FolderUp,
  Pencil,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type ReactNode,
} from "react";

import type { KnowledgeDocument, KnowledgeStatus } from "../../../types";
import { ConfirmDialog } from "../../../shared/ui/ConfirmDialog";
import { WorkspacePage } from "../../../shared/ui/WorkspacePage";
import { cn, sidebarIconButtonClass, sidebarMenuPanelClass } from "../../workspace/ui/sidebar/styles";

const ROOT_FOLDER_VALUE = "__root__";
const ALL_FOLDERS_VALUE = "__all__";
const ROOT_FOLDER_LABEL = "默认分组";

type KnowledgeManagerProps = {
  documents: KnowledgeDocument[];
  folders: string[];
  status: KnowledgeStatus;
  error: string | null;
  isLoading: boolean;
  isSaving: boolean;
  isUpdating: boolean;
  isAllSelected: boolean;
  onCreateFolder: (name: string) => Promise<string | null>;
  onDeleteFolder: (name: string) => Promise<boolean>;
  onDelete: (documentId: number) => void;
  onDeleteSelected: () => void;
  onMoveSelected: (folder: string) => void;
  onRefresh: () => void;
  onReindex: (documentId: number) => void;
  onRenameFolder: (name: string, newName: string) => Promise<string | null>;
  onSelectAll: () => void;
  onSelectMany: (documentIds: number[], selected: boolean) => void;
  onSelectOne: (documentId: number) => void;
  onUpdate: () => void;
  onUploadMany: (files: File[], folder?: string, relativePaths?: string[]) => void;
  selectedDocumentIds: number[];
  updateResult: {
    started: boolean;
    scheduled_documents: number;
    indexing_documents: number;
    ready_documents: number;
    failed_documents: number;
    chunk_count: number;
  } | null;
};

type FolderOption = {
  count?: number;
  icon?: ReactNode;
  label: string;
  value: string;
};

function folderLabel(folder: string): string {
  return folder.trim() || ROOT_FOLDER_LABEL;
}

function folderValueForView(value: string): string {
  return value === ROOT_FOLDER_VALUE ? "" : value;
}

function normalizeSearchValue(value: string): string {
  return value.trim().toLowerCase();
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "未记录";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatBytes(value: number): string {
  if (value >= 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${Math.round(value / 1024)} KB`;
  }
  return `${value} B`;
}

function statusLabel(document: KnowledgeDocument): string {
  if (document.status === "ready") {
    return "可用";
  }
  if (document.status === "indexing") {
    return "索引中";
  }
  if (document.status === "failed") {
    return "失败";
  }
  return "待处理";
}

function statusClassName(document: KnowledgeDocument): string {
  if (document.status === "ready") {
    return "border-[#d8eadc] bg-[#f0f8f1] text-[#3f7a48]";
  }
  if (document.status === "indexing") {
    return "border-app-border bg-app-panel-soft text-app-accent-strong";
  }
  if (document.status === "failed") {
    return "border-[#f0d0ca] bg-[#fbefed] text-[#9d3d32]";
  }
  return "border-app-border bg-app-panel-strong text-app-muted";
}

function webkitRelativePathFor(file: File): string {
  return (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
}

function FolderPicker({
  folders,
  includeAll = false,
  value,
  onChange,
}: {
  folders: string[];
  includeAll?: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const baseOptions: FolderOption[] = [
    ...(includeAll
      ? [{ icon: <FolderOpen className="size-4" />, label: "全部资料", value: ALL_FOLDERS_VALUE }]
      : []),
    { icon: <Folder className="size-4" />, label: ROOT_FOLDER_LABEL, value: ROOT_FOLDER_VALUE },
    ...folders.map((folder) => ({
      icon: <Folder className="size-4" />,
      label: folder,
      value: folder,
    })),
  ];
  const selectedIsCustom =
    value &&
    value !== ALL_FOLDERS_VALUE &&
    value !== ROOT_FOLDER_VALUE &&
    !folders.includes(value);
  const options = selectedIsCustom
    ? [{ icon: <Folder className="size-4" />, label: value, value }, ...baseOptions]
    : baseOptions;
  const selectedOption = options.find((option) => option.value === value);
  const selectedLabel =
    selectedOption?.label ??
    (value === ALL_FOLDERS_VALUE ? "全部资料" : folderLabel(folderValueForView(value)));

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <div className="relative min-w-0 w-full" ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        className="inline-flex h-10 w-full min-w-0 items-center justify-between gap-2 rounded-[8px] border border-app-border bg-app-panel-strong px-3 text-left text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span className="flex min-w-0 items-center gap-2">
          {selectedOption?.icon ?? <Folder className="size-4 shrink-0 text-app-muted" />}
          <span className="min-w-0 truncate">{selectedLabel}</span>
        </span>
        <ChevronDown className={`size-4 shrink-0 text-app-muted transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open ? (
        <div
          className={cn(
            "absolute left-0 top-[calc(100%+8px)] z-50 max-h-[260px] w-full overflow-y-auto",
            sidebarMenuPanelClass,
          )}
          role="listbox"
        >
          {options.map((option) => {
            const selected = option.value === value;
            return (
              <button
                aria-selected={selected}
                className={`flex h-10 w-full items-center justify-between gap-3 px-3 text-left text-[14px] font-medium transition-colors ${
                  selected ? "bg-app-panel-soft text-app-text" : "text-app-muted hover:bg-app-panel-soft hover:text-app-text"
                }`}
                key={option.value}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                role="option"
                type="button"
              >
                <span className="flex min-w-0 items-center gap-2">
                  {option.icon}
                  <span className="min-w-0 truncate">{option.label}</span>
                </span>
                {selected ? <Check className="size-4 shrink-0" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function DocumentRow({
  document,
  onDelete,
  onReindex,
  onSelect,
  selected,
}: {
  document: KnowledgeDocument;
  onDelete: (documentId: number) => void;
  onReindex: (documentId: number) => void;
  onSelect: (documentId: number) => void;
  selected: boolean;
}) {
  return (
    <div className="group grid gap-2 border-b border-app-border px-3 py-2.5 last:border-b-0 md:grid-cols-[minmax(0,1fr)_auto_auto_auto] md:items-center">
      <div className="flex min-w-0 items-center gap-3">
        <input
          aria-label={`选择 ${document.title}`}
          checked={selected}
          className="h-4 w-4 shrink-0 rounded border-app-border text-app-accent-strong focus:ring-app-accent-strong"
          onChange={() => onSelect(document.id)}
          type="checkbox"
        />
        <div className="min-w-0">
          <div className="truncate text-[15px] font-medium text-app-text">{document.title}</div>
          {document.error_message ? (
            <div className="mt-2 text-[12px] leading-5 text-[#9d3d32]">{document.error_message}</div>
          ) : null}
        </div>
      </div>

      <div className="flex items-center gap-2 md:block">
        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[12px] font-medium ${statusClassName(document)}`}>
          {statusLabel(document)}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-app-muted md:flex-nowrap">
        <span>{formatBytes(document.size_bytes)}</span>
        <span className="text-app-muted/55">/</span>
        <span>{document.chunk_count} 分块</span>
        <span className="text-app-muted/55">/</span>
        <span>{formatTimestamp(document.updated_at)}</span>
      </div>
      <div className="flex items-center justify-end gap-1">
        <button
          className="flex h-8 w-8 items-center justify-center rounded-[8px] text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
          onClick={() => onReindex(document.id)}
          title="重新索引"
          type="button"
        >
          <RefreshCw className="size-4" />
        </button>
        <button
          className="flex h-8 w-8 items-center justify-center rounded-[8px] text-app-muted transition hover:bg-[#fbefed] hover:text-[#9d3d32]"
          onClick={() => onDelete(document.id)}
          title="删除"
          type="button"
        >
          <Trash2 className="size-4" />
        </button>
      </div>
    </div>
  );
}

export function KnowledgePage({
  knowledge,
}: {
  knowledge: KnowledgeManagerProps;
}) {
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [renamingFolder, setRenamingFolder] = useState<string | null>(null);
  const [renameFolderName, setRenameFolderName] = useState("");
  const [uploadFolder, setUploadFolder] = useState("");
  const [moveFolder, setMoveFolder] = useState("");
  const [visibleFolder, setVisibleFolder] = useState(ALL_FOLDERS_VALUE);
  const [folderDeleteCandidate, setFolderDeleteCandidate] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const folderCounts = useMemo(() => {
    const counts = new Map<string, number>();
    knowledge.documents.forEach((document) => {
      const folder = (document.folder ?? "").trim();
      counts.set(folder, (counts.get(folder) ?? 0) + 1);
    });
    return counts;
  }, [knowledge.documents]);

  const folderOptions = useMemo(
    () => [
      {
        count: knowledge.documents.length,
        icon: <FolderOpen className="size-4 text-app-muted" />,
        label: "全部资料",
        value: ALL_FOLDERS_VALUE,
      },
      {
        count: folderCounts.get("") ?? 0,
        icon: <Folder className="size-4 text-app-muted" />,
        label: ROOT_FOLDER_LABEL,
        value: ROOT_FOLDER_VALUE,
      },
      ...knowledge.folders.map((folder) => ({
        count: folderCounts.get(folder) ?? 0,
        icon: <Folder className="size-4 text-app-muted" />,
        label: folder,
        value: folder,
      })),
    ],
    [folderCounts, knowledge.documents.length, knowledge.folders],
  );

  const visibleDocuments = useMemo(() => {
    const folderFiltered =
      visibleFolder === ALL_FOLDERS_VALUE
        ? knowledge.documents
        : knowledge.documents.filter((document) => (document.folder ?? "") === folderValueForView(visibleFolder));
    const normalizedQuery = normalizeSearchValue(query);
    if (!normalizedQuery) {
      return folderFiltered;
    }
    return folderFiltered.filter((document) =>
      normalizeSearchValue(`${document.title} ${document.path} ${document.folder}`).includes(normalizedQuery),
    );
  }, [knowledge.documents, query, visibleFolder]);

  const groupedDocuments = useMemo(() => {
    const groups = new Map<string, KnowledgeDocument[]>();
    visibleDocuments.forEach((document) => {
      const folder = (document.folder ?? "").trim();
      const items = groups.get(folder) ?? [];
      items.push(document);
      groups.set(folder, items);
    });
    return Array.from(groups.entries()).sort(([left], [right]) =>
      folderLabel(left).localeCompare(folderLabel(right), "zh-CN"),
    );
  }, [visibleDocuments]);

  const selectedVisibleDocumentIds = visibleDocuments
    .filter((document) => knowledge.selectedDocumentIds.includes(document.id))
    .map((document) => document.id);
  const allVisibleSelected =
    visibleDocuments.length > 0 && selectedVisibleDocumentIds.length === visibleDocuments.length;
  const selectedCount = knowledge.selectedDocumentIds.length;
  const selectedFolderLabel = visibleFolder === ALL_FOLDERS_VALUE ? "全部资料" : folderLabel(folderValueForView(visibleFolder));
  const knowledgeProgress =
    knowledge.updateResult && knowledge.updateResult.scheduled_documents > 0
      ? Math.max(
          0,
          Math.min(
            100,
            Math.round(
              ((knowledge.updateResult.scheduled_documents - knowledge.status.indexing_document_count) /
                knowledge.updateResult.scheduled_documents) *
                100,
            ),
          ),
        )
      : null;

  const setActiveFolder = (value: string) => {
    setVisibleFolder(value);
    if (value !== ALL_FOLDERS_VALUE) {
      setUploadFolder(folderValueForView(value));
    }
  };

  const handleCreateFolder = async () => {
    const createdFolder = await knowledge.onCreateFolder(newFolderName);
    if (!createdFolder) {
      return;
    }
    setNewFolderName("");
    setCreatingFolder(false);
    setUploadFolder(createdFolder);
    setVisibleFolder(createdFolder);
  };

  const handleDeleteFolder = async () => {
    if (!folderDeleteCandidate) {
      return;
    }
    const deleted = await knowledge.onDeleteFolder(folderDeleteCandidate);
    if (!deleted) {
      return;
    }
    if (visibleFolder === folderDeleteCandidate) {
      setVisibleFolder(ALL_FOLDERS_VALUE);
    }
    if (uploadFolder === folderDeleteCandidate) {
      setUploadFolder("");
    }
    if (moveFolder === folderDeleteCandidate) {
      setMoveFolder("");
    }
    setFolderDeleteCandidate(null);
  };

  const startRenamingFolder = (folder: string) => {
    setCreatingFolder(false);
    setNewFolderName("");
    setRenamingFolder(folder);
    setRenameFolderName(folder);
  };

  const cancelRenamingFolder = () => {
    setRenamingFolder(null);
    setRenameFolderName("");
  };

  const handleRenameFolder = async () => {
    if (!renamingFolder) {
      return;
    }
    const renamedFolder = await knowledge.onRenameFolder(renamingFolder, renameFolderName);
    if (!renamedFolder) {
      return;
    }
    if (visibleFolder === renamingFolder) {
      setVisibleFolder(renamedFolder);
    }
    if (uploadFolder === renamingFolder) {
      setUploadFolder(renamedFolder);
    }
    if (moveFolder === renamingFolder) {
      setMoveFolder(renamedFolder);
    }
    cancelRenamingFolder();
  };

  const handleUploadFiles = (files: FileList | null, includeRelativePaths: boolean) => {
    const nextFiles = Array.from(files ?? []);
    if (nextFiles.length === 0) {
      return;
    }
    const relativePaths = includeRelativePaths ? nextFiles.map(webkitRelativePathFor) : [];
    knowledge.onUploadMany(nextFiles, uploadFolder, relativePaths);
  };

  const handleDragEnter = (event: DragEvent<HTMLDivElement>) => {
    if (knowledge.isSaving || event.dataTransfer.files.length === 0) {
      return;
    }
    event.preventDefault();
    setDragActive(true);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (knowledge.isSaving || event.dataTransfer.files.length === 0) {
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setDragActive(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setDragActive(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    if (knowledge.isSaving || event.dataTransfer.files.length === 0) {
      return;
    }
    event.preventDefault();
    setDragActive(false);
    handleUploadFiles(event.dataTransfer.files, false);
  };

  const toggleVisibleSelection = () => {
    knowledge.onSelectMany(
      visibleDocuments.map((document) => document.id),
      !allVisibleSelected,
    );
  };
  const deleteCandidateDocumentCount = folderDeleteCandidate ? (folderCounts.get(folderDeleteCandidate) ?? 0) : 0;

  return (
    <>
      <WorkspacePage
        headerPlacement="content"
        maxWidthClassName="max-w-[1400px]"
        actions={
          <div className="flex items-center justify-end gap-2">
            <button
              className="flex h-10 w-10 items-center justify-center rounded-[8px] border border-app-border bg-app-panel-strong text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
              onClick={knowledge.onRefresh}
              title="刷新"
              type="button"
            >
              <RefreshCw className={`size-4 ${knowledge.isLoading ? "animate-spin" : ""}`} />
            </button>
            <button
              className="inline-flex h-10 items-center justify-center gap-2 whitespace-nowrap rounded-[8px] bg-app-accent-soft px-4 text-[14px] font-medium text-app-accent-strong transition hover:bg-[#e7ddcf] disabled:cursor-not-allowed disabled:opacity-55"
              disabled={knowledge.isUpdating}
              onClick={knowledge.onUpdate}
              type="button"
            >
              <RefreshCw className={`size-4 ${knowledge.isUpdating ? "animate-spin" : ""}`} />
              {knowledge.isUpdating ? "同步中" : "同步索引"}
            </button>
          </div>
        }
        title="Knowledge"
      >
      <input
        accept=".md,text/markdown"
        className="hidden"
        multiple
        onChange={(event) => {
          handleUploadFiles(event.target.files, false);
          event.currentTarget.value = "";
        }}
        ref={uploadInputRef}
        type="file"
      />
      <input
        accept=".md,text/markdown"
        className="hidden"
        multiple
        onChange={(event) => {
          handleUploadFiles(event.target.files, true);
          event.currentTarget.value = "";
        }}
        ref={folderInputRef}
        type="file"
        {...{ directory: "", webkitdirectory: "" }}
      />

      <section
        className={`rounded-[8px] border bg-app-panel-strong transition-colors ${
          dragActive ? "border-app-accent-strong bg-app-panel-soft" : "border-app-border"
        }`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <div className="grid lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="flex min-w-0 items-center p-5 md:p-6">
            <div className="min-w-0 flex-1">
              <div className="text-[18px] font-semibold text-app-text">添加资料</div>
              <div className="mt-1 max-w-[520px] text-[13px] leading-6 text-app-muted">
                拖入 Markdown 文件，或选择本地文件夹批量导入。
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-[8px] border border-app-border bg-app-panel px-4 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={knowledge.isSaving}
                  onClick={() => uploadInputRef.current?.click()}
                  type="button"
                >
                  <FileUp className="size-4" />
                  选择文件
                </button>
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-[8px] border border-app-border bg-app-panel px-4 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={knowledge.isSaving}
                  onClick={() => folderInputRef.current?.click()}
                  type="button"
                >
                  <FolderUp className="size-4" />
                  选择文件夹
                </button>
              </div>
            </div>
          </div>

          <div className="grid content-center gap-3 border-t border-app-border p-5 md:p-6 lg:grid-cols-1 lg:border-l lg:border-t-0">
            <div className="text-[13px] font-semibold text-app-text">归档设置</div>
            <div className="min-w-0">
              <div className="mb-1.5 text-[12px] font-medium text-app-muted">归入</div>
              <FolderPicker folders={knowledge.folders} value={uploadFolder || ROOT_FOLDER_VALUE} onChange={(value) => setUploadFolder(folderValueForView(value))} />
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3">
          <div className="text-[12px] font-medium text-app-muted">资料</div>
          <div className="mt-1 text-[22px] font-semibold text-app-text">{knowledge.status.document_count}</div>
        </div>
        <div className="rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3">
          <div className="text-[12px] font-medium text-app-muted">可用</div>
          <div className="mt-1 text-[22px] font-semibold text-app-text">{knowledge.status.ready_document_count}</div>
        </div>
        <div className="rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3">
          <div className="text-[12px] font-medium text-app-muted">分块</div>
          <div className="mt-1 text-[22px] font-semibold text-app-text">{knowledge.status.chunk_count}</div>
        </div>
        <div className="rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3">
          <div className="text-[12px] font-medium text-app-muted">空间</div>
          <div className="mt-1 text-[22px] font-semibold text-app-text">{formatBytes(knowledge.status.total_size_bytes)}</div>
        </div>
      </div>

      {knowledgeProgress != null ? (
        <div className="rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-3">
          <div className="flex items-center justify-between gap-3 text-[13px] font-medium text-app-muted">
            <span>索引进度</span>
            <span>{knowledgeProgress}%</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-app-panel">
            <div className="h-full rounded-full bg-app-accent transition-[width] duration-300" style={{ width: `${knowledgeProgress}%` }} />
          </div>
        </div>
      ) : null}

      {knowledge.error ? <div className="text-[13px] leading-6 text-[#9d3d32]">{knowledge.error}</div> : null}

      <section className="grid min-h-0 gap-4 lg:grid-cols-[400px_minmax(0,1fr)]">
        <aside className="min-w-0 rounded-[8px] border border-app-border bg-app-panel-strong p-2 lg:p-3">
          <div className="mb-2 flex items-center justify-between gap-2 px-2">
            <div className="text-[12px] font-semibold uppercase tracking-[0.14em] text-app-muted">分组</div>
            <button
              className="h-8 rounded-[8px] px-2 text-[13px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
              onClick={() => setCreatingFolder((current) => !current)}
              type="button"
            >
              新建
            </button>
          </div>
          {creatingFolder ? (
            <div className="mb-3 grid gap-2 px-2">
              <input
                autoFocus
                className="h-9 min-w-0 rounded-[8px] border border-app-border bg-app-panel px-3 text-[14px] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong"
                onChange={(event) => setNewFolderName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void handleCreateFolder();
                  }
                  if (event.key === "Escape") {
                    setCreatingFolder(false);
                  }
                }}
                placeholder="分组名称"
                value={newFolderName}
              />
              <div className="grid grid-cols-2 gap-2">
                <button
                  className="h-9 rounded-[8px] bg-app-accent-soft px-3 text-[13px] font-medium text-app-accent-strong transition hover:bg-[#e7ddcf] disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={knowledge.isSaving || !newFolderName.trim()}
                  onClick={() => void handleCreateFolder()}
                  type="button"
                >
                  创建
                </button>
                <button
                  className="h-9 rounded-[8px] border border-app-border bg-app-panel px-3 text-[13px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                  onClick={() => {
                    setCreatingFolder(false);
                    setNewFolderName("");
                  }}
                  type="button"
                >
                  取消
                </button>
              </div>
            </div>
          ) : null}
          <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
            {folderOptions.map((option) => {
              const active = option.value === visibleFolder;
              const deletable = option.value !== ALL_FOLDERS_VALUE && option.value !== ROOT_FOLDER_VALUE;
              const renaming = renamingFolder === option.value;
              return (
                <div
                  className={`group flex h-10 min-w-[154px] items-center rounded-[8px] transition-colors lg:min-w-0 ${
                    active ? "bg-app-panel-soft text-app-text" : "text-app-muted hover:bg-app-panel-soft hover:text-app-text"
                  }`}
                  key={option.value}
                >
                  {renaming ? (
                    <>
                      <input
                        autoFocus
                        className="ml-2 h-8 min-w-0 flex-1 rounded-[8px] border border-app-border bg-app-panel px-2 text-[13px] text-app-text outline-none focus:border-app-border-strong"
                        onChange={(event) => setRenameFolderName(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            void handleRenameFolder();
                          }
                          if (event.key === "Escape") {
                            cancelRenamingFolder();
                          }
                        }}
                        value={renameFolderName}
                      />
                      <button
                        aria-label="保存分组名称"
                        className={cn(sidebarIconButtonClass, "h-8 w-8 shrink-0 text-app-muted hover:bg-app-panel-soft hover:text-app-text")}
                        disabled={knowledge.isSaving || !renameFolderName.trim()}
                        onClick={() => void handleRenameFolder()}
                        type="button"
                      >
                        <Check className="size-4" />
                      </button>
                      <button
                        aria-label="取消重命名"
                        className={cn(sidebarIconButtonClass, "mr-1 h-8 w-8 shrink-0 text-app-muted hover:bg-app-panel-soft hover:text-app-text")}
                        onClick={cancelRenamingFolder}
                        type="button"
                      >
                        <X className="size-4" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        className={cn(
                          "flex h-full min-w-0 flex-1 items-center gap-2 rounded-[8px] pr-3 text-left text-[14px] font-medium",
                          deletable ? "pl-5" : "pl-3",
                        )}
                        onClick={() => setActiveFolder(option.value)}
                        type="button"
                      >
                        {option.icon}
                        <span className="min-w-0 truncate">{option.label}</span>
                      </button>
                      {deletable ? (
                        <>
                          <button
                            aria-label={`重命名分组 ${option.label}`}
                            className={cn(
                              sidebarIconButtonClass,
                              "h-8 w-8 shrink-0 opacity-100 hover:bg-app-panel-soft hover:text-app-text lg:opacity-0 lg:group-hover:opacity-100 lg:focus-visible:opacity-100",
                            )}
                            disabled={knowledge.isSaving}
                            onClick={(event) => {
                              event.stopPropagation();
                              startRenamingFolder(option.value);
                            }}
                            title="重命名分组"
                            type="button"
                          >
                            <Pencil className="size-4" />
                          </button>
                          <button
                            aria-label={`删除分组 ${option.label}`}
                            className={cn(
                              sidebarIconButtonClass,
                              "h-8 w-8 shrink-0 opacity-100 hover:bg-[#fbefed] hover:text-[#9d3d32] lg:opacity-0 lg:group-hover:opacity-100 lg:focus-visible:opacity-100",
                            )}
                            disabled={knowledge.isSaving}
                            onClick={(event) => {
                              event.stopPropagation();
                              setFolderDeleteCandidate(option.value);
                            }}
                            title="删除分组"
                            type="button"
                          >
                            <Trash2 className="size-4" />
                          </button>
                        </>
                      ) : null}
                      <span className="mr-3 flex min-w-5 shrink-0 justify-end text-[12px] text-app-muted" title={`${option.count ?? 0} 个资料`}>
                        {option.count}
                      </span>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </aside>

        <div className="min-w-0 rounded-[8px] border border-app-border bg-app-panel-strong">
          <div className="flex flex-col gap-3 border-b border-app-border p-3 md:flex-row md:items-center md:justify-between">
            <div className="min-w-0">
              <div className="truncate text-[16px] font-semibold text-app-text">{selectedFolderLabel}</div>
              <div className="mt-1 text-[12px] text-app-muted">
                {visibleDocuments.length} 个资料
                {query.trim() ? `，匹配 “${query.trim()}”` : ""}
              </div>
            </div>
            <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
              <label className="flex h-10 min-w-0 items-center gap-2 rounded-[8px] border border-app-border bg-app-panel px-3 text-app-muted transition focus-within:border-app-border-strong sm:w-[240px]">
                <Search className="size-4 shrink-0" />
                <input
                  className="min-w-0 flex-1 bg-transparent text-[14px] text-app-text outline-none placeholder:text-app-muted"
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="搜索资料"
                  value={query}
                />
              </label>
              {visibleDocuments.length > 0 ? (
                <button
                  className="inline-flex h-10 items-center justify-center rounded-[8px] border border-app-border bg-app-panel px-3 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                  onClick={toggleVisibleSelection}
                  type="button"
                >
                  {allVisibleSelected ? "取消选择" : "选择当前"}
                </button>
              ) : null}
            </div>
          </div>

          {selectedCount > 0 ? (
            <div className="flex flex-col gap-3 border-b border-app-border bg-app-panel px-3 py-3 md:flex-row md:items-center md:justify-between">
              <div className="text-[14px] font-medium text-app-text">已选 {selectedCount} 个资料</div>
              <div className="grid gap-2 sm:grid-cols-[180px_auto_auto]">
                <FolderPicker folders={knowledge.folders} value={moveFolder || ROOT_FOLDER_VALUE} onChange={(value) => setMoveFolder(folderValueForView(value))} />
                <button
                  className="inline-flex h-10 items-center justify-center rounded-[8px] border border-app-border bg-app-panel-strong px-3 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={knowledge.isSaving}
                  onClick={() => knowledge.onMoveSelected(moveFolder)}
                  type="button"
                >
                  移到分组
                </button>
                <button
                  className="inline-flex h-10 items-center justify-center rounded-[8px] bg-[#fbefed] px-3 text-[14px] font-medium text-[#9d3d32] transition hover:bg-[#f5dfdb] disabled:cursor-not-allowed disabled:opacity-55"
                  disabled={knowledge.isSaving}
                  onClick={knowledge.onDeleteSelected}
                  type="button"
                >
                  删除
                </button>
              </div>
            </div>
          ) : null}

          {groupedDocuments.length > 0 ? (
            <div>
              {groupedDocuments.map(([folder, documents]) => (
                <section key={folder || ROOT_FOLDER_VALUE}>
                  {visibleFolder === ALL_FOLDERS_VALUE ? (
                    <div className="flex items-center gap-2 border-b border-app-border bg-app-panel px-3 py-2 text-[13px] font-semibold text-app-muted">
                      <Folder className="size-4" />
                      <span className="min-w-0 truncate">{folderLabel(folder)}</span>
                      <span className="shrink-0 font-normal">{documents.length}</span>
                    </div>
                  ) : null}
                  {documents.map((document) => (
                    <DocumentRow
                      document={document}
                      key={document.id}
                      onDelete={knowledge.onDelete}
                      onReindex={knowledge.onReindex}
                      onSelect={knowledge.onSelectOne}
                      selected={knowledge.selectedDocumentIds.includes(document.id)}
                    />
                  ))}
                </section>
              ))}
            </div>
          ) : (
            <div className="grid place-items-center px-4 py-16 text-center">
              <div className="max-w-[360px]">
                <div className="mx-auto flex size-12 items-center justify-center rounded-[8px] bg-app-panel">
                  <FolderOpen className="size-5 text-app-muted" />
                </div>
                <div className="mt-4 text-[16px] font-semibold text-app-text">这里还没有资料</div>
                <div className="mt-2 text-[13px] leading-6 text-app-muted">把 Markdown 文件拖到上方，或选择一个本地文件夹。</div>
              </div>
            </div>
          )}
        </div>
      </section>
      </WorkspacePage>

      <ConfirmDialog
        confirmLabel="删除分组"
        description={
          deleteCandidateDocumentCount > 0 ? (
            <>
              删除 <span className="font-semibold text-app-text">{folderDeleteCandidate}</span> 分组？其中{" "}
              {deleteCandidateDocumentCount} 个资料会移到默认分组，资料本身不会删除。
            </>
          ) : (
            <>
              删除 <span className="font-semibold text-app-text">{folderDeleteCandidate}</span> 分组？
            </>
          )
        }
        disabled={knowledge.isSaving}
        intent="danger"
        onCancel={() => setFolderDeleteCandidate(null)}
        onConfirm={handleDeleteFolder}
        open={folderDeleteCandidate !== null}
        title="确认删除"
      />
    </>
  );
}
