import { useState } from "react";
import { applyCalibration } from "../services/jarvisApi";
import type { CalibrationApplyResponse } from "../types/dashboard";

type UseCalibrationOptions = {
  getLatestScanCorners: () => number[][] | null;
  getLatestScanImageSize: () => { width?: number; height?: number } | undefined;
  refreshDashboard: (logResult?: boolean) => void;
  prependLogs: (entries: string[]) => void;
  isScanMatBusy?: () => boolean;
};

export function useCalibration({
  getLatestScanCorners,
  getLatestScanImageSize,
  refreshDashboard,
  prependLogs,
  isScanMatBusy,
}: UseCalibrationOptions) {
  const [calibrationWidthMm, setCalibrationWidthMm] = useState("");
  const [calibrationHeightMm, setCalibrationHeightMm] = useState("");
  const [calibrating, setCalibrating] = useState(false);
  const [calibrationMessage, setCalibrationMessage] = useState("");

  const applyLatestScanCalibration = async () => {
    if (calibrating || isScanMatBusy?.()) return;

    const corners = getLatestScanCorners();
    if (!corners) {
      const message = "Run Scan Mat first; no corners are available yet.";
      setCalibrationMessage(message);
      prependLogs([`Calibration failed: ${message}`]);
      return;
    }

    const knownWidthMm = Number(calibrationWidthMm);
    const knownHeightMm = Number(calibrationHeightMm);
    if (!Number.isFinite(knownWidthMm) || knownWidthMm <= 0) {
      const message = "Calibration width must be a number greater than 0.";
      setCalibrationMessage(message);
      prependLogs([`Calibration failed: ${message}`]);
      return;
    }

    if (!Number.isFinite(knownHeightMm) || knownHeightMm <= 0) {
      const message = "Calibration height must be a number greater than 0.";
      setCalibrationMessage(message);
      prependLogs([`Calibration failed: ${message}`]);
      return;
    }

    setCalibrating(true);
    setCalibrationMessage("Applying calibration...");
    prependLogs(["Calibration apply requested"]);

    const imageSize = getLatestScanImageSize();

    try {
      const res = await applyCalibration({
        corners,
        known_width_mm: knownWidthMm,
        known_height_mm: knownHeightMm,
        image_width_px: imageSize?.width,
        image_height_px: imageSize?.height,
      });
      const data: CalibrationApplyResponse = await res.json();

      if (!res.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      const confidence =
        data.calibration?.confidence != null
          ? ` Confidence: ${data.calibration.confidence}`
          : "";
      const message = `Calibration saved.${confidence}`;
      setCalibrationMessage(message);
      prependLogs([message]);
      refreshDashboard(true);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unknown calibration error";
      setCalibrationMessage(`Calibration failed: ${message}`);
      prependLogs([`Calibration failed: ${message}`]);
    } finally {
      setCalibrating(false);
    }
  };

  return {
    calibrationWidthMm,
    calibrationHeightMm,
    setCalibrationWidthMm,
    setCalibrationHeightMm,
    calibrating,
    calibrationMessage,
    applyLatestScanCalibration,
  };
}
