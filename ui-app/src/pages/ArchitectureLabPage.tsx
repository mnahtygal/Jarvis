import { useCallback, useEffect, useState, type CSSProperties } from "react";
import {
  ExternalLink,
  FolderTree,
  GitBranch,
  Network,
  RefreshCw,
  Workflow,
} from "lucide-react";
import ControlButton from "../components/ControlButton";
import StatusDot from "../components/StatusDot";
import {
  getArchitectureCallflowUrl,
  getArchitectureStatus,
  getArchitectureTreeUrl,
} from "../services/jarvisApi";
import type { ArchitectureStatus } from "../types/dashboard";

type ArchitectureView = "overview" | "tree" | "callflow" | "statistics";

type ArchitectureLabPageProps = {
  initialStatus?: ArchitectureStatus;
};

const views: Array<{ id: ArchitectureView; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "tree", label: "Project Tree" },
  { id: "callflow", label: "Call Flow" },
  { id: "statistics", label: "Statistics" },
];

const panelStyle: CSSProperties = {
  background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 20,
  padding: 20,
};

function formatGeneratedAt(generatedAt?: string | null) {
  if (!generatedAt) return "Never";
  const date = new Date(generatedAt);
  return Number.isNaN(date.getTime()) ? "Never" : date.toLocaleString();
}

function Metric({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok?: boolean;
}) {
  return (
    <div
      style={{
        padding: 14,
        borderRadius: 14,
        background: "rgba(0,0,0,0.22)",
        border: "1px solid rgba(255,255,255,0.06)",
        minWidth: 0,
      }}
    >
      <div style={{ opacity: 0.68, fontSize: 13 }}>{label}</div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginTop: 8,
          fontWeight: 800,
          overflowWrap: "anywhere",
        }}
      >
        <StatusDot ok={ok} />
        {value}
      </div>
    </div>
  );
}

function ArtifactView({
  title,
  description,
  available,
  url,
  onBack,
}: {
  title: string;
  description: string;
  available: boolean;
  url: string;
  onBack: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);

  if (!available) {
    return (
      <div style={panelStyle}>
        <h3 style={{ marginTop: 0 }}>{title} unavailable</h3>
        <p style={{ opacity: 0.76, lineHeight: 1.5 }}>
          This Graphify artifact has not been generated or cannot be read.
        </p>
        <ControlButton
          onClick={onBack}
          label="Return to Overview"
          icon={<GitBranch size={16} />}
        />
      </div>
    );
  }

  return (
    <div style={panelStyle}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 14,
          marginBottom: 14,
        }}
      >
        <div>
          <h3 style={{ margin: 0 }}>{title}</h3>
          <div style={{ opacity: 0.7, marginTop: 5, fontSize: 13 }}>{description}</div>
        </div>
        <ControlButton
          onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
          label="Open in New Tab"
          icon={<ExternalLink size={16} />}
        />
      </div>

      {loading && !loadFailed && (
        <div style={{ marginBottom: 10, opacity: 0.72 }}>Loading {title.toLowerCase()}…</div>
      )}
      {loadFailed && (
        <div
          style={{
            marginBottom: 10,
            padding: 12,
            borderRadius: 12,
            background: "rgba(239,68,68,0.12)",
            color: "#fca5a5",
          }}
        >
          The artifact could not be loaded. Refresh status or open it in a new tab.
        </div>
      )}
      <iframe
        src={url}
        title={`Jarvis Architecture ${title}`}
        onLoad={() => setLoading(false)}
        onError={() => {
          setLoading(false);
          setLoadFailed(true);
        }}
        style={{
          width: "100%",
          minHeight: 720,
          display: "block",
          border: "1px solid rgba(255,255,255,0.12)",
          borderRadius: 14,
          background: "white",
        }}
      />
    </div>
  );
}

