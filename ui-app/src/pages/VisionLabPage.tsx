import { useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { Camera, RefreshCw, ScanEye } from "lucide-react";
import type {
  CameraRolesStatus,
  CalibrationStatus,
  DashboardStatus,
  MeasurementResult,
  MeasurementStatus,
  ScanMatDiagnostics,
} from "../types/dashboard";
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
  switchCameraRole: (role: string) => void;
  checkLatestSnapshot: () => void;
  setScanMode: Dispatch<SetStateAction<ScanMode>>;
  dashboard: DashboardStatus | null;
  visionOnline: boolean;
  cameraDetected: boolean;
  busy: boolean;
  capturing: boolean;
  analyzing: boolean;
  scanningMat: boolean;
  switchingCameraRole: boolean;
  cameraRoles?: CameraRolesStatus | null;
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
  measurementStatus?: MeasurementStatus;
  measuring: boolean;
  measurementResult: MeasurementResult | null;
  measurementMessage: string;
  measureLatestObject: () => void;
  rectifiedImageAvailable: boolean;
  promptPreview: string;
  logs: string[];
};

export default function VisionLabPage({
  captureCameraSnapshot,
  analyzeLatestSnapshot,
  runScanMat,
  switchCameraRole,
  checkLatestSnapshot,
  setScanMode,
  dashboard,
  visionOnline,
  cameraDetected,
  busy,
  capturing,
  analyzing,
  scanningMat,
  switchingCameraRole,
  cameraRoles,
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
  measurementStatus,
  measuring,
  measurementResult,
  measurementMessage,
  measureLatestObject,
  rectifiedImageAvailable,
  promptPreview,
  logs,
}: VisionLabPageProps) {
  const [measurementUnit, setMeasurementUnit] = useState<"mm" | "in">("mm");
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
  const measurementDisabled =
    measuring || !measurementStatus?.calibration_ready || !rectifiedImageAvailable;
  const measurement = measurementResult?.measurement;
  const unitScale = measurementUnit === "in" ? 1 / 25.4 : 1;
  const areaUnitScale = measurementUnit === "in" ? 1 / (25.4 * 25.4) : 1;
  const lengthUnitLabel = measurementUnit === "in" ? "in" : "mm";
  const areaUnitLabel = measurementUnit === "in" ? "in²" : "mm²";
  const formatLength = (value?: number | null) =>
    value == null ? "unknown" : `${(value * unitScale).toFixed(measurementUnit === "in" ? 3 : 2)} ${lengthUnitLabel}`;
  const formatArea = (value?: number | null) =>
    value == null ? "unknown" : `${(value * areaUnitScale).toFixed(measurementUnit === "in" ? 3 : 2)} ${areaUnitLabel}`;
  const measurementDiagnostics = measurementResult?.diagnostics;
  const measurementFailureReason = measurementResult
    ? measurementDiagnostics?.failure_reason || "none"
    : rectifiedImageAvailable
      ? "Measurement not run"
      : "Waiting for rectified scan";
  const cameras = cameraRoles?.cameras || dashboard?.devices?.camera?.cameras || [];
  const activeCameraRole = cameraRoles?.active_role || dashboard?.devices?.camera?.active_role || "unknown";
  const activeCamera = cameraRoles?.active_camera || dashboard?.devices?.camera?.active_camera;

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
              Scan Mat uses the workbench camera role by default.
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
          <div
            style={{
              padding: 14,
              borderRadius: 14,
              background: "rgba(0,0,0,0.22)",
              border: "1px solid rgba(255,255,255,0.06)",
              fontSize: 13,
              lineHeight: 1.45,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <strong>Camera</strong>
              <span style={{ color: activeCamera?.available ? "#22c55e" : "#f97316", fontWeight: 800 }}>
                {activeCameraRole}
              </span>
            </div>
            <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
              {cameras.length ? (
                cameras.map((camera) => (
                  <label
                    key={camera.role || camera.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 10,
                      padding: "8px 10px",
                      borderRadius: 10,
                      border: "1px solid rgba(255,255,255,0.08)",
                      background: camera.role === activeCameraRole ? "rgba(34,197,94,0.1)" : "rgba(255,255,255,0.04)",
                    }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <input
                        type="radio"
                        checked={camera.role === activeCameraRole}
                        disabled={busy || switchingCameraRole || !camera.available || !camera.role}
                        onChange={() => camera.role && switchCameraRole(camera.role)}
                      />
                      <span>
                        {camera.display_name || camera.id || "Camera"} - {camera.role || "unknown"}
                      </span>
                    </span>
                    <span style={{ color: camera.available ? "#22c55e" : "#f97316", fontWeight: 800 }}>
                      {camera.available ? camera.resolved_device_path || "connected" : "missing"}
                    </span>
                  </label>
                ))
              ) : (
                <div style={{ opacity: 0.7 }}>Camera roles unavailable.</div>
              )}
            </div>
          </div>

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
              1. Select the workbench camera and keep the mat corners visible.
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
                placeholder="609.6"
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
                placeholder="457.2"
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
            <div>
              <div style={{ fontWeight: 800 }}>Measurement</div>
              <div style={{ marginTop: 6, opacity: 0.72, fontSize: 13, lineHeight: 1.4 }}>
                Measure the main object from the latest rectified scan.
              </div>
            </div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 800,
                color: measurementStatus?.measurement_engine_ready ? "#22c55e" : "#f97316",
              }}
            >
              {measurementStatus?.measurement_engine_ready ? "Ready" : "Not ready"}
            </div>
          </div>

          <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 10, alignItems: "center" }}>
            <ControlButton
              onClick={measureLatestObject}
              label={measuring ? "Measuring..." : "Measure Object"}
              icon={<ScanEye size={16} />}
              disabled={measurementDisabled}
            />
            <div style={{ opacity: 0.72, fontSize: 13 }}>
              {rectifiedImageAvailable ? "Rectified scan ready" : "No rectified scan yet"}
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
              Units
              <select
                value={measurementUnit}
                onChange={(event) => setMeasurementUnit(event.target.value as "mm" | "in")}
                style={{ background: "#111827", color: "#e5e7eb", border: "1px solid #374151", borderRadius: 6, padding: "5px 8px" }}
              >
                <option value="mm">millimeters</option>
                <option value="in">inches</option>
              </select>
            </label>
          </div>

          <div style={{ marginTop: 12, fontWeight: 800, color: "#67e8f9" }}>
            2D calibrated measurement
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
            <div>Long side: {formatLength(measurement?.dimensions_mm?.long_side)}</div>
            <div>Short side: {formatLength(measurement?.dimensions_mm?.short_side)}</div>
            <div>Rotation: {measurement?.rotated_box_px?.rotation_degrees?.toFixed(2) ?? "unknown"}°</div>
            <div>Contour area: {formatArea(measurement?.contour_area_mm2 ?? measurement?.area_mm2)}</div>
            <div>Confidence: {measurement?.confidence == null ? "unknown" : `${(measurement.confidence * 100).toFixed(1)}%`}</div>
            <div>Method: {measurement?.method || "unknown"}</div>
            <div>
              Bounding Box:{" "}
              {measurement?.bbox_px
                ? `${measurement.bbox_px.x ?? "?"}, ${measurement.bbox_px.y ?? "?"}, ${measurement.bbox_px.width ?? "?"}x${measurement.bbox_px.height ?? "?"}`
                : "unknown"}
            </div>
            <div>Measurement status: {measurementFailureReason}</div>
          </div>

          {measurement?.artifacts?.overlay_url && (
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>Measurement overlay</div>
              <img
                src={measurement.artifacts.overlay_url}
                alt="2D calibrated measurement overlay"
                style={{ display: "block", width: "100%", maxHeight: 560, objectFit: "contain", borderRadius: 10, border: "1px solid rgba(255,255,255,0.1)" }}
              />
            </div>
          )}

          <div style={{ marginTop: 12, color: "#fbbf24", fontSize: 12, lineHeight: 1.45 }}>
            Measurement accuracy depends on calibration, lighting, object contrast, camera alignment,
            and the object lying flat on the Scan Mat.
          </div>

          {measurementMessage && (
            <div
              style={{
                marginTop: 12,
                color: measurementMessage.startsWith("Measurement failed") ? "#f97316" : "#22c55e",
                fontSize: 13,
              }}
            >
              {measurementMessage}
            </div>
          )}
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
