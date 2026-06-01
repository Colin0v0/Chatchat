import { useCallback, useEffect, useMemo, useState } from "react";

import type { ProjectSummary } from "../../../types";
import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import { createProject, deleteProject, fetchProjects, updateProject } from "../api/projects";

const PROJECT_STORAGE_PREFIX = "chatchat.active-project";

function projectStorageKey(userId: number | null | undefined) {
  return `${PROJECT_STORAGE_PREFIX}.${userId ?? "anonymous"}`;
}

function loadStoredProjectId(userId: number | null | undefined): number | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(projectStorageKey(userId));
  if (!raw) {
    return null;
  }
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function saveStoredProjectId(userId: number | null | undefined, projectId: number | null) {
  if (typeof window === "undefined") {
    return;
  }
  const key = projectStorageKey(userId);
  if (projectId === null) {
    window.localStorage.removeItem(key);
    return;
  }
  window.localStorage.setItem(key, String(projectId));
}

export function useProjectManager({
  defaultModel,
  enabled,
  onError,
  userId,
}: {
  defaultModel: string;
  enabled: boolean;
  onError: (message: string) => void;
  userId?: number | null;
}) {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [activeProjectId, setActiveProjectIdState] = useState<number | null>(() => loadStoredProjectId(userId));
  const [loaded, setLoaded] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const loadGuard = useLatestRequestGuard();

  useEffect(() => {
    const storedProjectId = loadStoredProjectId(userId);
    setActiveProjectIdState(storedProjectId);
  }, [userId]);

  const setActiveProjectId = useCallback(
    (projectId: number | null) => {
      setActiveProjectIdState(projectId);
      saveStoredProjectId(userId, projectId);
    },
    [userId],
  );

  const loadProjects = useCallback(async () => {
    if (!enabled) {
      return;
    }
    const requestId = loadGuard.begin();
    try {
      const nextProjects = await fetchProjects();
      if (!loadGuard.isCurrent(requestId)) {
        return;
      }
      setProjects(nextProjects);
      setActiveProjectIdState((current) => {
        if (current !== null && nextProjects.some((project) => project.id === current)) {
          return current;
        }
        saveStoredProjectId(userId, null);
        return null;
      });
      setLoaded(true);
    } catch (error) {
      if (loadGuard.isCurrent(requestId)) {
        onError(error instanceof Error ? error.message : "Failed to load projects.");
        setLoaded(true);
      }
    }
  }, [enabled, loadGuard, onError, userId]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  const create = useCallback(
    async (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) {
        return null;
      }
      setIsSaving(true);
      try {
        const project = await createProject({
          name: trimmed,
          default_model: defaultModel || null,
        });
        setProjects((current) => [project, ...current.filter((item) => item.id !== project.id)]);
        setActiveProjectId(project.id);
        return project;
      } catch (error) {
        onError(error instanceof Error ? error.message : "Failed to create project.");
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [defaultModel, onError, setActiveProjectId],
  );

  const update = useCallback(
    async (projectId: number, patch: Partial<Pick<ProjectSummary, "name" | "description" | "default_model">>) => {
      setIsSaving(true);
      try {
        const project = await updateProject(projectId, patch);
        setProjects((current) => current.map((item) => (item.id === project.id ? project : item)));
        return project;
      } catch (error) {
        onError(error instanceof Error ? error.message : "Failed to update project.");
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [onError],
  );

  const remove = useCallback(
    async (projectId: number) => {
      setIsSaving(true);
      try {
        await deleteProject(projectId);
        setProjects((current) => current.filter((item) => item.id !== projectId));
        setActiveProjectIdState((current) => {
          if (current !== projectId) {
            return current;
          }
          saveStoredProjectId(userId, null);
          return null;
        });
        return true;
      } catch (error) {
        onError(error instanceof Error ? error.message : "Failed to delete project.");
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [onError, userId],
  );

  const activeProject = useMemo(
    () => projects.find((project) => project.id === activeProjectId) ?? null,
    [activeProjectId, projects],
  );

  return useMemo(
    () => ({
      activeProject,
      activeProjectId,
      isSaving,
      loaded,
      projects,
      create,
      refresh: loadProjects,
      remove,
      setActiveProjectId,
      update,
    }),
    [activeProject, activeProjectId, create, isSaving, loadProjects, loaded, projects, remove, setActiveProjectId, update],
  );
}
