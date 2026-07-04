import type { Dispatch, ReactNode, SetStateAction } from "react";
import { Camera, RefreshCw, ScanEye } from "lucide-react";
import type { CalibrationStatus, DashboardStatus, ScanMatDiagnostics } from "../types/dashboard";
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
  scanMatDiagnostics: ScanMatDiagnostics | null;
  latestScanCornersAvailable: boolean;
  calibrationWidthMm: string;
  calibrationHeightMm: string;
  setCalibrationWidthMm: Dispatch<SetStateAction<string>>;
  setCalibrationHeightMm: Dispatch<SetStateAction<string>>;
  calibrating: boolean;
  calibrationMessage: string;
  applyLatestScanCalibration: () => void;
  calibrationStatus?: CalibrationStatus;
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
  scanMatDiagnostics,
  latestScanCornersAvailable,
  calibrationWidthMm,
  calibrationHeightMm,
  setCalibrationWidthMm,
  setCalibrationHeightMm,
  calibrating,
  calibrationMessage,
  applyLatestScanCalibration,
  calibrationStatus,
  promptPreview,
  logs,
}: VisionLabPageProps) {
  const widthValue = Number(calibrationWidthMm);
  const heightValue = Number(calibrationHeightMm);
  const calibrationDimensionsValid =
    Number.isFinite(widthValue) && widthValue > 0 && Number.isFinite(heightValue) && heightValue > 0;
  const calibrationDisabled =
    calibrating || scanningMat || !latestScanCornersAvailable || !calibrationDimensionsValid;
  const formatRatio = (value?: number | null) =>
    value == null ? "unknown" : `${(value * 100).toFixed(1)}%`;
  const formatCount = (value?: number | null) => value ?? "unknown";
  const detectionStatus = scanMatDiagnostics
    ? scanMatDiagnostics.corners_detected
      ? "Corners detected"
      : "Corners not detected"
    : "No scan yet";

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

        <div
          style={{
            marginTop: 22,
            padding: 16,
            borderRadius: 14,
            background: "rgba(0,0,0,0.22)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 800 }}>Calibration</div>
              <div style={{ marginTop: 6, opacity: 0.72, fontSize: 13, lineHeight: 1.4 }}>
                Run Scan Mat first, then enter the real-world mat size and apply calibration.
              </div>
            </div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 800,
                color: calibrationStatus?.ready ? "#22c55e" : "#f97316",
              }}
            >
              {calibrationStatus?.status || "unknown"}
            </div>
          </div>

          <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <label style={{ display: "grid", gap: 6, fontSize: 13, opacity: 0.86 }}>
              Width mm
              <input
                value={calibrationWidthMm}
                onChange={(event) => setCalibrationWidthMm(event.target.value)}
                inputMode="decimal"
                placeholder="420"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: 12,
                  borderRadius: 12,
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "rgba(0,0,0,0.34)",
                  color: "white",
                  outline: "none",
                }}
              />
            </label>
            <label style={{ display: "grid", gap: 6, fontSize: 13, opacity: 0.86 }}>
              Height mm
              <input
                value={calibrationHeightMm}
                onChange={(event) => setCalibrationHeightMm(event.target.value)}
                inputMode="decimal"
                placeholder="297"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  padding: 12,
                  borderRadius: 12,
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "rgba(0,0,0,0.34)",
                  color: "white",
                  outline: "none",
                }}
              />
            </label>
          </div>

          <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
            <ControlButton
              onClick={applyLatestScanCalibration}
              label={calibrating ? "Applying..." : "Apply Calibration"}
              icon={<ScanEye size={16} />}
              disabled={calibrationDisabled}
            />
            <div style={{ opacity: 0.72, fontSize: 13 }}>
              {latestScanCornersAvailable ? "Latest scan corners ready" : "No scan corners yet"}
            </div>
          </div>

          <div style={{ marginTop: 12, display: "grid", gap: 4, fontSize: 13, opacity: 0.76 }}>
            <div>Confidence: {calibrationStatus?.confidence ?? "unknown"}</div>
            <div>
              mm / px: x {calibrationStatus?.mm_per_pixel_x ?? "unknown"} · y{" "}
              {calibrationStatus?.mm_per_pixel_y ?? "unknown"}
            </div>
            <div>Last calibrated: {calibrationStatus?.last_calibrated_at || "never"}</div>
            {calibrationMessage && (
              <div style={{ marginTop: 4, color: calibrationMessage.startsWith("Calibration failed") ? "#f97316" : "#22c55e" }}>
                {calibrationMessage}
              </div>
            )}
          </div>
        </div>

        {snapshotPanel}
        {scanMatPanel}

        <div
          style={{
            marginTop: 22,
            padding: 16,
            borderRadius: 14,
            background: "rgba(0,0,0,0.22)",
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
            <div style={{ fontWeight: 800 }}>Scan Mat Diagnostics</div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 800,
                color: scanMatDiagnostics?.corners_detected ? "#22c55e" : "#f97316",
              }}
            >
              {detectionStatus}
            </div>
          </div>

          <div
            style={{
              marginTop: 12,
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 8,
              fontSize: 13,
              opacity: 0.78,
            }}
          >
            <div>Failure reason: {scanMatDiagnostics?.failure_reason || "none"}</div>
            <div>
              Image size:{" "}
              {scanMatDiagnostics?.image_width && scanMatDiagnostics?.image_height
                ? `${scanMatDiagnostics.image_width}x${scanMatDiagnostics.image_height}`
                : "unknown"}
            </div>
            <div>Contours: {formatCount(scanMatDiagnostics?.contour_count)}</div>
            <div>Candidate quads: {formatCount(scanMatDiagnostics?.candidate_quad_count)}</div>
            <div>Largest area: {formatRatio(scanMatDiagnostics?.largest_contour_area_ratio)}</div>
            <div>Selected area: {formatRatio(scanMatDiagnostics?.selected_quad_area_ratio)}</div>
          </div>

          {scanMatDiagnostics?.suggestions?.length ? (
            <div style={{ marginTop: 12, fontSize: 13, opacity: 0.76, lineHeight: 1.45 }}>
              {scanMatDiagnostics.suggestions.map((suggestion) => (
                <div key={suggestion}>{suggestion}</div>
              ))}
            </div>
          ) : (
            <div style={{ marginTop: 12, fontSize: 13, opacity: 0.62 }}>
              Run Scan Mat to populate diagnostics.
            </div>
          )}
        </div>

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
