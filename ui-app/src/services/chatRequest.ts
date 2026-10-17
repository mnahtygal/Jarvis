export const CHAT_REQUEST_TIMEOUT_MS = 30 * 60 * 1000;
export const MAX_CHAT_RESPONSE_BYTES = 2 * 1024 * 1024;

export type JarvisChatResponse = {
  heard: string;
  response: string;
};

export type RequestGate = {
  tryAcquire: () => boolean;
  release: () => void;
  isActive: () => boolean;
};

type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class JarvisRequestError extends Error {
  readonly code: "empty_command" | "http_error" | "invalid_response" | "network_error" | "timeout";

  constructor(
    message: string,
    code: "empty_command" | "http_error" | "invalid_response" | "network_error" | "timeout"
  ) {
    super(message);
    this.name = "JarvisRequestError";
    this.code = code;
  }
}

export function createRequestGate(): RequestGate {
  let active = false;
  return {
    tryAcquire() {
      if (active) return false;
      active = true;
      return true;
    },
    release() {
      active = false;
    },
    isActive() {
      return active;
    },
  };
}

export function normalizeCommand(command: string): string | null {
  const normalized = command.trim();
  return normalized || null;
}

export async function runSerializedRequest<T>(
  gate: RequestGate,
  request: () => Promise<T>
): Promise<{ started: false } | { started: true; value: T }> {
  if (!gate.tryAcquire()) return { started: false };
  try {
    return { started: true, value: await request() };
  } finally {
    gate.release();
  }
}

function parseResponseBody(body: string): JarvisChatResponse | null {
  let value: unknown;
  try {
    value = JSON.parse(body);
  } catch {
    return null;
  }
  if (!value || typeof value !== "object") return null;
  const payload = value as Record<string, unknown>;
  if (typeof payload.response !== "string") return null;
  return {
    heard: typeof payload.heard === "string" ? payload.heard : "",
    response: payload.response,
  };
}

async function readBoundedResponseBody(response: Response): Promise<string> {
  const declaredLength = Number(response.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_CHAT_RESPONSE_BYTES) {
    throw new JarvisRequestError("Jarvis returned more output than the UI can safely display.", "invalid_response");
  }
  if (!response.body) {
    const body = await response.text();
    if (new TextEncoder().encode(body).byteLength > MAX_CHAT_RESPONSE_BYTES) {
      throw new JarvisRequestError("Jarvis returned more output than the UI can safely display.", "invalid_response");
    }
    return body;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let body = "";
  let receivedBytes = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    receivedBytes += value.byteLength;
    if (receivedBytes > MAX_CHAT_RESPONSE_BYTES) {
      await reader.cancel();
      throw new JarvisRequestError("Jarvis returned more output than the UI can safely display.", "invalid_response");
    }
    body += decoder.decode(value, { stream: true });
  }
  return body + decoder.decode();
}

export async function postJarvisChat(
  url: string,
  payload: Record<string, unknown>,
  options: {
    fetchImpl?: FetchLike;
    timeoutMs?: number;
  } = {}
): Promise<JarvisChatResponse> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? CHAT_REQUEST_TIMEOUT_MS;
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const body = await readBoundedResponseBody(response);
    const parsed = parseResponseBody(body);
    if (!response.ok) {
      throw new JarvisRequestError(
        `Jarvis request failed (HTTP ${response.status}). Please retry or check backend status.`,
        "http_error"
      );
    }
    if (!parsed) {
      throw new JarvisRequestError(
        "Jarvis returned an invalid response. Please retry or check the backend log.",
        "invalid_response"
      );
    }
    return parsed;
  } catch (error) {
    if (error instanceof JarvisRequestError) throw error;
    if (controller.signal.aborted) {
      throw new JarvisRequestError(
        "Jarvis took too long to respond. The request may still be finishing on the backend.",
        "timeout"
      );
    }
    throw new JarvisRequestError(
      "Jarvis backend is unavailable. Check the readiness indicator and try again.",
      "network_error"
    );
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export function safeRequestError(error: unknown): string {
  return error instanceof JarvisRequestError
    ? error.message
    : "Jarvis request failed safely. Please retry.";
}
