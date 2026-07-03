import { useCallback, useEffect, useMemo, useState } from "react";
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
  Usb,
  ScanEye,
} from "lucide-react";
import ActivityLog from "./components/ActivityLog";
import ControlButton from "./components/ControlButton";
import GlowRing from "./components/GlowRing";
import MissionSection from "./components/MissionSection";
import StatusCard from "./components/StatusCard";
import type { AskResponse, DashboardStatus } from "./types/dashboard";

type AppPage = "home" | "mission" | "vision" | "maker" | "memory" | "system";
type ScanMode = "general" | "object" | "measurement" | "ocr" | "print" | "jetski" | "workbench";

type CameraSnapshotResponse = {
  ok?: boolean;
  device?: string;
  elapsed_seconds?: number;
  relative_path?: string;
  size_bytes?: number;
  error?: string;
};

type VisionAnalysisResponse = {
  ok?: boolean;
  model?: string;
  description?: string;
  image_name?: string;
  error?: string;
};

type ScanMatResponse = {
  ok?: boolean;
  scan_ok?: boolean;
  mat_detected?: boolean;
  raw_image_url?: string;
  annotated_image_url?: string | null;
  rectified_image_url?: string | null;
  rectified_available?: boolean;
  warning?: string | null;
  corners?: number[][];
  image_name?: string;
  error?: string;
  capture?: CameraSnapshotResponse;
  mat_analysis?: {
    ok?: boolean;
    mat_detected?: boolean;
    image_name?: string;
    annotated_path?: string;
    rectified_path?: string;
    mat?: {
      corners?: number[][];
    };
  };
};

const scanModes: Array<{ id: ScanMode; label: string; detail: string }> = [
  {
    id: "general",
    label: "General Scan",
    detail: "Describe the scene and important visible details.",
  },
  {
    id: "object",
    label: "Object on Mat",
    detail: "Describe the main object on the measurement mat.",
  },
  {
    id: "measurement",
    label: "Measurement Helper",
    detail: "Estimate size and orientation using visible grid lines.",
  },
  {
    id: "ocr",
    label: "Read Text / Label",
    detail: "Focus on visible words, numbers, labels, and markings.",
  },
  {
    id: "print",
    label: "3D Print Inspect",
    detail: "Look for print quality issues and geometry problems.",
  },
  {
    id: "jetski",
    label: "Jet Ski Part Scan",
    detail: "Inspect marine parts, covers, plugs, fittings, and damage.",
  },
  {
    id: "workbench",
    label: "Workbench Status",
    detail: "Summarize what is on the bench and what looks important.",
  },
];

function getScanPrompt(mode: ScanMode) {
  const safety = "Do not identify people. If people appear, describe only non-identifying visible details.";

  if (mode === "object") {
    return `${safety} The image is from a fixed workbench scan mat. Describe the main object on the mat. Focus on shape, material, color, holes, edges, markings, orientation, and anything useful for repair, fabrication, or 3D modeling. Mention uncertainty.`;
  }

  if (mode === "measurement") {
    return `${safety} The image is from a fixed 18 by 24 inch measurement mat. Estimate the visible object's approximate length, width, orientation, and position using the grid only if the grid is readable. Be clear that estimates are approximate and mention when the grid is not clear enough.`;
  }

  if (mode === "ocr") {
    return `${safety} Read any visible text, labels, serial numbers, markings, symbols, or measurements. Preserve line breaks when useful. If text is unclear, say what is uncertain instead of guessing too strongly.`;
  }

  if (mode === "print") {
    return `${safety} Inspect the visible 3D printed part or prototype. Look for warping, layer shifts, stringing, elephant foot, missing walls, rough edges, poor bridging, holes, and dimensional clues from the mat. Give practical next-step advice.`;
  }

  if (mode === "jetski") {
    return `${safety} Inspect the visible jet ski or marine part. Describe shape, material, mounting points, plugs, covers, seals, cracks, corrosion, wear, markings, and likely orientation. Do not guess exact dimensions unless the grid is visible and readable.`;
  }

  if (mode === "workbench") {
    return `${safety} Summarize what is visible on the workbench. Identify tools, parts, documents, cables, and anything that looks important for the current project. Keep it practical and concise.`;
  }

  return `${safety} Briefly describe what you see in this image. Mention important objects, visible text, lighting, and anything useful for a workshop assistant. Mention uncertainty when needed.`;
}

