import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import {
  Clock3,
  Database,
  Cpu,
  Gauge,
  CheckCircle2,
  AlertTriangle,
  Usb,
  ScanEye,
  Network,
} from "lucide-react";
import { appConfig } from "./config/appConfig";
import StatusCard from "./components/StatusCard";
import { useApiHealth } from "./hooks/useApiHealth";
import { useCalibration } from "./hooks/useCalibration";
import { useDashboardStatus } from "./hooks/useDashboardStatus";
import { useMeasurement } from "./hooks/useMeasurement";
import HomePage from "./pages/HomePage";
import ArchitectureLabPage from "./pages/ArchitectureLabPage";
import MissionControlPage from "./pages/MissionControlPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import VisionLabPage from "./pages/VisionLabPage";
import {
  analyzeSnapshot,
  askJarvis,
  captureScanMat,
  captureSnapshot,
  checkLatestSnapshot as requestLatestSnapshot,
  getCameras,
  sendTextCommand,
  switchActiveCamera,
} from "./services/jarvisApi";
import type {
  AskResponse,
  CameraRolesStatus,
  ScanMatDiagnostics,
} from "./types/dashboard";

type AppPage = "home" | "mission" | "vision" | "maker" | "architecture" | "memory" | "system";
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
  diagnostics?: ScanMatDiagnostics;
  corners?: number[][];
  annotated_path?: string;
  rectified_path?: string;
  image_size?: {
    width?: number;
    height?: number;
  };
  image_name?: string;
  error?: string;
  capture?: CameraSnapshotResponse;
  mat_analysis?: {
    ok?: boolean;
    mat_detected?: boolean;
    image_name?: string;
    image_size?: {
      width?: number;
      height?: number;
    };
    diagnostics?: ScanMatDiagnostics;
    annotated_path?: string;
    rectified_path?: string;
    mat?: {
      corners?: number[][];
    };
  };
};

