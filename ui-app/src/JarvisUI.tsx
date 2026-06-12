import { useEffect, useMemo, useState } from "react";
import {
  Mic,
  Camera,
  Activity,
  Power,
  Clock3,
  MessageSquare,
  Volume2,
  VolumeX,
  RefreshCw,
  Brain,
  Database,
  Cpu,
  Gauge,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import ActivityLog from "./components/ActivityLog";
import ControlButton from "./components/ControlButton";
import GlowRing from "./components/GlowRing";
import StatusCard from "./components/StatusCard";
import type { AskResponse, DashboardStatus } from "./types/dashboard";

export default function JarvisUI() {
  const apiBase = useMemo(() => "http://127.0.0.1:5000", []);
  const [listening, setListening] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [command, setCommand] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [apiStatus, setApiStatus] = useState("Checking API...");
  const [dashboard, setDashboard] = useState<DashboardStatus | null>(null);
  const [dashboardStatus, setDashboardStatus] = useState("Checking dashboard...");
  const [logs, setLogs] = useState<string[]>([
    "Jarvis UI online",
    "Ready for voice or typed commands",
  ]);

  const [time, setTime] = useState(
    new Date().toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    })
  );

  useEffect(() => {
    const timer = setInterval(() => {
      setTime(
        new Date().toLocaleTimeString([], {
          hour: "numeric",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const prependLogs = (entries: string[]) => {
    setLogs((prev) => [...entries, ...prev].slice(0, 80));
  };

  const quickCommands = [
    "brain status",
    "semantic memory status",
    "show memory categories",
    "show cruise memories",
    "show project memories",
    "show work memories",
  ];

  const refreshDashboard = async (logResult = false) => {
    try {
      const res = await fetch(`${apiBase}/api/status/dashboard`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data: DashboardStatus = await res.json();
      setDashboard(data);
      setDashboardStatus("Dashboard connected");

      if (logResult) {
        prependLogs(["Dashboard status refreshed"]);
      }
    } catch (error) {
      console.error(error);
      setDashboardStatus("Dashboard offline");
      if (logResult) {
        prependLogs(["Dashboard status refresh failed"]);
      }
    }
  };

  const runQuickCommand = async (quickCommand: string) => {
    if (listening || processing) return;

    setProcessing(true);
    prependLogs([`You: ${quickCommand}`]);

    try {
      const res = await fetch(`${apiBase}/text`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          command: quickCommand,
          use_voice: false,
        }),
      });

      const data: AskResponse = await res.json();
      prependLogs([`Jarvis: ${data.response || "(no response)"}`]);
      refreshDashboard(false);
    } catch (error) {
      console.error(error);
      prependLogs([`Failed to run quick command: ${quickCommand}`]);
    } finally {
      setProcessing(false);
    }
  };

  const checkApi = async () => {
    try {
      const res = await fetch(`${apiBase}/health`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      setApiStatus("API connected");
      prependLogs(["Backend health check passed"]);
    } catch (error) {
      console.error(error);
      setApiStatus("API offline");
      prependLogs(["Backend health check failed"]);
    }

    refreshDashboard(true);
  };

  useEffect(() => {
    checkApi();
    const dashboardTimer = setInterval(() => refreshDashboard(false), 30000);
    return () => clearInterval(dashboardTimer);
  }, []);

  const runVoiceAsk = async () => {
    if (listening || processing) return;

    setListening(true);
    prependLogs(["Listening requested from UI"]);

    try {
      const res = await fetch(`${apiBase}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          use_voice: voiceEnabled,
        }),
      });

      const data: AskResponse = await res.json();

      setListening(false);
      setProcessing(true);

      prependLogs([
        `You: ${data.heard || "(nothing heard)"}`,
        `Jarvis: ${data.response || "(no response)"}`,
      ]);
      refreshDashboard(false);
    } catch (error) {
      console.error(error);
      setListening(false);
      prependLogs(["Jarvis API call failed"]);
    } finally {
      setProcessing(false);
    }
  };

  const sendTypedCommand = async () => {
    const trimmed = command.trim();
    if (!trimmed || listening || processing) return;

    setProcessing(true);
    prependLogs([`You: ${trimmed}`]);

    try {
      const res = await fetch(`${apiBase}/text`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          command: trimmed,
          use_voice: false,
        }),
      });

      const data: AskResponse = await res.json();
      prependLogs([`Jarvis: ${data.response || "(no response)"}`]);
      setCommand("");
      refreshDashboard(false);
    } catch (error) {
      console.error(error);
      prependLogs(["Failed to send typed command"]);
    } finally {
      setProcessing(false);
    }
  };

  const brainReady = dashboard?.brain?.ready ?? false;
  const modelOnline = dashboard?.model?.online ?? false;
  const postgresOnline = dashboard?.memory?.postgres?.online ?? false;
  const semanticOnline = dashboard?.memory?.semantic_memory?.online ?? false;
  const martybenchScore = dashboard?.martybench?.score;

  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(circle at top, rgba(34,211,238,0.14), transparent 25%), #020617",
        color: "white",
        padding: 20,
        fontFamily: "Arial, Helvetica, sans-serif",
      }}
    >
      <div
        style={{
          maxWidth: 1220,
          margin: "0 auto",
        }}
      >
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: 34, marginBottom: 8 }}>Jarvis Command Center</h1>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 16,
              opacity: 0.8,
              fontSize: 14,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Clock3 size={16} />
              {time}
            </div>
            <div>API: {apiStatus}</div>
            <div>Dashboard: {dashboardStatus}</div>
            <div>Voice: {voiceEnabled ? "On" : "Off"}</div>
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gap: 14,
            marginBottom: 20,
          }}
        >
          <StatusCard
            title="Brain"
            value={dashboard?.brain?.overall || "Unknown"}
            detail={`${dashboard?.brain?.runtime?.host || "Thor"} / ${dashboard?.brain?.runtime?.model || "unknown"} / ${dashboard?.brain?.runtime?.engine || "llama.cpp"}`}
            icon={brainReady ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}
            ok={brainReady}
          />
          <StatusCard
            title="Active Model"
            value={dashboard?.model?.active_model_name || "Unknown"}
            detail={dashboard?.model?.active_model_id || dashboard?.model?.detail || "No model data yet"}
            icon={<Cpu size={20} />}
            ok={modelOnline}
          />
          <StatusCard
            title="Memory"
            value={`${dashboard?.memory?.exact_memory?.fact_count ?? "?"} facts / ${dashboard?.brain?.semantic_memory || "semantic ?"}`}
            detail={`PostgreSQL: ${dashboard?.memory?.postgres?.detail || "unknown"} · Embeddings: ${dashboard?.memory?.local_embeddings?.online ? "online" : "unknown"}`}
            icon={<Database size={20} />}
            ok={postgresOnline && semanticOnline}
          />
          <StatusCard
            title="MartyBench"
            value={
              martybenchScore?.total != null
                ? `${martybenchScore.total}/${martybenchScore.max_total || 35}`
                : "No score"
            }
            detail={`${dashboard?.martybench?.variant || "unknown"} · ${martybenchScore?.verdict || "unknown"}`}
            icon={<Gauge size={20} />}
            ok={(martybenchScore?.total ?? 0) >= 28}
          />
        </div>

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
            <GlowRing listening={listening} processing={processing} />

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
                disabled={listening || processing}
                label={listening ? "Listening..." : processing ? "Working..." : "Listen"}
                icon={<Mic size={16} />}
              />
              <ControlButton
                label="Camera"
                icon={<Camera size={16} />}
                disabled
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
                    disabled={listening || processing}
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
                  disabled={processing || listening}
                  style={{
                    padding: "12px 16px",
                    borderRadius: 12,
                    border: "1px solid rgba(255,255,255,0.12)",
                    background: "white",
                    color: "#020617",
                    fontWeight: 700,
                    cursor: processing || listening ? "not-allowed" : "pointer",
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
                <div>MartyBench run: {dashboard?.martybench?.run_id || "unknown"}</div>
              </div>
            </div>
          </div>

          <ActivityLog logs={logs} />
        </div>
      </div>
    </div>
  );
}
