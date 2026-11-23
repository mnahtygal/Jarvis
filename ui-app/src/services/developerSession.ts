export type BoundedPythonSessionInput = {
  workspace: string;
  sourceFile: string;
  testFile: string;
};

export type BoundedPythonSessionErrors = Partial<
  Record<keyof BoundedPythonSessionInput, string>
>;

function normalizedInput(input: BoundedPythonSessionInput): BoundedPythonSessionInput {
  return {
    workspace: input.workspace.trim(),
    sourceFile: input.sourceFile.trim(),
    testFile: input.testFile.trim(),
  };
}

function appearsAbsolute(path: string): boolean {
  return path.startsWith("/") || /^[A-Za-z]:[\\/]/.test(path) || path.startsWith("\\\\");
}

export function validateBoundedPythonSessionInput(
  input: BoundedPythonSessionInput
): BoundedPythonSessionErrors {
  const { workspace, sourceFile, testFile } = normalizedInput(input);
  const errors: BoundedPythonSessionErrors = {};

  if (!workspace) {
    errors.workspace = "Workspace is required.";
  } else if (!appearsAbsolute(workspace)) {
    errors.workspace = "Workspace must be an absolute path.";
  }

  if (!sourceFile) {
    errors.sourceFile = "Source file is required.";
  } else if (appearsAbsolute(sourceFile)) {
    errors.sourceFile = "Source file must be relative to the workspace.";
  } else if (!sourceFile.endsWith(".py")) {
    errors.sourceFile = "Source file must end in .py.";
  }

  if (!testFile) {
    errors.testFile = "Test file is required.";
  } else if (appearsAbsolute(testFile)) {
    errors.testFile = "Test file must be relative to the workspace.";
  } else if (!testFile.endsWith(".py")) {
    errors.testFile = "Test file must end in .py.";
  }

  if (
    sourceFile
    && testFile
    && sourceFile === testFile
    && !errors.sourceFile
    && !errors.testFile
  ) {
    errors.testFile = "Source and test files must be different.";
  }

  return errors;
}

export function buildBoundedPythonSessionRequest(
  input: BoundedPythonSessionInput
): string {
  const { workspace, sourceFile, testFile } = normalizedInput(input);

  return `Run a bounded developer session on ${workspace}. Source file: ${sourceFile} Test file: ${testFile} Verification: pytest -q ${testFile} Only ${sourceFile} may be modified. ${testFile} must remain read-only. Ask for approval before making any change. Do not use Git.`;
}

export function submitBoundedPythonSessionRequest(
  input: BoundedPythonSessionInput,
  submitTextCommand: (command: string) => void
): string {
  const request = buildBoundedPythonSessionRequest(input);
  submitTextCommand(request);
  return request;
}
