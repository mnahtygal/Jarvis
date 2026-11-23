import assert from "node:assert/strict";
import test from "node:test";

import {
  buildBoundedPythonSessionRequest,
  submitBoundedPythonSessionRequest,
  validateBoundedPythonSessionInput,
} from "../src/services/developerSession.ts";

const validInput = {
  workspace: "/home/mnahtygal/projects/jarvis-repair-challenge",
  sourceFile: "stock.py",
  testFile: "test_stock.py",
};

const canonicalRequest = "Run a bounded developer session on /home/mnahtygal/projects/jarvis-repair-challenge. Source file: stock.py Test file: test_stock.py Verification: pytest -q test_stock.py Only stock.py may be modified. test_stock.py must remain read-only. Ask for approval before making any change. Do not use Git.";

test("bounded Python request builder produces the exact canonical request", () => {
  assert.equal(
    buildBoundedPythonSessionRequest(validInput),
    canonicalRequest
  );
});

test("launcher submission sends exactly one canonical text command", () => {
  const submittedCommands: string[] = [];
  const visibleSummary = "Workspace: /home/mnahtygal/projects/jarvis-repair-challenge Source: stock.py Test: test_stock.py";
  const originalFetch = globalThis.fetch;
  let directEndpointCalls = 0;
  globalThis.fetch = async () => {
    directEndpointCalls += 1;
    throw new Error("Launcher must not call a backend endpoint directly.");
  };

  try {
    const submittedRequest = submitBoundedPythonSessionRequest(
      validInput,
      (command) => submittedCommands.push(command)
    );

    assert.equal(submittedRequest, canonicalRequest);
    assert.deepEqual(submittedCommands, [canonicalRequest]);
    assert.notEqual(submittedCommands[0], visibleSummary);
    assert.equal(submittedCommands.includes("approve"), false);
    assert.equal(directEndpointCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("bounded Python request builder trims structured values without adding scope", () => {
  assert.equal(
    buildBoundedPythonSessionRequest({
      workspace: "  /tmp/project  ",
      sourceFile: " src/repair.py ",
      testFile: " tests/test_repair.py ",
    }),
    "Run a bounded developer session on /tmp/project. Source file: src/repair.py Test file: tests/test_repair.py Verification: pytest -q tests/test_repair.py Only src/repair.py may be modified. tests/test_repair.py must remain read-only. Ask for approval before making any change. Do not use Git."
  );
});

test("launcher validation accepts the supported structured scope", () => {
  assert.deepEqual(validateBoundedPythonSessionInput(validInput), {});
});

test("launcher validation rejects missing, non-Python, absolute, and identical paths", () => {
  assert.deepEqual(validateBoundedPythonSessionInput({
    workspace: "relative/project",
    sourceFile: "/tmp/source.txt",
    testFile: "/tmp/source.txt",
  }), {
    workspace: "Workspace must be an absolute path.",
    sourceFile: "Source file must be relative to the workspace.",
    testFile: "Test file must be relative to the workspace.",
  });

  assert.deepEqual(validateBoundedPythonSessionInput({
    workspace: "",
    sourceFile: "source.txt",
    testFile: "",
  }), {
    workspace: "Workspace is required.",
    sourceFile: "Source file must end in .py.",
    testFile: "Test file is required.",
  });

  assert.deepEqual(validateBoundedPythonSessionInput({
    workspace: "/tmp/project",
    sourceFile: "same.py",
    testFile: "same.py",
  }), {
    testFile: "Source and test files must be different.",
  });
});
