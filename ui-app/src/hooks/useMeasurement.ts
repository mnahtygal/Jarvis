import { useState } from "react";
import { measureLatestObject as measureLatestObjectApi } from "../services/jarvisApi";
import type { MeasurementResult } from "../types/dashboard";

type UseMeasurementOptions = {
  getLatestRectifiedImagePath: () => string | null;
  canMeasureLatestObject: () => boolean;
  refreshDashboard: (logResult?: boolean) => void;
  prependLogs: (entries: string[]) => void;
};

export function useMeasurement({
  getLatestRectifiedImagePath,
  canMeasureLatestObject,
  refreshDashboard,
  prependLogs,
}: UseMeasurementOptions) {
  const [measuring, setMeasuring] = useState(false);
  const [measurementResult, setMeasurementResult] = useState<MeasurementResult | null>(null);
  const [measurementMessage, setMeasurementMessage] = useState("");

  const measureLatestObject = async () => {
    if (measuring) return;

    const rectifiedImagePath = getLatestRectifiedImagePath();
    if (!rectifiedImagePath) {
      const message = "Run Scan Mat first; no rectified image is available yet.";
      setMeasurementMessage(message);
      prependLogs([`Measurement failed: ${message}`]);
      return;
    }

    if (!canMeasureLatestObject()) {
      const message = "Calibration is required before measurement.";
      setMeasurementMessage(message);
      prependLogs([`Measurement failed: ${message}`]);
      return;
    }

    setMeasuring(true);
    setMeasurementMessage("Measuring latest rectified scan...");
    prependLogs(["Measurement requested"]);

    try {
      const res = await measureLatestObjectApi(rectifiedImagePath);
      const data: MeasurementResult = await res.json();
      setMeasurementResult(data);

      if (!res.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      const width = data.measurement?.dimensions_mm?.long_side ?? data.measurement?.bbox_mm?.width;
      const height = data.measurement?.dimensions_mm?.short_side ?? data.measurement?.bbox_mm?.height;
      const message =
        width != null && height != null
          ? `Measurement complete: ${width} mm x ${height} mm`
          : "Measurement complete";
      setMeasurementMessage(message);
      prependLogs([message]);
      refreshDashboard(false);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unknown measurement error";
      setMeasurementMessage(`Measurement failed: ${message}`);
      prependLogs([`Measurement failed: ${message}`]);
      refreshDashboard(false);
    } finally {
      setMeasuring(false);
    }
  };

  return {
    measuring,
    measurementResult,
    measurementMessage,
    measureLatestObject,
  };
}
