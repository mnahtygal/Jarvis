import type { Dispatch, ReactNode, SetStateAction } from "react";
import {
  Activity,
  Brain,
  Camera,
  MessageSquare,
  Mic,
  Power,
  RefreshCw,
  ScanEye,
  Volume2,
  VolumeX,
} from "lucide-react";
import type { DashboardStatus } from "../types/dashboard";
import ActivityLog from "./ActivityLog";
import ControlButton from "./ControlButton";
import GlowRing from "./GlowRing";

type HomePageProps = {
  runVoiceAsk: () => void;
  captureCameraSnapshot: () => void;
  analyzeLatestSnapshot: (mode: "general") => void;
  checkApi: () => void;
  refreshDashboard: (logResult?: boolean) => void;
  runQuickCommand: (quickCommand: string) => void;
  sendTypedCommand: () => void;
  setVoiceEnabled: Dispatch<SetStateAction<boolean>>;
  setCommand: Dispatch<SetStateAction<string>>;
  listening: boolean;
  processing: boolean;
  capturing: boolean;
  analyzing: boolean;
  busy: boolean;
  cameraDetected: boolean;
  snapshotAvailable: boolean;
  snapshotPanel: ReactNode;
  quickCommands: string[];
  command: string;
  voiceEnabled: boolean;
  dashboard: DashboardStatus | null;
  logs: string[];
};

export default function HomePage({
  runVoiceAsk,
  captureCameraSnapshot,
  analyzeLatestSnapshot,
  checkApi,
  refreshDashboard,
  runQuickCommand,
  sendTypedCommand,
  setVoiceEnabled,
  setCommand,
  listening,
  processing,
  capturing,
  analyzing,
  busy,
  cameraDetected,
  snapshotAvailable,
  snapshotPanel,
  quickCommands,
  command,
  voiceEnabled,
  dashboard,
  logs,
}: HomePageProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1.25fr 1fr",
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
        <GlowRing listening={listening} processing={processing || capturing || analyzing} />

        <div
          style={{
            marginTop: 24,
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
          }}
        >
          <ControlButton
            onClick={runVoiceAsk}
            disabled={busy}
            label={listening ? "Listening..." : processing ? "Working..." : "Listen"}
            icon={<Mic size={16} />}
          />
          <ControlButton
            onClick={captureCameraSnapshot}
            label={capturing ? "Capturing..." : "Camera"}
            icon={<Camera size={16} />}
            disabled={!cameraDetected || busy}
          />
          <ControlButton
            onClick={() => analyzeLatestSnapshot("general")}
            label={analyzing ? "Analyzing..." : "Analyze Snapshot"}
            icon={<ScanEye size={16} />}
            disabled={!snapshotAvailable || busy}
          />
          <ControlButton
            onClick={checkApi}
            label="Status"
            icon={<Activity size={16} />}
          />
          <ControlButton
            label="Power"
            icon={<Power size={16} />}
            disabled
          />
          <ControlButton
            onClick={() => setVoiceEnabled((v) => !v)}
            label={voiceEnabled ? "Voice On" : "Voice Off"}
            icon={voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          />
          <ControlButton
            onClick={() => refreshDashboard(true)}
            label="Refresh Dashboard"
            icon={<RefreshCw size={16} />}
          />
        </div>

        {snapshotAvailable && snapshotPanel}

        <div style={{ marginTop: 24 }}>
          <div style={{ marginBottom: 10, opacity: 0.85 }}>Dashboard quick commands</div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 10,
            }}
          >
            {quickCommands.map((quickCommand) => (
              <ControlButton
                key={quickCommand}
                onClick={() => runQuickCommand(quickCommand)}
                disabled={busy}
                label={quickCommand}
                icon={<MessageSquare size={16} />}
              />
            ))}
          </div>
        </div>

        <div style={{ marginTop: 24 }}>
          <div style={{ marginBottom: 10, opacity: 0.85 }}>Typed command</div>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendTypedCommand()}
              placeholder="Type command... try: what model are you using"
              style={{
                flex: 1,
                padding: 12,
                borderRadius: 12,
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(0,0,0,0.22)",
                color: "white",
                outline: "none",
              }}
            />
            <button
              onClick={sendTypedCommand}
              disabled={busy}
              style={{
                padding: "12px 16px",
                borderRadius: 12,
                border: "1px solid rgba(255,255,255,0.12)",
                background: "white",
                color: "#020617",
                fontWeight: 700,
                cursor: busy ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <MessageSquare size={16} />
              Send
            </button>
          </div>
        </div>

        <div style={{ marginTop: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, opacity: 0.85 }}>
            <Brain size={16} />
            Live details
          </div>
          <div
            style={{
              marginTop: 10,
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 10,
              fontSize: 13,
              opacity: 0.82,
            }}
          >
            <div>Last topic: {dashboard?.brain?.last_topic || "unknown"}</div>
            <div>History rows: {dashboard?.brain?.recent_history_rows_checked ?? "?"}</div>
            <div>LLM: {dashboard?.brain?.llm_endpoint || "unknown"}</div>
            <div>Vision: {dashboard?.vision?.detail || "unknown"}</div>
            <div>MartyBench run: {dashboard?.martybench?.run_id || "unknown"}</div>
            <div>Mic: {dashboard?.devices?.microphone?.detected ? dashboard?.devices?.microphone?.name || "detected" : "unknown"}</div>
            <div>Camera: {dashboard?.devices?.camera?.expected_device || "unknown"}</div>
          </div>
        </div>
      </div>

      <ActivityLog logs={logs} />
    </div>
  );
}