export default function ArchitectureLabPage({
  initialStatus,
}: ArchitectureLabPageProps) {
  const [activeView, setActiveView] = useState<ArchitectureView>("overview");
  const [status, setStatus] = useState<ArchitectureStatus | undefined>(initialStatus);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState("");

  const refreshStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError("");
    try {
      const response = await getArchitectureStatus();
      if (!response.ok) {
        throw new Error(`Architecture status returned HTTP ${response.status}`);
      }
      const data: ArchitectureStatus = await response.json();
      setStatus(data);
    } catch (error) {
      console.error(error);
      setStatusError(
        error instanceof Error ? error.message : "Architecture status is unavailable."
      );
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => {
      void refreshStatus();
    }, 0);
    return () => window.clearTimeout(initialRefresh);
  }, [refreshStatus]);

  const treeUrl = getArchitectureTreeUrl();
  const callflowUrl = getArchitectureCallflowUrl();
  const nodes = status?.nodes ?? 0;
  const edges = status?.edges ?? 0;
  const edgeToNodeRatio = nodes > 0 ? (edges / nodes).toFixed(2) : "N/A";

  return (
    <div>
      <div
        style={{
          ...panelStyle,
          padding: 24,
          marginBottom: 20,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div>
          <h2 style={{ margin: 0, display: "flex", alignItems: "center", gap: 10 }}>
            <Network size={24} />
            Architecture Lab
          </h2>
          <div style={{ opacity: 0.74, marginTop: 6 }}>
            Explore Jarvis modules, dependencies, call flows, and generated architecture artifacts.
          </div>
        </div>
        <ControlButton
          onClick={() => void refreshStatus()}
          label={statusLoading ? "Refreshing…" : "Refresh Status"}
          icon={<RefreshCw size={16} />}
          disabled={statusLoading}
        />
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 10,
          marginBottom: 20,
        }}
      >
        {views.map((view) => {
          const active = activeView === view.id;
          return (
            <button
              key={view.id}
              onClick={() => setActiveView(view.id)}
              style={{
                padding: "9px 13px",
                borderRadius: 999,
                border: active
                  ? "1px solid rgba(34,211,238,0.75)"
                  : "1px solid rgba(255,255,255,0.10)",
                background: active
                  ? "rgba(34,211,238,0.16)"
                  : "rgba(255,255,255,0.05)",
                color: "white",
                cursor: "pointer",
                fontWeight: active ? 800 : 600,
              }}
            >
              {view.label}
            </button>
          );
        })}
      </div>

      {statusError && (
        <div
          style={{
            marginBottom: 20,
            padding: 14,
            borderRadius: 14,
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(239,68,68,0.24)",
            color: "#fca5a5",
          }}
        >
          {statusError}
        </div>
      )}

      {activeView === "overview" && (
        <div style={panelStyle}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 12,
            }}
          >
            <Metric label="Graph Status" value={status?.status || "Unknown"} ok={status?.ready} />
            <Metric label="Nodes" value={status?.nodes != null ? String(status.nodes) : "Unknown"} />
            <Metric label="Edges" value={status?.edges != null ? String(status.edges) : "Unknown"} />
            <Metric
              label="Last Generated"
              value={formatGeneratedAt(status?.generated_at)}
            />
            <Metric
              label="Project Tree"
              value={status?.tree_available ? "Available" : "Missing"}
              ok={status?.tree_available}
            />
            <Metric
              label="Call Flow"
              value={status?.callflow_available ? "Available" : "Missing"}
              ok={status?.callflow_available}
            />
          </div>

          <div
            style={{
              marginTop: 16,
              padding: 14,
              borderRadius: 14,
              background: "rgba(0,0,0,0.22)",
              border: "1px solid rgba(255,255,255,0.06)",
              lineHeight: 1.5,
            }}
          >
            <div><strong>Graph source:</strong> {status?.graph_path || "Unknown"}</div>
            <div style={{ marginTop: 6, opacity: 0.76 }}>
              {status?.detail || "Architecture status has not loaded yet."}
            </div>
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 16 }}>
            <ControlButton
              onClick={() => setActiveView("tree")}
              label="Open Project Tree"
              icon={<FolderTree size={16} />}
              disabled={!status?.tree_available}
            />
            <ControlButton
              onClick={() => setActiveView("callflow")}
              label="Open Call Flow"
              icon={<Workflow size={16} />}
              disabled={!status?.callflow_available}
            />
          </div>
        </div>
      )}

      {activeView === "tree" && (
        <ArtifactView
          title="Project Tree"
          description="Graphify-generated repository structure and module view."
          available={Boolean(status?.tree_available)}
          url={treeUrl}
          onBack={() => setActiveView("overview")}
        />
      )}

      {activeView === "callflow" && (
        <ArtifactView
          title="Call Flow"
          description="Interactive Graphify call-flow diagram."
          available={Boolean(status?.callflow_available)}
          url={callflowUrl}
          onBack={() => setActiveView("overview")}
        />
      )}

      {activeView === "statistics" && (
        <div style={panelStyle}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: 12,
            }}
          >
            <Metric label="Nodes" value={String(nodes)} />
            <Metric label="Edges" value={String(edges)} />
            <Metric label="Edge-to-node Ratio" value={edgeToNodeRatio} />
            <Metric label="Current Status" value={status?.status || "Unknown"} ok={status?.ready} />
            <Metric
              label="Tree Artifact"
              value={status?.tree_available ? "Available" : "Missing"}
              ok={status?.tree_available}
            />
            <Metric
              label="Call-flow Artifact"
              value={status?.callflow_available ? "Available" : "Missing"}
              ok={status?.callflow_available}
            />
            <Metric label="Last Generated" value={formatGeneratedAt(status?.generated_at)} />
            <Metric label="Graph Source" value={status?.graph_path || "Unknown"} />
          </div>
        </div>
      )}
    </div>
  );
}