type NormalizedScanMatResponse = {
  matDetected: boolean;
  rawImageUrl?: string | null;
  annotatedImageUrl?: string | null;
  rectifiedImageUrl?: string | null;
  rectifiedImagePath?: string | null;
  rectifiedAvailable: boolean;
  warning?: string | null;
  diagnostics: ScanMatDiagnostics | null;
  corners: number[][] | null;
  imageSize?: {
    width?: number;
    height?: number;
  };
  imageName?: string;
  failureReason?: string | null;
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

function normalizeScanMatResponse(result: ScanMatResponse | null): NormalizedScanMatResponse | null {
  if (!result) return null;

  const diagnostics = result.diagnostics || result.mat_analysis?.diagnostics || null;
  const matDetected = result.mat_detected ?? result.mat_analysis?.mat_detected ?? false;
  const rectifiedImagePath = result.rectified_path || result.mat_analysis?.rectified_path || null;
  const rectifiedAvailable = result.rectified_available ?? Boolean(rectifiedImagePath || result.rectified_image_url);

  return {
    matDetected,
    rawImageUrl: result.raw_image_url,
    annotatedImageUrl: result.annotated_image_url,
    rectifiedImageUrl: result.rectified_image_url,
    rectifiedImagePath,
    rectifiedAvailable,
    warning: result.warning,
    diagnostics,
    corners: result.corners || result.mat_analysis?.mat?.corners || null,
    imageSize: result.image_size || result.mat_analysis?.image_size,
    imageName: result.image_name || result.mat_analysis?.image_name,
    failureReason: diagnostics?.failure_reason || null,
  };
}

export default function JarvisUI() {
  const apiBase = appConfig.apiBaseUrl;
  const [activePage, setActivePage] = useState<AppPage>("home");
  const [scanMode, setScanMode] = useState<ScanMode>("object");
  const [listening, setListening] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [scanningMat, setScanningMat] = useState(false);
  const [command, setCommand] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [snapshotVersion, setSnapshotVersion] = useState(0);
  const [snapshotAvailable, setSnapshotAvailable] = useState(false);
  const [scanMatResult, setScanMatResult] = useState<ScanMatResponse | null>(null);
  const [scanMatVersion, setScanMatVersion] = useState(0);
  const [cameraRoles, setCameraRoles] = useState<CameraRolesStatus | null>(null);
  const [switchingCameraRole, setSwitchingCameraRole] = useState(false);
  const microphoneLogRef = useRef("");
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
    }, appConfig.clockRefreshMs);

    return () => clearInterval(timer);
  }, []);

  const prependLogs = useCallback((entries: string[]) => {
    setLogs((prev) => [...entries, ...prev].slice(0, 80));
  }, []);

  const { dashboard, dashboardStatus, refreshDashboard } = useDashboardStatus(prependLogs);
  const { apiOnline, apiStatus, checkApi: checkApiHealth } = useApiHealth(
    refreshDashboard,
    prependLogs
  );
  const normalizedScanMat = normalizeScanMatResponse(scanMatResult);
  const {
    calibrationWidthMm,
    calibrationHeightMm,
    setCalibrationWidthMm,
    setCalibrationHeightMm,
    calibrating,
    calibrationMessage,
    applyLatestScanCalibration,
  } = useCalibration({
    getLatestScanCorners: () => normalizeScanMatResponse(scanMatResult)?.corners || null,
    getLatestScanImageSize: () => normalizeScanMatResponse(scanMatResult)?.imageSize,
    refreshDashboard,
    prependLogs,
    isScanMatBusy: () => scanningMat,
  });
  const {
    measuring,
    measurementResult,
    measurementMessage,
    measureLatestObject,
  } = useMeasurement({
    getLatestRectifiedImagePath: () => normalizeScanMatResponse(scanMatResult)?.rectifiedImagePath || null,
    canMeasureLatestObject: () => Boolean(dashboard?.calibration?.ready),
    refreshDashboard,
    prependLogs,
  });
  const apiDisplayStatus = apiOnline ? apiStatus : apiStatus;

  const busy = listening || processing || capturing || analyzing || scanningMat || calibrating || measuring || switchingCameraRole;

  useEffect(() => {
    const microphone = dashboard?.devices?.microphone;
    if (!microphone) return;

    const fallbackName = microphone.fallback_microphone?.name;
    const logEntry = microphone.using_preferred
      ? "Microphone: Samson Q2U selected"
      : fallbackName
        ? `Microphone fallback: ${fallbackName}`
        : "";

    if (!logEntry || microphoneLogRef.current === logEntry) return;
    microphoneLogRef.current = logEntry;
    prependLogs([logEntry]);
  }, [dashboard?.devices?.microphone, prependLogs]);

  const quickCommands = [
    "brain status",
    "semantic memory status",
    "show memory categories",
    "show cruise memories",
    "show project memories",
    "show work memories",
  ];

  const checkLatestSnapshot = useCallback(async () => {
    try {
      const res = await requestLatestSnapshot();
      setSnapshotAvailable(res.ok);
      if (res.ok) {
        setSnapshotVersion(Date.now());
      }
    } catch (error) {
      console.error(error);
      setSnapshotAvailable(false);
    }
  }, []);

  const refreshCameraRoles = useCallback(async () => {
    try {
      const res = await getCameras();
      const data: CameraRolesStatus = await res.json();
      if (res.ok && data.ok !== false) {
        setCameraRoles(data);
      }
    } catch (error) {
      console.error(error);
    }
  }, []);

  const runQuickCommand = async (quickCommand: string) => {
    if (busy) return;

    setProcessing(true);
    prependLogs([`You: ${quickCommand}`]);

    try {
      const res = await sendTextCommand(quickCommand, false);

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
    await checkApiHealth();
    checkLatestSnapshot();
    refreshCameraRoles();
  }, [checkApiHealth, checkLatestSnapshot, refreshCameraRoles]);

  useEffect(() => {
    const initialCheck = window.setTimeout(() => {
      checkApi();
    }, 0);
    return () => {
      window.clearTimeout(initialCheck);
    };
  }, [checkApi]);

  const runVoiceAsk = async () => {
    if (busy) return;

    setListening(true);
    prependLogs(["Listening requested from UI"]);

    try {
      const res = await askJarvis(voiceEnabled);

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
      const res = await captureSnapshot();

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

  const switchCameraRole = async (role: string) => {
    if (busy || switchingCameraRole) return;

    setSwitchingCameraRole(true);
    prependLogs([`Camera switch requested: ${role}`]);

    try {
      const res = await switchActiveCamera(role);
      const data: CameraRolesStatus = await res.json();

      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      setCameraRoles(data);
      const active = data.active_camera;
      prependLogs([
        `Camera switched to ${data.active_role || role}: ${active?.display_name || "camera"}`,
      ]);
      refreshDashboard(false);
    } catch (error) {
      console.error(error);
      const message = error instanceof Error ? error.message : "Camera unavailable";
      prependLogs([`Camera switch failed: ${message}`]);
    } finally {
      setSwitchingCameraRole(false);
    }
  };

  const analyzeLatestSnapshot = async (mode: ScanMode = "general") => {
    if (busy || !snapshotAvailable) return;

    const selectedMode = scanModes.find((item) => item.id === mode);
    setAnalyzing(true);
    prependLogs([`Vision analysis requested: ${selectedMode?.label || "General Scan"}`]);

    try {
      const res = await analyzeSnapshot(getScanPrompt(mode));

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
      const res = await captureScanMat();
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
        normalizeScanMatResponse(data)?.matDetected
          ? "Scan Mat: mat detected; artifacts ready"
          : `Scan Mat: ${normalizeScanMatResponse(data)?.warning || "mat was not detected"}`,
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
      const res = await sendTextCommand(trimmed, false);

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
  const latestScanCorners = normalizedScanMat?.corners || null;
  const latestScanDiagnostics = normalizedScanMat?.diagnostics || null;
  const latestRectifiedImagePath = normalizedScanMat?.rectifiedImagePath || null;

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
            color: normalizedScanMat?.matDetected ? "#22c55e" : "#f97316",
            fontSize: 13,
            fontWeight: 800,
          }}
        >
          {normalizedScanMat?.matDetected ? "Mat detected" : "Needs better view"}
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
          normalizedScanMat?.rawImageUrl,
          normalizedScanMat?.imageName || "Latest captured image"
        )}
        {scanArtifactCard(
          "Annotated Detection",
          normalizedScanMat?.annotatedImageUrl,
          normalizedScanMat?.matDetected
            ? "Detected mat boundary and corners."
            : "Diagnostic image from OpenCV mat detection."
        )}
        {scanArtifactCard(
          "Rectified View",
          normalizedScanMat?.rectifiedAvailable ? normalizedScanMat?.rectifiedImageUrl : null,
          normalizedScanMat?.rectifiedAvailable
            ? "Perspective-corrected top-down mat view."
            : undefined,
          normalizedScanMat?.warning || "Rectified view is unavailable until the mat is detected."
        )}
      </div>

      {normalizedScanMat?.corners && (
        <div style={{ marginTop: 10, opacity: 0.68, fontSize: 12 }}>
          Corners: {normalizedScanMat.corners.map((corner) => `[${corner.join(", ")}]`).join(" ")}
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

  const navItems: Array<{ id: AppPage; label: string; icon?: ReactNode }> = [
    { id: "home", label: "Home" },
    { id: "mission", label: "Mission Control" },
    { id: "vision", label: "Vision Lab" },
    { id: "maker", label: "Maker Lab" },
    { id: "architecture", label: "Architecture Lab", icon: <Network size={15} /> },
    { id: "memory", label: "Memory" },
    { id: "system", label: "System" },
  ];

  const missionControlPage = (
    <MissionControlPage
      dashboard={dashboard}
      martybenchScore={martybenchScore}
      refreshDashboard={refreshDashboard}
    />
  );

  const architectureLabPage = (
    <ArchitectureLabPage initialStatus={dashboard?.architecture} />
  );

  const homePage = (
    <HomePage
      runVoiceAsk={runVoiceAsk}
      captureCameraSnapshot={captureCameraSnapshot}
      analyzeLatestSnapshot={analyzeLatestSnapshot}
      checkApi={checkApi}
      refreshDashboard={refreshDashboard}
      runQuickCommand={runQuickCommand}
      sendTypedCommand={sendTypedCommand}
      setVoiceEnabled={setVoiceEnabled}
      setCommand={setCommand}
      listening={listening}
      processing={processing}
      capturing={capturing}
      analyzing={analyzing}
      busy={busy}
      cameraDetected={cameraDetected}
      snapshotAvailable={snapshotAvailable}
      snapshotPanel={snapshotPanel}
      quickCommands={quickCommands}
      command={command}
      voiceEnabled={voiceEnabled}
      dashboard={dashboard}
      logs={logs}
    />
  );

  const visionPage = (
    <VisionLabPage
      captureCameraSnapshot={captureCameraSnapshot}
      analyzeLatestSnapshot={analyzeLatestSnapshot}
      runScanMat={runScanMat}
      switchCameraRole={switchCameraRole}
      checkLatestSnapshot={checkLatestSnapshot}
      setScanMode={setScanMode}
      dashboard={dashboard}
      visionOnline={visionOnline}
      cameraDetected={cameraDetected}
      busy={busy}
      capturing={capturing}
      analyzing={analyzing}
      scanningMat={scanningMat}
      switchingCameraRole={switchingCameraRole}
      cameraRoles={cameraRoles || dashboard?.devices?.camera}
      scanMode={scanMode}
      scanModes={scanModes}
      selectedScanMode={selectedScanMode}
      snapshotAvailable={snapshotAvailable}
      snapshotPanel={snapshotPanel}
      scanMatPanel={scanMatPanel}
      scanMatDiagnostics={latestScanDiagnostics}
      latestScanCornersAvailable={Boolean(latestScanCorners)}
      calibrationWidthMm={calibrationWidthMm}
      calibrationHeightMm={calibrationHeightMm}
      setCalibrationWidthMm={setCalibrationWidthMm}
      setCalibrationHeightMm={setCalibrationHeightMm}
      calibrating={calibrating}
      calibrationMessage={calibrationMessage}
      applyLatestScanCalibration={applyLatestScanCalibration}
      calibrationStatus={dashboard?.calibration}
      measurementStatus={dashboard?.measurement}
      measuring={measuring}
      measurementResult={measurementResult}
      measurementMessage={measurementMessage}
      measureLatestObject={measureLatestObject}
      rectifiedImageAvailable={Boolean(latestRectifiedImagePath)}
      promptPreview={getScanPrompt(scanMode)}
      logs={logs}
    />
  );

  const currentPage = (() => {
    switch (activePage) {
      case "mission":
        return missionControlPage;
      case "vision":
        return visionPage;
      case "maker":
        return (
          <PlaceholderPage
            title="Maker Lab"
            description="Future home for OpenSCAD, 3D printing, laser engraving, jet ski parts, and workshop projects."
            items={[
              "OpenSCAD generation",
              "3D print inspection",
              "Laser engraving review",
              "Jet ski part reverse engineering",
            ]}
          />
        );
      case "architecture":
        return architectureLabPage;
      case "memory":
        return (
          <PlaceholderPage
            title="Memory"
            description="Future home for exact facts, semantic memory, project notes, and scanned-object history."
            items={[
              "Exact memory facts",
              "Semantic memory search",
              "Project memory categories",
              "Vision scan history",
            ]}
          />
        );
      case "system":
        return (
          <PlaceholderPage
            title="System"
            description="Future home for services, models, smoke tests, logs, and runtime controls."
            items={[
              "jarvis-status",
              "jarvis-smoke-test",
              "Model health",
              "Service logs",
            ]}
          />
        );
      default:
        return homePage;
    }
  })();

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
            <div>API: {apiDisplayStatus}</div>
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
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                }}
              >
                {item.icon}
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
