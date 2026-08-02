import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { groundedSamApi, type GroundedSamApiClient } from "../services/jarvisApi";
import type {
  GroundedSamAnalysisResult,
  GroundedSamHealth,
  GroundedSamSavedImage,
} from "../types/groundedSam";

export type GroundedSamPhase =
  | "idle"
  | "loading"
  | "ready"
  | "analyzing"
  | "success"
  | "failure";

export type GroundedSamState = {
  phase: GroundedSamPhase;
  health: GroundedSamHealth | null;
  images: GroundedSamSavedImage[];
  selectedImageId: string;
  selectedImage: GroundedSamSavedImage | null;
  prompt: string;
  result: GroundedSamAnalysisResult | null;
  inventoryLoading: boolean;
  errorMessage: string;
  analysisDisabledReason: string | null;
  setSelectedImageId: (imageId: string) => void;
  setPrompt: (prompt: string) => void;
  refreshInventory: () => Promise<void>;
  submitAnalysis: () => Promise<void>;
};

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function errorText(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}

function failureText(result: GroundedSamAnalysisResult) {
  const detail = result.error || result.failure_reason || result.status || "Unknown failure";
  switch (result.failure_reason) {
    case "backend_disabled":
      return "Grounded SAM is disabled in the backend configuration.";
    case "worker_unavailable":
    case "dependency_missing":
    case "model_unavailable":
    case "model_load_failed":
      return `Grounded SAM worker is unavailable: ${detail}`;
    case "worker_busy":
      return "Grounded SAM worker is busy. Wait for the current request, then try again.";
    case "request_timeout":
      return `Grounded SAM analysis timed out: ${detail}`;
    case "source_image_missing":
    case "source_image_unreadable":
      return `The saved-image selection is stale or invalid: ${detail}`;
    case "no_detector_candidate":
      return "No detector candidate matched the object prompt.";
    case "ambiguous_detector_candidates":
      return "Multiple similarly strong objects matched the prompt. Refine the prompt and try again.";
    case "calibration_invalid":
    case "calibration_provenance_mismatch":
      return `The saved C920 image failed calibration provenance validation: ${detail}`;
    case "invalid_prompt":
      return `The object prompt is invalid: ${detail}`;
    case "artifact_write_failed":
      return `Analysis completed partially, but an artifact could not be saved: ${detail}`;
    default:
      return `Grounded SAM analysis failed: ${detail}`;
  }
}

