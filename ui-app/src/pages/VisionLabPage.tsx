import type { Dispatch, ReactNode, SetStateAction } from "react";
import { Camera, RefreshCw, ScanEye } from "lucide-react";
import type { DashboardStatus } from "../types/dashboard";
import ActivityLog from "../components/ActivityLog";
import ControlButton from "../components/ControlButton";

type ScanMode = "general" | "object" | "measurement" | "ocr" | "print" | "jetski" | "workbench";

type ScanModeOption = {
  id: ScanMode;
  label: string;
  detail: string;
};

type VisionLabPageProps = {
  captureCameraSnapshot: () => void;
  analyzeLatestSnapshot: (mode: ScanMode) => void;
  runScanMat: () => void;
  checkLatestSnapshot: () => void;
  setScanMode: Dispatch<SetStateAction<ScanMode>>;
  dashboard: DashboardStatus | null;
  visionOnline: boolean;
  cameraDetected: boolean;
  busy: boolean;
  capturing: boolean;
  analyzing: boolean;
  scanningMat: boolean;
  scanMode: ScanMode;
  scanModes: ScanModeOption[];
  selectedScanMode: ScanModeOption;
  snapshotAvailable: boolean;
  snapshotPanel: ReactNode;
  scanMatPanel: ReactNode;
  promptPreview: string;
  logs: string[];
};

export default function VisionLabPage({
  captureCameraSnapshot,
  analyzeLatestSnapshot,
  runScanMat,
  checkLatestSnapshot,
  setScanMode,
  dashboard,
  visionOnline,
  cameraDetected,
  busy,
  capturing,
  analyzing,
  scanningMat,
  scanMode,
  scanModes,
  selectedScanMode,
  snapshotAvailable,
  snapshotPanel,
  scanMatPanel,
  promptPreview,
  logs,
}: VisionLabPageProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1.3fr 1fr",
        gap: 20,
      }}
    >
      <div
        style={{
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 20,
          padding: 24,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ margin: 0 }}>Vision Lab</h2>
            <div style={{ opacity: 0.74, marginTop: 6 }}>
              Scan mat mode for objects, parts, OCR, measurements, and workshop inspection.
              Capture Mat uses the current camera angle — point the Insta360 down first.
            </div>
          </div>
          <div
            style={{
              padding: "8px 12px",
              borderRadius: 999,
              background: visionOnline ? "rgba(34,197,94,0.14)" : "rgba(239,68,68,0.14)",
              border: "1px solid rgba(255,255,255,0.08)",
              fontWeight: 700,
              fontSize: 13,
            }}
          >
            Vision {dashboard?.vision?.overall || "Unknown"}
          </div>
        </div>

        <div style={{ marginTop: 22, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div>
            <div style={{ marginBottom: 8, opacity: 0.85 }}>Scan mode</div>
            <select
              value={scanMode}
              onChange={(e) => setScanMode(e.target.value as ScanMode)}
              style={{
                width: "100%",
                padding: 12,
                borderRadius: 12,
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(0,0,0,0.34)",
                color: "white",
                outline: "none",
              }}
            >
              {scanModes.map((mode) => (
                <option key={mode.id} value={mode.id} style={{ color: "black" }}>
                  {mode.label}
                </option>
              ))}
            </select>
            <div style={{ marginTop: 8, opacity: 0.72, fontSize: 13 }}>{selectedScanMode.detail}</div>
          </div>

          <div
            style={{
              padding: 14,
              borderRadius: 14,
              background: "rgba(0,0,0,0.22)",
              border: "1px solid rgba(255,255,255,0.06)",
              fontSize: 13,
              lineHeight: 1.45,
              opacity: 0.88,
            }}
          >
            <strong>Workbench position checklist</strong>
            <div style={{ marginTop: 6 }}>
              1. Use Insta360 Link Controller / DeskView to point camera down.
              <br />
              2. Confirm the mat fills most of the preview.
              <br />
              3. Center the object on the grid before Capture Mat.
            </div>
          </div>
        </div>

        <div style={{ marginTop: 22, display: "flex", flexWrap: "wrap", gap: 10 }}>
          <ControlButton
            onClick={captureCameraSnapshot}
            label={capturing ? "Capturing..." : "Capture Current View"}
            icon={<Camera size={16} />}
            disabled={!cameraDetected || busy}
          />
          <ControlButton
            onClick={() => analyzeLatestSnapshot(scanMode)}
            label={analyzing ? "Analyzing..." : `Analyze: ${selectedScanMode.label}`}
            icon={<ScanEye size={16} />}
            disabled={!snapshotAvailable || busy}
          />
          <ControlButton
            onClick={runScanMat}
            label={scanningMat ? "Scanning Mat..." : "Scan Mat"}
            icon={<ScanEye size={16} />}
            disabled={!cameraDetected || busy}
          />
          <ControlButton
            onClick={checkLatestSnapshot}
            label="Refresh Snapshot"
            icon={<RefreshCw size={16} />}
            disabled={busy}
          />
        </div>

        {snapshotPanel}
        {scanMatPanel}

        <div style={{ marginTop: 22 }}>
          <div style={{ marginBottom: 10, opacity: 0.85 }}>Prompt preview</div>
          <div
            style={{
              padding: 14,
              borderRadius: 14,
              background: "rgba(0,0,0,0.22)",
              border: "1px solid rgba(255,255,255,0.06)",
              whiteSpace: "pre-wrap",
              lineHeight: 1.45,
              fontSize: 13,
              opacity: 0.82,
            }}
          >
            {promptPreview}
          </div>
        </div>
      </div>

      <ActivityLog logs={logs} />
    </div>
  );
}
