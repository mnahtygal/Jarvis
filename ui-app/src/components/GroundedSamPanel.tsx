import { RefreshCw, ScanEye } from "lucide-react";
import ControlButton from "./ControlButton";
import type { GroundedSamState } from "../hooks/useGroundedSam";
import type { GroundedSamMeasuredEnvelope } from "../types/groundedSam";

const panelStyle = {
  marginTop: 22,
  padding: 16,
  borderRadius: 14,
  background: "rgba(8,47,73,0.22)",
  border: "1px solid rgba(34,211,238,0.22)",
} as const;

const insetStyle = {
  padding: 12,
  borderRadius: 10,
  border: "1px solid rgba(255,255,255,0.08)",
  background: "rgba(0,0,0,0.22)",
} as const;

function formatPercent(value?: number | null) {
  return value == null ? "unknown" : `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value?: number | null, digits = 2) {
  return value == null ? "unknown" : value.toFixed(digits);
}

function formatBox(box?: [number, number, number, number] | null) {
  return box ? box.map((value) => value.toFixed(1)).join(", ") : "none";
}

function EnvelopeDetails({ title, envelope }: {
  title: string;
  envelope?: GroundedSamMeasuredEnvelope;
}) {
  return (
    <div style={insetStyle}>
      <div style={{ fontWeight: 800 }}>{title}</div>
      <div style={{ marginTop: 8, display: "grid", gap: 5, opacity: 0.8 }}>
        <div>Long side: {formatNumber(envelope?.long_side_mm)} mm</div>
        <div>Short side: {formatNumber(envelope?.short_side_mm)} mm</div>
        <div>Angle: {formatNumber(envelope?.angle_degrees)}°</div>
        {envelope?.trim_percentile != null && (
          <div>Trim percentile: {formatNumber(envelope.trim_percentile, 1)}%</div>
        )}
      </div>
    </div>
  );
}

function ArtifactCard({ title, url }: { title: string; url?: string }) {
  return (
    <div style={insetStyle}>
      <div style={{ fontWeight: 800, marginBottom: 8 }}>{title}</div>
      {url ? (
        <img
          src={url}
          alt={`Grounded SAM ${title.toLowerCase()}`}
          style={{
            display: "block",
            width: "100%",
            aspectRatio: "4 / 3",
            objectFit: "contain",
            borderRadius: 8,
            background: "rgba(0,0,0,0.3)",
          }}
        />
      ) : (
        <div style={{ minHeight: 110, display: "grid", placeItems: "center", opacity: 0.6 }}>
          Artifact unavailable
        </div>
      )}
    </div>
  );
}

export default function GroundedSamPanel({ state }: { state: GroundedSamState }) {
  const {
    phase,
    health,
    images,
    selectedImageId,
    selectedImage,
    prompt,
    result,
    inventoryLoading,
    errorMessage,
    analysisDisabledReason,
    setSelectedImageId,
    setPrompt,
    refreshInventory,
    submitAnalysis,
  } = state;
  const detector = result?.detector;
  const segmenter = result?.segmenter;
  const measurement = result?.measurement;
  const calibration = result?.calibration;
  const timings = Object.entries(result?.stage_timings_ms || {});
  const responseWarnings = result?.warnings || [];
  const hasElevationWarning = responseWarnings.some((warning) =>
    warning.toLowerCase().includes("elevated objects")
  );
  const warnings = result
    ? hasElevationWarning
      ? responseWarnings
      : [...responseWarnings, "Elevated objects are not precision mat-plane measurements."]
    : [];
  const workerLabel = !health
    ? "Status unavailable"
    : !health.enabled
      ? "Disabled"
      : !health.worker_reachable
        ? "Worker unavailable"
        : health.busy
          ? "Busy"
          : health.model_state === "loading"
            ? "Loading models"
            : health.model_state === "load_failed"
              ? "Model load failed"
            : health.model_state;

  return (
    <section style={panelStyle} aria-label="Experimental Grounded SAM saved-image analysis">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <div style={{ fontSize: 18, fontWeight: 900 }}>Grounded SAM saved-image analysis</div>
            <span
              style={{
                padding: "5px 9px",
                borderRadius: 999,
                background: "rgba(251,191,36,0.16)",
                border: "1px solid rgba(251,191,36,0.42)",
                color: "#fde68a",
                fontSize: 11,
                fontWeight: 900,
                letterSpacing: 0.5,
                textTransform: "uppercase",
              }}
            >
              Experimental
            </span>
          </div>
          <div style={{ marginTop: 7, opacity: 0.74, fontSize: 13, lineHeight: 1.45 }}>
            Prompt-driven analysis of a previously saved, server-validated C920 rectified image.
            This panel never captures a camera image and never falls back to OpenCV.
          </div>
        </div>
        <div style={{ color: health?.enabled && health.worker_reachable ? "#22c55e" : "#f97316", fontWeight: 800, fontSize: 13 }}>
          {workerLabel}
        </div>
      </div>

      <div style={{ marginTop: 16, display: "grid", gap: 12 }}>
        <label style={{ display: "grid", gap: 6, fontSize: 13 }}>
          Validated saved image
          <select
            value={selectedImageId}
            onChange={(event) => setSelectedImageId(event.target.value)}
            disabled={inventoryLoading || phase === "analyzing" || images.length === 0}
            style={{
              width: "100%",
              padding: 11,
              borderRadius: 10,
              border: "1px solid rgba(255,255,255,0.12)",
              background: "#111827",
              color: "white",
            }}
          >
            {images.length === 0 && <option value="">No validated saved images</option>}
            {images.map((image) => (
              <option key={image.image_id} value={image.image_id}>
                {image.display_name}
              </option>
            ))}
          </select>
        </label>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <ControlButton
            onClick={() => void refreshInventory()}
            label={inventoryLoading ? "Refreshing..." : "Refresh Images"}
            icon={<RefreshCw size={16} />}
            disabled={inventoryLoading || phase === "analyzing"}
          />
          <div style={{ opacity: 0.68, fontSize: 12 }}>
            {images.length} validated C920 image{images.length === 1 ? "" : "s"}, newest first
          </div>
        </div>

        {selectedImage && (
          <div style={{ ...insetStyle, display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 7, fontSize: 12 }}>
            <div>Capture time: {selectedImage.captured_at}</div>
            <div>Dimensions: {selectedImage.width} × {selectedImage.height}</div>
            <div>Camera: {selectedImage.logical_camera_id} / {selectedImage.camera_role}</div>
            <div>Profile: {selectedImage.calibration_profile_id}</div>
            <div>Calibration confidence: {formatPercent(selectedImage.calibration_confidence)}</div>
            <div>Provenance: {selectedImage.provenance_state}</div>
          </div>
        )}

        <label style={{ display: "grid", gap: 6, fontSize: 13 }}>
          Object prompt
          <input
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            maxLength={256}
            placeholder="small metal gear"
            disabled={phase === "analyzing"}
            style={{
              width: "100%",
              boxSizing: "border-box",
              padding: 11,
              borderRadius: 10,
              border: "1px solid rgba(255,255,255,0.12)",
              background: "rgba(0,0,0,0.34)",
              color: "white",
            }}
          />
        </label>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <ControlButton
            onClick={() => void submitAnalysis()}
            label={phase === "analyzing" ? "Analyzing saved image..." : "Analyze with Grounded SAM"}
            icon={<ScanEye size={16} />}
            disabled={analysisDisabledReason !== null}
          />
          {analysisDisabledReason && phase !== "analyzing" && (
            <div style={{ color: "#fbbf24", fontSize: 12 }}>{analysisDisabledReason}</div>
          )}
        </div>
      </div>

      {(phase === "loading" || phase === "analyzing") && (
        <div style={{ marginTop: 14, color: "#67e8f9", fontSize: 13 }}>
          {phase === "analyzing"
            ? "Grounding DINO and SAM2 analysis is running on the saved image."
            : "Loading saved-image inventory and worker status..."}
        </div>
      )}

      {errorMessage && (
        <div role="alert" style={{ marginTop: 14, ...insetStyle, color: "#fdba74", lineHeight: 1.45 }}>
          <strong>{result?.failure_reason || "Grounded SAM unavailable"}</strong>
          <div style={{ marginTop: 5 }}>{errorMessage}</div>
          {result?.status && <div style={{ marginTop: 5, opacity: 0.72 }}>Status: {result.status}</div>}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 18, display: "grid", gap: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <strong>Grounded SAM result</strong>
            <span style={{ color: result.ok ? "#22c55e" : "#f97316", fontWeight: 800 }}>
              {result.status}
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10 }}>
            <ArtifactCard title="Diagnostic overlay" url={result.artifacts.diagnostic_overlay_url} />
            <ArtifactCard title="Raw mask" url={result.artifacts.raw_mask_url} />
            <ArtifactCard title="Cleaned mask" url={result.artifacts.cleaned_mask_url} />
          </div>

          <div style={{ ...insetStyle, fontSize: 13 }}>
            <div style={{ fontWeight: 800 }}>Selected detector candidate</div>
            <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 7, opacity: 0.82 }}>
              <div>Label: {detector?.selected_label || "none"}</div>
              <div>Confidence: {formatPercent(detector?.selected_confidence)}</div>
              <div>Box: {formatBox(detector?.selected_box)}</div>
              <div>SAM2 mask score: {formatPercent(segmenter?.selected_mask_score)}</div>
              <div>Mask area: {segmenter?.mask_area_pixels ?? "unknown"} px</div>
              <div>Device / dtype: {result.device || "unknown"} / {result.dtype || "unknown"}</div>
            </div>
          </div>

          {detector?.candidates?.length ? (
            <details style={insetStyle}>
              <summary style={{ cursor: "pointer", fontWeight: 800 }}>
                Detector candidates ({detector.candidates.length})
              </summary>
              <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
                {detector.candidates.map((candidate, index) => (
                  <div key={`${candidate.label}-${index}`} style={{ paddingTop: 8, borderTop: "1px solid rgba(255,255,255,0.07)", fontSize: 12 }}>
                    <strong>{candidate.label || `Candidate ${index + 1}`}</strong>
                    <div style={{ marginTop: 4, opacity: 0.78 }}>
                      {formatPercent(candidate.confidence)} · box {formatBox(candidate.box)} · area {formatPercent(candidate.area_ratio)} · {candidate.accepted ? "accepted" : "rejected"}
                    </div>
                    {!candidate.accepted && (
                      <div style={{ marginTop: 3, color: "#fdba74" }}>
                        {candidate.rejection_reasons.join(", ") || "No rejection reason supplied"}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </details>
          ) : null}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10, fontSize: 13 }}>
            <EnvelopeDetails title="Maximum occupied envelope" envelope={measurement?.maximum_occupied_envelope} />
            <EnvelopeDetails title="Robust body" envelope={measurement?.robust_body} />
          </div>

          <div style={{ ...insetStyle, display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 7, fontSize: 12 }}>
            <div>Mask area: {formatNumber(measurement?.area_mm2)} mm²</div>
            <div>Measurement unit: {measurement?.unit || "unknown"}</div>
            <div>Calibration profile: {calibration?.profile_id || "unknown"}</div>
            <div>Calibration confidence: {formatPercent(calibration?.confidence)}</div>
            <div>Model load: {formatNumber(result.model_load_timing_ms?.total)} ms</div>
            <div>Total duration: {formatNumber(result.stage_timings_ms.total)} ms</div>
          </div>

          {timings.length > 0 && (
            <details style={insetStyle}>
              <summary style={{ cursor: "pointer", fontWeight: 800 }}>Stage timings</summary>
              <div style={{ marginTop: 9, display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 6, fontSize: 12 }}>
                {timings.map(([stage, duration]) => (
                  <div key={stage}>{stage}: {formatNumber(duration)} ms</div>
                ))}
              </div>
            </details>
          )}

          {Object.keys(result.diagnostics || {}).length > 0 && (
            <details style={insetStyle}>
              <summary style={{ cursor: "pointer", fontWeight: 800 }}>Structured diagnostics</summary>
              <pre style={{ margin: "10px 0 0", whiteSpace: "pre-wrap", overflowWrap: "anywhere", fontSize: 11, opacity: 0.78 }}>
                {JSON.stringify(result.diagnostics, null, 2)}
              </pre>
            </details>
          )}

          <div style={{ color: "#fbbf24", fontSize: 12, lineHeight: 1.5 }}>
            {warnings.map((warning) => <div key={warning}>{warning}</div>)}
          </div>
        </div>
      )}
    </section>
  );
}