export function useGroundedSam(
  apiClient: GroundedSamApiClient = groundedSamApi
): GroundedSamState {
  const [phase, setPhase] = useState<GroundedSamPhase>("idle");
  const [health, setHealth] = useState<GroundedSamHealth | null>(null);
  const [images, setImages] = useState<GroundedSamSavedImage[]>([]);
  const [selectedImageId, setSelectedImageIdState] = useState("");
  const [prompt, setPromptState] = useState("");
  const [result, setResult] = useState<GroundedSamAnalysisResult | null>(null);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const inventoryController = useRef<AbortController | null>(null);
  const analysisController = useRef<AbortController | null>(null);
  const inventorySequence = useRef(0);
  const analysisSequence = useRef(0);
  const analysisInFlight = useRef(false);
  const selectedImageIdRef = useRef("");

  const clearAnalysis = useCallback(() => {
    analysisSequence.current += 1;
    analysisController.current?.abort();
    analysisController.current = null;
    analysisInFlight.current = false;
    setResult(null);
    setErrorMessage("");
  }, []);

  const setSelectedImageId = useCallback((imageId: string) => {
    if (selectedImageIdRef.current === imageId) return;
    clearAnalysis();
    selectedImageIdRef.current = imageId;
    setSelectedImageIdState(imageId);
    setPhase("ready");
  }, [clearAnalysis]);

  const setPrompt = useCallback((value: string) => {
    setPromptState(value);
    setErrorMessage("");
    setPhase((current) => current === "failure" ? "ready" : current);
  }, []);

  const refreshInventory = useCallback(async () => {
    const sequence = inventorySequence.current + 1;
    inventorySequence.current = sequence;
    inventoryController.current?.abort();
    const controller = new AbortController();
    inventoryController.current = controller;
    setInventoryLoading(true);
    setErrorMessage("");
    if (!analysisInFlight.current) setPhase("loading");

    try {
      const [nextHealth, inventory] = await Promise.all([
        apiClient.getStatus(controller.signal),
        apiClient.getSavedImages(controller.signal),
      ]);
      if (controller.signal.aborted || inventorySequence.current !== sequence) return;
      setHealth(nextHealth);
      setImages(inventory.images);
      const currentSelection = selectedImageIdRef.current;
      const nextSelection = inventory.images.some((image) => image.image_id === currentSelection)
        ? currentSelection
        : inventory.images[0]?.image_id || "";
      if (nextSelection !== currentSelection) {
        clearAnalysis();
        selectedImageIdRef.current = nextSelection;
        setSelectedImageIdState(nextSelection);
      }
      if (!analysisInFlight.current) setPhase("ready");
    } catch (error) {
      if (isAbortError(error) || inventorySequence.current !== sequence) return;
      setHealth(null);
      setImages([]);
      clearAnalysis();
      selectedImageIdRef.current = "";
      setSelectedImageIdState("");
      setErrorMessage(errorText(error, "Grounded SAM inventory could not be loaded."));
      setPhase("failure");
    } finally {
      if (inventorySequence.current === sequence) setInventoryLoading(false);
    }
  }, [apiClient, clearAnalysis]);

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => {
      void refreshInventory();
    }, 0);
    return () => {
      window.clearTimeout(initialRefresh);
      inventorySequence.current += 1;
      analysisSequence.current += 1;
      inventoryController.current?.abort();
      analysisController.current?.abort();
      analysisInFlight.current = false;
    };
  }, [refreshInventory]);

  const selectedImage = useMemo(
    () => images.find((image) => image.image_id === selectedImageId) || null,
    [images, selectedImageId]
  );

  const analysisDisabledReason = useMemo(() => {
    if (phase === "analyzing") return "Analysis is already running.";
    if (inventoryLoading && !health) return "Loading saved images and worker status.";
    if (!health) return "Grounded SAM backend status is unavailable.";
    if (!health.enabled) return "Grounded SAM is disabled in backend configuration.";
    if (!health.worker_reachable) return "The manually started loopback worker is unavailable.";
    if (health.dependencies_available === false) return "Grounded SAM dependencies are unavailable.";
    if (health.model_state === "loading") return "Grounded SAM models are loading.";
    if (health.model_state === "load_failed") {
      return health.last_load_error
        ? `Grounded SAM model loading failed: ${health.last_load_error}`
        : "Grounded SAM model loading failed.";
    }
    if (health.model_state === "unavailable") return "Grounded SAM models are unavailable.";
    if (health.busy) return "Grounded SAM worker is busy.";
    if (!images.length) return "No validated C920 rectified images are available.";
    if (!selectedImage) return "Select a validated saved image.";
    if (!prompt.trim()) return "Enter an object prompt.";
    return null;
  }, [health, images.length, inventoryLoading, phase, prompt, selectedImage]);

  const submitAnalysis = useCallback(async () => {
    if (analysisInFlight.current) return;
    const trimmedPrompt = prompt.trim();
    if (!selectedImageIdRef.current) {
      setErrorMessage("Select a validated saved image before analysis.");
      setPhase("failure");
      return;
    }
    if (!trimmedPrompt) {
      setErrorMessage("Enter an object prompt before analysis.");
      setPhase("failure");
      return;
    }
    if (analysisDisabledReason) {
      setErrorMessage(analysisDisabledReason);
      setPhase("failure");
      return;
    }

    const sequence = analysisSequence.current + 1;
    analysisSequence.current = sequence;
    analysisController.current?.abort();
    const controller = new AbortController();
    analysisController.current = controller;
    analysisInFlight.current = true;
    setResult(null);
    setErrorMessage("");
    setPhase("analyzing");

    try {
      const response = await apiClient.analyze(
        selectedImageIdRef.current,
        trimmedPrompt,
        controller.signal
      );
      if (controller.signal.aborted || analysisSequence.current !== sequence) return;
      setResult(response.result);
      if (response.result.ok && response.httpStatus >= 200 && response.httpStatus < 300) {
        setPhase("success");
      } else {
        setErrorMessage(failureText(response.result));
        setPhase("failure");
      }
    } catch (error) {
      if (isAbortError(error) || analysisSequence.current !== sequence) return;
      setErrorMessage(errorText(error, "Grounded SAM analysis request failed."));
      setPhase("failure");
    } finally {
      if (analysisSequence.current === sequence) {
        analysisInFlight.current = false;
        analysisController.current = null;
      }
    }
  }, [analysisDisabledReason, apiClient, prompt]);

  return {
    phase,
    health,
    images,
    selectedImageId,
    selectedImage,
    prompt,
    result,
    inventoryLoading,
    errorMessage,
    analysisDisabledReason,
    setSelectedImageId,
    setPrompt,
    refreshInventory,
    submitAnalysis,
  };
}
