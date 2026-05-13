import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import { fetchModels } from "../../models/api/models";
import {
  normalizeReasoningProfileForModel,
  reasoningRequestValueForModel,
  resolveModelDefaultReasoningProfile,
  resolveModelReasoningControl,
} from "../../models/lib/reasoningProfiles";
import type { ModelsPayload, ReasoningProfileValue } from "../../../types";
import { loadStoredModelsCache, saveModelsCache } from "./workspaceCache";
import { modelAllowsImageAttachments } from "./chatAppUtils";

interface UseWorkspaceModelsOptions {
  defaultModel: string;
  onDefaultModelResolved: (model: string) => void;
  setError: (message: string | null) => void;
}

function firstExistingModel(models: ModelsPayload["models"], preferredModel: string, backendDefaultModel: string) {
  return (
    models.find((item) => item.id === preferredModel)?.id
    ?? models.find((item) => item.id === backendDefaultModel)?.id
    ?? models[0]?.id
    ?? ""
  );
}

function resolveSelectedModel(models: ModelsPayload["models"], preferredModel: string) {
  return models.find((item) => item.id === preferredModel)?.id ?? models[0]?.id ?? "";
}

export function useWorkspaceModels({
  defaultModel,
  onDefaultModelResolved,
  setError,
}: UseWorkspaceModelsOptions) {
  const [initialModelsCache] = useState(() => loadStoredModelsCache());
  const [models, setModels] = useState(() => initialModelsCache?.models ?? []);
  const [selectedModel, setSelectedModel] = useState(() => {
    if (initialModelsCache?.models.length) {
      return firstExistingModel(
        initialModelsCache.models,
        defaultModel,
        initialModelsCache.default_model,
      );
    }
    return "";
  });
  const [reasoningProfile, setReasoningProfile] = useState<ReasoningProfileValue>("off");
  const modelsLoadGuard = useLatestRequestGuard();
  const reasoningSyncKeyRef = useRef<string | null>(null);

  const selectedModelOption = useMemo(
    () => (selectedModel ? models.find((item) => item.id === selectedModel) ?? null : null),
    [models, selectedModel],
  );
  const attachmentUploadAvailable = selectedModelOption?.supports_attachment_upload ?? false;
  const imageUploadAvailable = selectedModelOption ? modelAllowsImageAttachments(selectedModelOption) : false;
  const selectedModelReasoningKey = useMemo(
    () => {
      if (!selectedModelOption) {
        return "";
      }
      return [
        selectedModelOption.id,
        resolveModelReasoningControl(selectedModelOption),
        resolveModelDefaultReasoningProfile(selectedModelOption),
      ].join(":");
    },
    [selectedModelOption],
  );
  const activeReasoningRequest = useMemo(
    () => selectedModelOption ? reasoningRequestValueForModel(selectedModelOption, reasoningProfile) : null,
    [reasoningProfile, selectedModelOption],
  );
  const availableModels = models;

  const adjustModelLoveScore = useCallback((modelId: string, delta: number) => {
    setModels((current) =>
      current.map((model) =>
        model.id === modelId
          ? {
              ...model,
              // 中文注释：模型页展示的是喜爱数，点踩只能扣回 0，不能出现负数。
              love_score: Math.max(0, (model.love_score ?? 0) + delta),
            }
          : model,
      ),
    );
  }, []);

  const adjustModelUsageCount = useCallback((modelId: string, delta: number) => {
    setModels((current) =>
      current.map((model) =>
        model.id === modelId
          ? {
              ...model,
              // 中文注释：调用数来自全局统计，本地即时同步时同样保证不会显示负数。
              usage_count: Math.max(0, (model.usage_count ?? 0) + delta),
            }
          : model,
      ),
    );
  }, []);

  const handleModelChange = useCallback((model: string) => {
    if (!model) {
      return;
    }
    setSelectedModel(model);
  }, []);

  const handleReasoningProfileChange = useCallback((value: ReasoningProfileValue) => {
    if (!selectedModelOption) {
      return;
    }
    setReasoningProfile(normalizeReasoningProfileForModel(selectedModelOption, value));
  }, [selectedModelOption]);

  const loadModels = useCallback(async () => {
    const requestId = modelsLoadGuard.begin();
    try {
      const payload = await fetchModels();
      if (!modelsLoadGuard.isCurrent(requestId)) {
        return;
      }
      const nextModels = payload.models;
      saveModelsCache({
        default_model: payload.default_model,
        models: nextModels,
      } satisfies ModelsPayload);
      setModels(nextModels);
      const nextDefaultModel = firstExistingModel(nextModels, defaultModel, payload.default_model);
      if (nextDefaultModel && nextDefaultModel !== defaultModel) {
        onDefaultModelResolved(nextDefaultModel);
      }
      setSelectedModel((current) => resolveSelectedModel(nextModels, current || nextDefaultModel));
    } catch (loadError) {
      if (modelsLoadGuard.isCurrent(requestId)) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load models.");
      }
    }
  }, [defaultModel, modelsLoadGuard, onDefaultModelResolved, setError]);

  useEffect(() => {
    void loadModels();
  }, [loadModels]);

  useEffect(() => {
    if (!selectedModelOption) {
      reasoningSyncKeyRef.current = null;
      setReasoningProfile("off");
      return;
    }
    if (reasoningSyncKeyRef.current === selectedModelReasoningKey) {
      return;
    }
    reasoningSyncKeyRef.current = selectedModelReasoningKey;
    setReasoningProfile(
      resolveModelDefaultReasoningProfile(selectedModelOption),
    );
  }, [selectedModelOption, selectedModelReasoningKey]);

  return {
    activeReasoningRequest,
    adjustModelLoveScore,
    adjustModelUsageCount,
    attachmentUploadAvailable,
    availableModels,
    handleModelChange,
    handleReasoningProfileChange,
    imageUploadAvailable,
    reasoningProfile,
    selectedModel,
    setSelectedModel,
  };
}
