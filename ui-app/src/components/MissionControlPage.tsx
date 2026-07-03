import { RefreshCw } from "lucide-react";
import type { DashboardStatus } from "../types/dashboard";
import ControlButton from "./ControlButton";
import MissionSection from "./MissionSection";

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

export default function MissionControlPage({
  dashboard,
  martybenchScore,
  refreshDashboard,
}: MissionControlPageProps) {
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
      </div>
    </div>
  );
}
