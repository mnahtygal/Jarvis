export type GroundedSamFailureReason =
  | "invalid_backend"
  | "backend_disabled"
  | "invalid_prompt"
  | "source_image_missing"
  | "source_image_unreadable"
  | "dependency_missing"
  | "worker_unavailable"
  | "worker_busy"
  | "model_unavailable"
  | "model_load_failed"
  | "request_timeout"
  | "no_detector_candidate"
  | "ambiguous_detector_candidates"
  | "invalid_segmentation_mask"
  | "calibration_invalid"
  | "calibration_provenance_mismatch"
  | "artifact_write_failed"
  | "internal_error";

export type GroundedSamHealth = {
  backend: "grounded_sam";
  backend_version: string;
  experimental: true;
  enabled: boolean;
  worker_reachable: boolean;
  dependencies_available: boolean | null;
  model_state: "unloaded" | "loading" | "ready" | "load_failed" | "unavailable" | string;
  last_load_error: string | null;
  last_load_failure_reason?: GroundedSamFailureReason | null;
  busy: boolean;
  load_attempts?: number;
  last_load_ms?: number | null;
  models_loaded?: boolean;
  device?: string | null;
  dtype?: string | null;
  dependency_versions?: Record<string, string | null>;
  reported_dependencies?: Record<string, string | null>;
};

export type GroundedSamSavedImage = {
  image_id: string;
  display_name: string;
  captured_at: string;
  timestamp_source: "provenance_created_at" | "filesystem_mtime";
  width: number;
  height: number;
  logical_camera_id: "logitech_c920";
  camera_role: "workbench";
  calibration_profile_id: "logitech_c920_overhead_scan_mat";
  calibration_confidence: number | null;
  geometry_version: string;
  homography_version: string;
  provenance_state: "validated";
};

export type GroundedSamInventoryResponse = {
  ok: true;
  backend: "grounded_sam";
  experimental: true;
  count: number;
  images: GroundedSamSavedImage[];
};

export type GroundedSamDetectorCandidate = {
  box: [number, number, number, number];
  confidence: number;
  label: string;
  prompt: string;
  area_ratio: number;
  touches_boundary: boolean;
  accepted: boolean;
  rejection_reasons: string[];
};

export type GroundedSamDetector = {
  model: string;
  box_threshold: number;
  text_threshold: number;
  candidates: GroundedSamDetectorCandidate[];
  selected_box: [number, number, number, number] | null;
  selected_label: string | null;
  selected_confidence: number | null;
};

export type GroundedSamSegmenter = {
  model: string;
  selected_mask_score: number | null;
  selected_mask_index: number | null;
  mask_area_pixels: number | null;
  cleanup?: {
    raw_area_pixels?: number;
    cleaned_area_pixels?: number;
    removed_pixels?: number;
    kernel_size?: number;
    component_decisions?: Array<Record<string, unknown>>;
  };
};

export type GroundedSamMeasuredEnvelope = {
  long_side_mm?: number;
  short_side_mm?: number;
  angle_degrees?: number;
  box_px?: number[][];
  trim_percentile?: number;
};

export type GroundedSamMeasurement = {
  unit?: string;
  method?: string;
  maximum_occupied_envelope?: GroundedSamMeasuredEnvelope;
  robust_body?: GroundedSamMeasuredEnvelope;
  area_mm2?: number;
};

export type GroundedSamCalibration = {
  ready?: boolean;
  profile_id?: string | null;
  logical_camera_id?: string | null;
  camera_role?: string | null;
  pixels_per_mm_x?: number | null;
  pixels_per_mm_y?: number | null;
  mm_per_pixel_x?: number | null;
  mm_per_pixel_y?: number | null;
  confidence?: number | null;
  geometry_version?: string | null;
  homography_version?: string | null;
};

export type GroundedSamArtifacts = {
  raw_mask_url?: string;
  cleaned_mask_url?: string;
  diagnostic_overlay_url?: string;
};

export type GroundedSamSourceImage = {
  image_id?: string;
  sha256?: string;
  width?: number;
  height?: number;
  calibration_profile_id?: string | null;
  logical_camera_id?: string | null;
  camera_role?: string | null;
  geometry_version?: string | null;
  homography_version?: string | null;
};

export type GroundedSamModelLoadTiming = {
  total?: number | null;
  cache_hit?: boolean;
  attempt?: number;
};

export type GroundedSamAnalysisResult = {
  ok: boolean;
  backend: "grounded_sam";
  backend_version: string;
  experimental: true;
  status: string;
  failure_reason: GroundedSamFailureReason | null;
  error: string | null;
  source_image: GroundedSamSourceImage | null;
  prompt: string | null;
  detector: GroundedSamDetector | null;
  segmenter: GroundedSamSegmenter | null;
  measurement: GroundedSamMeasurement | null;
  calibration: GroundedSamCalibration | null;
  artifacts: GroundedSamArtifacts;
  model_load_timing_ms: GroundedSamModelLoadTiming | null;
  stage_timings_ms: Record<string, number>;
  device: string | null;
  dtype: string | null;
  dependency_versions: Record<string, string | null>;
  warnings: string[];
  diagnostics: Record<string, unknown>;
};

export type GroundedSamAnalysisResponse = {
  httpStatus: number;
  result: GroundedSamAnalysisResult;
};
