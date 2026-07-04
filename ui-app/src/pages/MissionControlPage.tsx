import { RefreshCw } from "lucide-react";
import type { CameraControlStatus, DashboardStatus } from "../types/dashboard";
import ControlButton from "../components/ControlButton";
import MissionSection from "../components/MissionSection";

type MartyBenchScore = {
  total?: number | null;
  max_total?: number;
  verdict?: string;
};

type MissionControlPageProps = {
  dashboard: DashboardStatus | null;
  martybenchScore?: MartyBenchScore;
  refreshDashboard: (logResult?: boolean) => void;
};

function detectedLabel(present?: boolean) {
  return present ? "detected" : "missing";
}

function formatControlStatus(control?: CameraControlStatus) {
  if (!control?.present) {
    return "missing";
  }

  const value = control.value ?? "unknown";
  return `present / value ${value}`;
}

export default function MissionControlPage({
  dashboard,
  martybenchScore,
  refreshDashboard,
}: MissionControlPageProps) {
  const cameraDiagnostics = dashboard?.camera_diagnostics;
  const captureDevice = cameraDiagnostics?.capture_device;
  const metadataDevice = cameraDiagnostics?.metadata_device;
  const cameraFormat = captureDevice?.format;
  const panControl = cameraDiagnostics?.controls?.pan_absolute;
  const tiltControl = cameraDiagnostics?.controls?.tilt_absolute;
  const zoomControl = cameraDiagnostics?.controls?.zoom_absolute;
  const gimbalStatus = cameraDiagnostics?.gimbal?.status;
  const extensionUnit = cameraDiagnostics?.extension_unit;
  const formatValue =
    cameraFormat?.width && cameraFormat?.height
      ? `${cameraFormat.width}x${cameraFormat.height} / ${cameraFormat.pixel_format || "unknown"} / ${cameraFormat.fps || "unknown fps"}`
      : "Unknown";

  return (
    <div>
      <div
        style={{
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 20,
          padding: 24,
          marginBottom: 20,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div>
          <h2 style={{ margin: 0 }}>Mission Control</h2>
          <div style={{ opacity: 0.74, marginTop: 6 }}>
            Read-only operations view for Thor and Jarvis.
          </div>
        </div>
        <ControlButton
          onClick={() => refreshDashboard(true)}
          label="Refresh Dashboard"
          icon={<RefreshCw size={16} />}
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: 20,
        }}
      >
        <MissionSection
          title="Core Services"
          rows={[
            {
              label: "Brain",
              value: dashboard?.brain?.overall || "Unknown",
              ok: dashboard?.brain?.ready,
            },
            {
              label: "Active Model",
              value: dashboard?.model?.active_model_name || dashboard?.model?.detail || "Unknown",
              ok: dashboard?.model?.online,
            },
            {
              label: "Vision",
              value: dashboard?.vision?.overall || dashboard?.vision?.detail || "Unknown",
              ok: dashboard?.vision?.online,
            },
            {
              label: "PostgreSQL",
              value: dashboard?.memory?.postgres?.detail || dashboard?.brain?.postgres || "Unknown",
              ok: dashboard?.memory?.postgres?.online,
            },
            {
              label: "Semantic Memory",
              value: dashboard?.memory?.semantic_memory?.detail || dashboard?.brain?.semantic_memory || "Unknown",
              ok: dashboard?.memory?.semantic_memory?.online,
            },
            {
              label: "Local Embeddings",
              value: dashboard?.memory?.local_embeddings?.detail || dashboard?.brain?.local_embeddings || "Unknown",
              ok: dashboard?.memory?.local_embeddings?.online,
            },
          ]}
        />

        <MissionSection
          title="Runtime"
          rows={[
            {
              label: "Host",
              value: dashboard?.brain?.runtime?.host || dashboard?.model?.host || "Thor",
            },
            {
              label: "Engine",
              value: dashboard?.brain?.runtime?.engine || dashboard?.model?.runtime || "llama.cpp",
            },
            {
              label: "Model ID",
              value: dashboard?.model?.active_model_id || "Unknown",
            },
            {
              label: "Vision Port",
              value: dashboard?.vision?.port ? String(dashboard.vision.port) : "Unknown",
            },
            {
              label: "Last Topic",
              value: dashboard?.brain?.last_topic || dashboard?.memory?.last_topic || "Unknown",
            },
            {
              label: "Recent History Rows",
              value: String(
                dashboard?.brain?.recent_history_rows_checked
                  ?? dashboard?.memory?.recent_history?.rows_checked
                  ?? "?"
              ),
            },
          ]}
        />

        <MissionSection
          title="Devices"
          rows={[
            {
              label: "Microphone",
              value: `${dashboard?.devices?.microphone?.detected ? "Detected" : "Missing"} / ${dashboard?.devices?.microphone?.name || "unknown"}`,
              ok: dashboard?.devices?.microphone?.detected,
            },
            {
              label: "Camera",
              value: `${dashboard?.devices?.camera?.detected ? "Detected" : "Missing"} / ${dashboard?.devices?.camera?.name || "unknown"}`,
              ok: dashboard?.devices?.camera?.detected,
            },
            {
              label: "Camera Path",
              value: dashboard?.devices?.camera?.expected_device || "Unknown",
              ok: dashboard?.devices?.camera?.expected_device_present,
            },
            {
              label: "Audio Backend",
              value: dashboard?.devices?.audio_backend || "Unknown",
            },
            {
              label: "Dock Note",
              value: dashboard?.devices?.dock_note || "Unknown",
            },
          ]}
        />

        <MissionSection
          title="MartyBench"
          rows={[
            {
              label: "Available",
              value: dashboard?.martybench?.available ? "Yes" : "No",
              ok: dashboard?.martybench?.available,
            },
            {
              label: "Run ID",
              value: dashboard?.martybench?.run_id || "Unknown",
            },
            {
              label: "Variant",
              value: dashboard?.martybench?.variant || "Unknown",
            },
            {
              label: "Score",
              value:
                martybenchScore?.total != null
                  ? `${martybenchScore.total}/${martybenchScore.max_total || 35}`
                  : "No score",
            },
            {
              label: "Verdict",
              value: martybenchScore?.verdict || "Unknown",
            },
          ]}
        />

        <MissionSection
          title="Camera Diagnostics"
          rows={[
            {
              label: "Overall",
              value: cameraDiagnostics?.overall || "Unknown",
              ok: cameraDiagnostics?.ready,
            },
            {
              label: "Capture Device",
              value: `${captureDevice?.path || "/dev/video0"} ${detectedLabel(captureDevice?.present)}`,
              ok: captureDevice?.present,
            },
            {
              label: "Metadata Device",
              value: `${metadataDevice?.path || "/dev/video1"} ${detectedLabel(metadataDevice?.present)}`,
              ok: metadataDevice?.present,
            },
            {
              label: "Format",
              value: formatValue,
            },
            {
              label: "Pan Control",
              value: formatControlStatus(panControl),
              ok: panControl?.present,
            },
            {
              label: "Tilt Control",
              value: formatControlStatus(tiltControl),
              ok: tiltControl?.present,
            },
            {
              label: "Zoom Control",
              value: formatControlStatus(zoomControl),
              ok: zoomControl?.present,
            },
            {
              label: "Gimbal Path",
              value: gimbalStatus || "Unknown",
              ok: gimbalStatus === "extension_unit_required" ? false : undefined,
            },
            {
              label: "Extension Unit",
              value: `${extensionUnit?.detected ? "detected" : "missing"} / Unit ${extensionUnit?.unit_id ?? "unknown"} / ${extensionUnit?.controls ?? "unknown"} controls`,
              ok: extensionUnit?.detected,
            },
            {
              label: "Extension GUID",
              value: extensionUnit?.guid || "Unknown",
            },
          ]}
        />
      </div>
    </div>
  );
}
