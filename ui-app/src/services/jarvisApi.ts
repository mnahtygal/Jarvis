// Centralized HTTP client for the Jarvis frontend.

import { appConfig } from "../config/appConfig";
import type {
  GroundedSamAnalysisResponse,
  GroundedSamAnalysisResult,
  GroundedSamHealth,
  GroundedSamInventoryResponse,
} from "../types/groundedSam";

export const API_BASE = appConfig.apiBaseUrl;

const JSON_HEADERS = {
  "Content-Type": "application/json",
};

export type ApplyCalibrationPayload = {
  corners: number[][];
  known_width_mm: number;
  known_height_mm: number;
  image_width_px?: number;
  image_height_px?: number;
};

export async function getDashboardStatus() {
  return fetch(`${API_BASE}/api/status/dashboard`);
}

export async function getArchitectureStatus() {
  return fetch(`${API_BASE}/api/status/architecture`);
}

export function getArchitectureTreeUrl() {
  return `${API_BASE}/api/architecture/tree`;
}

export function getArchitectureCallflowUrl() {
  return `${API_BASE}/api/architecture/callflow`;
}

export async function getCalibrationStatus() {
  return fetch(`${API_BASE}/api/status/calibration`);
}

export async function getCalibrationProfile() {
  return fetch(`${API_BASE}/api/calibration/profile`);
}

export async function checkHealth() {
  return fetch(`${API_BASE}/health`);
}

export async function checkLatestSnapshot() {
  return fetch(`${API_BASE}/api/camera/latest`, {
    method: "HEAD",
    cache: "no-store",
  });
}

export async function sendTextCommand(command: string, useVoice = false) {
  return fetch(`${API_BASE}/text`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      command,
      use_voice: useVoice,
    }),
  });
}

export async function listen() {
  return fetch(`${API_BASE}/listen`);
}

export async function askJarvis(useVoice: boolean) {
  return fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      use_voice: useVoice,
    }),
  });
}

export async function captureSnapshot() {
  return fetch(`${API_BASE}/api/camera/snapshot`, {
    method: "POST",
  });
}

export async function getCameras() {
  return fetch(`${API_BASE}/api/cameras`);
}

export async function switchActiveCamera(role: string) {
  return fetch(`${API_BASE}/api/camera/active`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ role }),
  });
}

export async function analyzeSnapshot(prompt: string) {
  return fetch(`${API_BASE}/api/camera/analyze`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      prompt,
    }),
  });
}

export async function captureAndAnalyze(prompt: string, mode = "general") {
  return fetch(`${API_BASE}/api/camera/capture-analyze`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      prompt,
      mode,
    }),
  });
}

export async function scanMat() {
  return fetch(`${API_BASE}/api/vision/scan-mat`, {
    method: "POST",
  });
}

export async function captureScanMat() {
  return fetch(`${API_BASE}/api/vision/capture-scan-mat`, {
    method: "POST",
  });
}

export async function applyCalibration(payload: ApplyCalibrationPayload) {
  return fetch(`${API_BASE}/api/calibration/apply`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
  });
}

export async function measureLatestObject(imagePath: string) {
  return fetch(`${API_BASE}/api/measurement/analyze`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      image_path: imagePath,
    }),
  });
}

export async function getGroundedSamStatus(signal?: AbortSignal) {
  return fetch(`${API_BASE}/api/status/grounded-sam`, { signal });
}

export async function getGroundedSamSavedImages(signal?: AbortSignal) {
  return fetch(`${API_BASE}/api/vision/grounded-sam/saved-images`, {
    cache: "no-store",
    signal,
  });
}

export async function analyzeGroundedSamSavedImage(
  imageId: string,
  prompt: string,
  signal?: AbortSignal
) {
  return fetch(`${API_BASE}/api/measurement/analyze`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({
      backend: "grounded_sam",
      image_id: imageId,
      prompt,
    }),
    signal,
  });
}

async function decodeJson<T>(response: Response, label: string): Promise<T> {
  try {
    return await response.json() as T;
  } catch {
    throw new Error(`${label} returned an invalid JSON response.`);
  }
}

export const groundedSamApi = {
  async getStatus(signal?: AbortSignal): Promise<GroundedSamHealth> {
    const response = await getGroundedSamStatus(signal);
    const payload = await decodeJson<GroundedSamHealth>(response, "Grounded SAM status");
    if (!response.ok) {
      throw new Error(`Grounded SAM status failed with HTTP ${response.status}.`);
    }
    return payload;
  },

  async getSavedImages(signal?: AbortSignal): Promise<GroundedSamInventoryResponse> {
    const response = await getGroundedSamSavedImages(signal);
    const payload = await decodeJson<GroundedSamInventoryResponse>(response, "Saved-image inventory");
    if (!response.ok || !payload.ok) {
      throw new Error(`Saved-image inventory failed with HTTP ${response.status}.`);
    }
    return payload;
  },

  async analyze(
    imageId: string,
    prompt: string,
    signal?: AbortSignal
  ): Promise<GroundedSamAnalysisResponse> {
    const response = await analyzeGroundedSamSavedImage(imageId, prompt, signal);
    const result = await decodeJson<GroundedSamAnalysisResult>(response, "Grounded SAM analysis");
    return { httpStatus: response.status, result };
  },
};

export type GroundedSamApiClient = typeof groundedSamApi;