export default function JarvisUI() {
  const apiBase = useMemo(() => "http://127.0.0.1:5000", []);
  const [activePage, setActivePage] = useState<AppPage>("home");
  const [scanMode, setScanMode] = useState<ScanMode>("object");
  const [listening, setListening] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [scanningMat, setScanningMat] = useState(false);
  const [command, setCommand] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [apiStatus, setApiStatus] = useState("Checking API...");
  const [dashboard, setDashboard] = useState<DashboardStatus | null>(null);
  const [dashboardStatus, setDashboardStatus] = useState("Checking dashboard...");
  const [snapshotVersion, setSnapshotVersion] = useState(0);
  const [snapshotAvailable, setSnapshotAvailable] = useState(false);
  const [scanMatResult, setScanMatResult] = useState<ScanMatResponse | null>(null);
  const [scanMatVersion, setScanMatVersion] = useState(0);
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

  const prependLogs = useCallback((entries: string[]) => {
    setLogs((prev) => [...entries, ...prev].slice(0, 80));
  }, []);

  const busy = listening || processing || capturing || analyzing || scanningMat;

  const quickCommands = [
    "brain status",
    "semantic memory status",
    "show memory categories",
    "show cruise memories",
    "show project memories",
    "show work memories",
  ];

  const refreshDashboard = useCallback(async (logResult = false) => {
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
  }, [apiBase, prependLogs]);

  const checkLatestSnapshot = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/api/camera/latest`, {
        method: "HEAD",
        cache: "no-store",
      });
      setSnapshotAvailable(res.ok);
      if (res.ok) {
        setSnapshotVersion(Date.now());
      }
    } catch (error) {
      console.error(error);
      setSnapshotAvailable(false);
    }
  }, [apiBase]);

  const runQuickCommand = async (quickCommand: string) => {
    if (busy) return;

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

  const checkApi = useCallback(async () => {
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
    checkLatestSnapshot();
  }, [apiBase, checkLatestSnapshot, prependLogs, refreshDashboard]);

  useEffect(() => {
    const initialCheck = window.setTimeout(() => {
      checkApi();
    }, 0);
    const dashboardTimer = setInterval(() => refreshDashboard(false), 30000);
    return () => {
      window.clearTimeout(initialCheck);
      clearInterval(dashboardTimer);
    };
  }, [checkApi, refreshDashboard]);

  const runVoiceAsk = async () => {
    if (busy) return;

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

  const captureCameraSnapshot = async () => {
    if (busy) return;

    setCapturing(true);
    prependLogs(["Camera snapshot requested"]);

    try {
      const res = await fetch(`${apiBase}/api/camera/snapshot`, {
        method: "POST",
      });

      const data: CameraSnapshotResponse = await res.json();

      if (!res.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      prependLogs([
        `Camera snapshot saved: ${data.relative_path || "runtime/camera"}`,
        `Camera: ${data.device || "/dev/video0"} · ${data.size_bytes ?? 0} bytes · ${data.elapsed_seconds ?? "?"}s`,
      ]);
      setSnapshotAvailable(true);
      setSnapshotVersion(Date.now());
      refreshDashboard(false);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unknown camera error";
      prependLogs([`Camera snapshot failed: ${message}`]);
    } finally {
      setCapturing(false);
    }
  };

  const analyzeLatestSnapshot = async (mode: ScanMode = "general") => {
    if (busy || !snapshotAvailable) return;

    const selectedMode = scanModes.find((item) => item.id === mode);
    setAnalyzing(true);
    prependLogs([`Vision analysis requested: ${selectedMode?.label || "General Scan"}`]);

    try {
      const res = await fetch(`${apiBase}/api/camera/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt: getScanPrompt(mode),
        }),
      });

      const data: VisionAnalysisResponse = await res.json();

      if (!res.ok || !data.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      prependLogs([
        `Vision (${selectedMode?.label || "General Scan"} / ${data.model || "local model"}): ${data.description || "No description returned."}`,
        `Analyzed snapshot: ${data.image_name || "latest"}`,
      ]);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unknown vision error";
      prependLogs([`Vision analysis failed: ${message}`]);
    } finally {
      setAnalyzing(false);
    }
  };

  const runScanMat = async () => {
    if (busy || !cameraDetected) return;

    setScanningMat(true);
    prependLogs(["Scan Mat requested"]);

    try {
      const res = await fetch(`${apiBase}/api/vision/capture-scan-mat`, {
        method: "POST",
      });
      const data: ScanMatResponse = await res.json();

      if (!res.ok && res.status !== 422) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      setScanMatResult(data);
      setScanMatVersion(Date.now());

      if (data.raw_image_url) {
        setSnapshotAvailable(true);
        setSnapshotVersion(Date.now());
      }

      prependLogs([
        data.mat_detected
          ? "Scan Mat: mat detected; artifacts ready"
          : `Scan Mat: ${data.warning || "mat was not detected"}`,
      ]);
      refreshDashboard(false);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Unknown scan-mat error";
      prependLogs([`Scan Mat failed: ${message}`]);
    } finally {
      setScanningMat(false);
    }
  };

  const sendTypedCommand = async () => {
    const trimmed = command.trim();
    if (!trimmed || busy) return;

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
  const visionOnline = dashboard?.vision?.online ?? false;
  const postgresOnline = dashboard?.memory?.postgres?.online ?? false;
  const semanticOnline = dashboard?.memory?.semantic_memory?.online ?? false;
  const devicesReady = dashboard?.devices?.ready ?? false;
  const cameraDetected = dashboard?.devices?.camera?.detected ?? false;
  const martybenchScore = dashboard?.martybench?.score;
  const selectedScanMode = scanModes.find((item) => item.id === scanMode) || scanModes[0];

  const snapshotPanel = (
    <div style={{ marginTop: 24 }}>
      <div style={{ marginBottom: 10, opacity: 0.85 }}>Latest snapshot</div>
      {snapshotAvailable ? (
        <img
          src={`${apiBase}/api/camera/latest?v=${snapshotVersion}`}
          alt="Latest Jarvis camera snapshot"
          style={{
            width: "100%",
            maxHeight: 460,
            objectFit: "cover",
            borderRadius: 16,
            border: "1px solid rgba(255,255,255,0.12)",
            background: "rgba(0,0,0,0.22)",
          }}
          onError={() => setSnapshotAvailable(false)}
        />
      ) : (
        <div
          style={{
            minHeight: 260,
            borderRadius: 16,
            border: "1px dashed rgba(255,255,255,0.18)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: 0.72,
          }}
        >
          No snapshot yet. Capture one from Camera.
        </div>
      )}
    </div>
  );

  const artifactImageSrc = (url?: string | null) =>
    url ? `${url}${url.includes("?") ? "&" : "?"}v=${scanMatVersion}` : "";

  const scanArtifactCard = (
    title: string,
    imageUrl?: string | null,
    detail?: string,
    warning?: string | null
  ) => (
    <div
      style={{
        background: "rgba(0,0,0,0.22)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 14,
        padding: 14,
        minWidth: 0,
      }}
    >
      <div style={{ fontWeight: 800, marginBottom: 8 }}>{title}</div>
      {imageUrl ? (
        <img
          src={artifactImageSrc(imageUrl)}
          alt={title}
          style={{
            width: "100%",
            aspectRatio: "4 / 3",
            objectFit: "cover",
            borderRadius: 10,
            border: "1px solid rgba(255,255,255,0.08)",
            background: "rgba(0,0,0,0.24)",
          }}
        />
      ) : (
        <div
          style={{
            aspectRatio: "4 / 3",
            borderRadius: 10,
            border: "1px dashed rgba(255,255,255,0.18)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
            textAlign: "center",
            color: "rgba(255,255,255,0.72)",
            background: "rgba(0,0,0,0.16)",
          }}
        >
          {warning || "Artifact unavailable for this scan."}
        </div>
      )}
      {detail && (
        <div style={{ marginTop: 8, opacity: 0.72, fontSize: 12, lineHeight: 1.35 }}>
          {detail}
        </div>
      )}
    </div>
  );

  const scanMatPanel = scanMatResult && (
    <div style={{ marginTop: 22 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 10 }}>
        <div style={{ opacity: 0.85 }}>Scan Mat artifacts</div>
        <div
          style={{
            color: scanMatResult.mat_detected ? "#22c55e" : "#f97316",
            fontSize: 13,
            fontWeight: 800,
          }}
        >
          {scanMatResult.mat_detected ? "Mat detected" : "Needs better view"}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 12,
        }}
      >
        {scanArtifactCard(
          "Raw Capture",
          scanMatResult.raw_image_url,
          scanMatResult.image_name || scanMatResult.mat_analysis?.image_name || "Latest captured image"
        )}
        {scanArtifactCard(
          "Annotated Detection",
          scanMatResult.annotated_image_url,
          scanMatResult.mat_detected
            ? "Detected mat boundary and corners."
            : "Diagnostic image from OpenCV mat detection."
        )}
        {scanArtifactCard(
          "Rectified View",
          scanMatResult.rectified_available ? scanMatResult.rectified_image_url : null,
          scanMatResult.rectified_available
            ? "Perspective-corrected top-down mat view."
            : undefined,
          scanMatResult.warning || "Rectified view is unavailable until the mat is detected."
        )}
      </div>

      {scanMatResult.corners && (
        <div style={{ marginTop: 10, opacity: 0.68, fontSize: 12 }}>
          Corners: {scanMatResult.corners.map((corner) => `[${corner.join(", ")}]`).join(" ")}
        </div>
      )}
    </div>
  );

  const topCards = (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(6, minmax(0, 1fr))",
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
        title="Vision"
        value={dashboard?.vision?.overall || "Unknown"}
        detail={`${dashboard?.vision?.active_model_name || "Gemma Vision"} · port ${dashboard?.vision?.port || 8081}`}
        icon={<ScanEye size={20} />}
        ok={visionOnline}
      />
      <StatusCard
        title="Memory"
        value={`${dashboard?.memory?.exact_memory?.fact_count ?? "?"} facts / ${dashboard?.brain?.semantic_memory || "semantic ?"}`}
        detail={`PostgreSQL: ${dashboard?.memory?.postgres?.detail || "unknown"} · Embeddings: ${dashboard?.memory?.local_embeddings?.online ? "online" : "unknown"}`}
        icon={<Database size={20} />}
        ok={postgresOnline && semanticOnline}
      />
      <StatusCard
        title="Devices"
        value={dashboard?.devices?.overall || "Unknown"}
        detail={`Mic: ${dashboard?.devices?.microphone?.detected ? dashboard?.devices?.microphone?.name || "detected" : "missing"} · Camera: ${dashboard?.devices?.camera?.detected ? dashboard?.devices?.camera?.name || dashboard?.devices?.camera?.expected_device || "detected" : "missing"} · ${dashboard?.devices?.audio_backend || "audio ?"}`}
        icon={<Usb size={20} />}
        ok={devicesReady}
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
  );

  const navItems: Array<{ id: AppPage; label: string }> = [
    { id: "home", label: "Home" },
    { id: "mission", label: "Mission Control" },
    { id: "vision", label: "Vision Lab" },
    { id: "maker", label: "Maker Lab" },
    { id: "memory", label: "Memory" },
    { id: "system", label: "System" },
  ];

  const placeholderPage = (title: string, description: string, items: string[]) => (
    <div
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 20,
        padding: 24,
      }}
    >
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <p style={{ opacity: 0.78, lineHeight: 1.5 }}>{description}</p>
      <div style={{ display: "grid", gap: 10, marginTop: 20 }}>
        {items.map((item) => (
          <div
            key={item}
            style={{
              padding: 12,
              borderRadius: 12,
              background: "rgba(0,0,0,0.22)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );

  const missionControlPage = (
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

  const homePage = (
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

  const visionPage = (
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
            {getScanPrompt(scanMode)}
          </div>
        </div>
      </div>

      <ActivityLog logs={logs} />
    </div>
  );

  const currentPage =
    activePage === "vision"
      ? visionPage
      : activePage === "mission"
        ? missionControlPage
      : activePage === "maker"
        ? placeholderPage("Maker Lab", "Future home for OpenSCAD, 3D printing, laser engraving, jet ski parts, and workshop projects.", [
            "OpenSCAD generation",
            "3D print inspection",
            "Laser engraving review",
            "Jet ski part reverse engineering",
          ])
        : activePage === "memory"
          ? placeholderPage("Memory", "Future home for exact facts, semantic memory, project notes, and scanned-object history.", [
              "Exact memory facts",
              "Semantic memory search",
              "Project memory categories",
              "Vision scan history",
            ])
          : activePage === "system"
            ? placeholderPage("System", "Future home for services, models, smoke tests, logs, and runtime controls.", [
                "jarvis-status",
                "jarvis-smoke-test",
                "Model health",
                "Service logs",
              ])
            : homePage;

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
          maxWidth: 1280,
          margin: "0 auto",
        }}
      >
        <div style={{ marginBottom: 18 }}>
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
            display: "flex",
            flexWrap: "wrap",
            gap: 10,
            marginBottom: 20,
          }}
        >
          {navItems.map((item) => {
            const active = item.id === activePage;
            return (
              <button
                key={item.id}
                onClick={() => setActivePage(item.id)}
                style={{
                  padding: "10px 14px",
                  borderRadius: 999,
                  border: active ? "1px solid rgba(34,211,238,0.75)" : "1px solid rgba(255,255,255,0.10)",
                  background: active ? "rgba(34,211,238,0.16)" : "rgba(255,255,255,0.05)",
                  color: "white",
                  cursor: "pointer",
                  fontWeight: active ? 800 : 600,
                }}
              >
                {item.label}
              </button>
            );
          })}
        </div>

        {topCards}
        {currentPage}
      </div>
    </div>
  );
}
