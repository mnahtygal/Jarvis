// Centralized HTTP client for the Jarvis frontend.

export const API_BASE = "http://127.0.0.1:5000";

const JSON_HEADERS = {
  "Content-Type": "application/json",
};

export async function getDashboardStatus() {
  return fetch(`${API_BASE}/api/status/dashboard`);
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
