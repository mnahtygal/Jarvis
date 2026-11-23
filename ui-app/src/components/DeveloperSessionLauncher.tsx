import { useState, type FormEvent } from "react";
import { Code2, ShieldCheck } from "lucide-react";
import {
  submitBoundedPythonSessionRequest,
  validateBoundedPythonSessionInput,
  type BoundedPythonSessionInput,
} from "../services/developerSession";

type DeveloperSessionLauncherProps = {
  busy: boolean;
  onSubmitRequest: (request: string) => void;
};

const emptyInput: BoundedPythonSessionInput = {
  workspace: "",
  sourceFile: "",
  testFile: "",
};

const inputStyle = {
  width: "100%",
  minWidth: 0,
  padding: 11,
  borderRadius: 10,
  border: "1px solid rgba(255,255,255,0.12)",
  background: "rgba(0,0,0,0.22)",
  color: "white",
  outline: "none",
} as const;

export default function DeveloperSessionLauncher({
  busy,
  onSubmitRequest,
}: DeveloperSessionLauncherProps) {
  const [input, setInput] = useState(emptyInput);
  const [errors, setErrors] = useState(
    validateBoundedPythonSessionInput(emptyInput)
  );
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const workspace = input.workspace.trim();
  const sourceFile = input.sourceFile.trim();
  const testFile = input.testFile.trim();

  const updateInput = (field: keyof BoundedPythonSessionInput, value: string) => {
    const next = { ...input, [field]: value };
    setInput(next);
    if (hasSubmitted) {
      setErrors(validateBoundedPythonSessionInput(next));
    }
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors = validateBoundedPythonSessionInput(input);
    setHasSubmitted(true);
    setErrors(nextErrors);
    if (busy || Object.keys(nextErrors).length > 0) return;

    submitBoundedPythonSessionRequest(input, onSubmitRequest);
  };

  return (
    <section className="developer-session-panel" aria-labelledby="developer-session-title">
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <Code2 size={18} />
        <div id="developer-session-title" style={{ fontSize: 18, fontWeight: 800 }}>
          Developer Session
        </div>
      </div>
      <div style={{ marginTop: 7, opacity: 0.74, fontSize: 13, lineHeight: 1.45 }}>
        Prepare a bounded Python repair request. Jarvis will still require a separate,
        explicit approval before anything runs.
      </div>

      <form onSubmit={submit} noValidate>
        <div className="developer-session-fields">
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>
            Workspace
            <input
              value={input.workspace}
              onChange={(event) => updateInput("workspace", event.target.value)}
              placeholder="/home/marty/project"
              disabled={busy}
              aria-invalid={hasSubmitted && Boolean(errors.workspace)}
              aria-describedby={hasSubmitted && errors.workspace ? "workspace-error" : undefined}
              style={inputStyle}
            />
            {hasSubmitted && errors.workspace && (
              <span id="workspace-error" className="developer-session-error">
                {errors.workspace}
              </span>
            )}
          </label>

          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>
            Source file
            <input
              value={input.sourceFile}
              onChange={(event) => updateInput("sourceFile", event.target.value)}
              placeholder="stock.py"
              disabled={busy}
              aria-invalid={hasSubmitted && Boolean(errors.sourceFile)}
              aria-describedby={hasSubmitted && errors.sourceFile ? "source-file-error" : undefined}
              style={inputStyle}
            />
            {hasSubmitted && errors.sourceFile && (
              <span id="source-file-error" className="developer-session-error">
                {errors.sourceFile}
              </span>
            )}
          </label>

          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>
            Test file
            <input
              value={input.testFile}
              onChange={(event) => updateInput("testFile", event.target.value)}
              placeholder="test_stock.py"
              disabled={busy}
              aria-invalid={hasSubmitted && Boolean(errors.testFile)}
              aria-describedby={hasSubmitted && errors.testFile ? "test-file-error" : undefined}
              style={inputStyle}
            />
            {hasSubmitted && errors.testFile && (
              <span id="test-file-error" className="developer-session-error">
                {errors.testFile}
              </span>
            )}
          </label>
        </div>

        <div className="developer-session-summary" aria-label="Fixed developer session safety properties">
          <div><strong>Verification:</strong> pytest -q {testFile || "<test file>"}</div>
          <div><strong>Writable:</strong> {sourceFile || "<source file>"} only</div>
          <div><strong>Read-only:</strong> {testFile || "<test file>"}</div>
          <div><strong>Git:</strong> disabled</div>
          <div><strong>Approval:</strong> required</div>
          <div><strong>Workspace:</strong> {workspace || "<absolute workspace>"}</div>
        </div>

        <button
          type="submit"
          disabled={busy}
          style={{
            marginTop: 12,
            padding: "11px 15px",
            borderRadius: 11,
            border: "1px solid rgba(34,211,238,0.34)",
            background: "rgba(34,211,238,0.14)",
            color: "#cffafe",
            fontWeight: 800,
            cursor: busy ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <ShieldCheck size={16} />
          Prepare Developer Session
        </button>
      </form>
    </section>
  );
}
