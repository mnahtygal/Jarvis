import assert from "node:assert/strict";
import test from "node:test";

import {
  JarvisRequestError,
  createRequestGate,
  normalizeCommand,
  postJarvisChat,
  runSerializedRequest,
} from "../src/services/chatRequest.ts";

test("empty and whitespace-only commands are refused before transport", () => {
  assert.equal(normalizeCommand(""), null);
  assert.equal(normalizeCommand("   \n\t"), null);
  assert.equal(normalizeCommand("  approve  "), "approve");
});

test("chat requests serialize the exact JSON payload and preserve multiline output", async () => {
  let requestBody = "";
  const result = await postJarvisChat(
    "http://127.0.0.1:5000/text",
    { command: "Read core/brain.py", use_voice: false },
    {
      fetchImpl: async (_url, init) => {
        requestBody = String(init?.body);
        return new Response(JSON.stringify({
          heard: "Read core/brain.py",
          response: "1: first line\n2: second line",
        }));
      },
    }
  );

  assert.deepEqual(JSON.parse(requestBody), {
    command: "Read core/brain.py",
    use_voice: false,
  });
  assert.equal(result.response, "1: first line\n2: second line");
});

test("confirmation responses remain plain backend-authored text", async () => {
  let calls = 0;
  let requestBody = "";
  const result = await postJarvisChat("http://127.0.0.1:5000/text", { command: "approve" }, {
    fetchImpl: async (_url, init) => {
      calls += 1;
      requestBody = String(init?.body);
      return new Response(JSON.stringify({
        heard: "approve",
        response: "Confirmation required. Reply exactly 'approve'.",
      }));
    },
  });
  assert.equal(result.response, "Confirmation required. Reply exactly 'approve'.");
  assert.equal(JSON.parse(requestBody).command, "approve");
  assert.equal(calls, 1, "approval must not be retried automatically");
});

test("request gate prevents duplicate submission and releases after success", async () => {
  const gate = createRequestGate();
  let releaseRequest: (() => void) | undefined;
  const pending = runSerializedRequest(gate, async () => {
    await new Promise<void>((resolve) => {
      releaseRequest = resolve;
    });
    return "done";
  });

  const duplicate = await runSerializedRequest(gate, async () => "duplicate");
  assert.deepEqual(duplicate, { started: false });
  releaseRequest?.();
  assert.deepEqual(await pending, { started: true, value: "done" });
  assert.equal(gate.isActive(), false);
});

test("request gate releases after errors", async () => {
  const gate = createRequestGate();
  await assert.rejects(
    runSerializedRequest(gate, async () => {
      throw new Error("failure");
    }),
    /failure/
  );
  assert.equal(gate.isActive(), false);
  assert.deepEqual(
    await runSerializedRequest(gate, async () => "retry"),
    { started: true, value: "retry" }
  );
});

async function assertGateReleasesAfter(request: () => Promise<unknown>) {
  const gate = createRequestGate();
  await assert.rejects(runSerializedRequest(gate, request));
  assert.equal(gate.isActive(), false);
  assert.deepEqual(
    await runSerializedRequest(gate, async () => "retry"),
    { started: true, value: "retry" }
  );
}

test("request gate releases after HTTP failure", async () => {
  await assertGateReleasesAfter(() => postJarvisChat("/text", {}, {
    fetchImpl: async () => new Response("error", { status: 500 }),
  }));
});

test("request gate releases after network failure", async () => {
  await assertGateReleasesAfter(() => postJarvisChat("/text", {}, {
    fetchImpl: async () => { throw new TypeError("disconnect"); },
  }));
});

test("request gate releases after malformed response", async () => {
  await assertGateReleasesAfter(() => postJarvisChat("/text", {}, {
    fetchImpl: async () => new Response("not json"),
  }));
});

test("request gate releases after timeout", async () => {
  await assertGateReleasesAfter(() => postJarvisChat("/text", {}, {
    timeoutMs: 1,
    fetchImpl: async (_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new Error("aborted")));
    }),
  }));
});

test("oversized responses are rejected before display", async () => {
  await assert.rejects(
    postJarvisChat("/text", {}, {
      fetchImpl: async () => new Response("x", {
        headers: { "content-length": String(2 * 1024 * 1024 + 1) },
      }),
    }),
    (error: unknown) => error instanceof JarvisRequestError
      && error.code === "invalid_response"
  );
});

test("HTTP, malformed JSON, plain text, network, and timeout failures are safe", async () => {
  await assert.rejects(
    postJarvisChat("/text", {}, {
      fetchImpl: async () => new Response(
        JSON.stringify({ response: "private traceback" }),
        { status: 500 }
      ),
    }),
    (error: unknown) => error instanceof JarvisRequestError
      && error.code === "http_error"
      && !error.message.includes("private traceback")
  );
  await assert.rejects(
    postJarvisChat("/text", {}, {
      fetchImpl: async () => new Response("not json"),
    }),
    (error: unknown) => error instanceof JarvisRequestError
      && error.code === "invalid_response"
  );
  await assert.rejects(
    postJarvisChat("/text", {}, {
      fetchImpl: async () => new Response("server detail", { status: 502 }),
    }),
    (error: unknown) => error instanceof JarvisRequestError
      && error.code === "http_error"
      && !error.message.includes("server detail")
  );
  await assert.rejects(
    postJarvisChat("/text", {}, {
      fetchImpl: async () => { throw new TypeError("disconnect detail"); },
    }),
    (error: unknown) => error instanceof JarvisRequestError
      && error.code === "network_error"
      && !error.message.includes("disconnect detail")
  );
  await assert.rejects(
    postJarvisChat("/text", {}, {
      timeoutMs: 1,
      fetchImpl: async (_url, init) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new Error("aborted")));
      }),
    }),
    (error: unknown) => error instanceof JarvisRequestError
      && error.code === "timeout"
  );
});
