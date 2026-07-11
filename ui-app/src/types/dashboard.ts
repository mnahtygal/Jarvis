export type AskResponse = {
  heard: string;
  response: string;
};

export type DeviceStatus = {
  overall?: string;
  ready?: boolean;
  audio_backend?: string;
  dock_note?: string;
  microphone?: {
    name?: string;
    detected?: boolean;
    preferred_microphone?: string;
    resolved_microphone?: string | null;
    available?: boolean;
    using_preferred?: boolean;
    fallback_microphone?: AudioSource | null;
    usb_lines?: string[];
    audio_source_lines?: string[];
    wpctl_lines?: string[];
    test_command?: string;
  };
  camera?: {
    name?: string;
    detected?: boolean;
    expected_device?: string;
    expected_device_present?: boolean;
    active_role?: string;
    active_camera?: CameraRole;
    cameras?: CameraRole[];
    video_devices?: string[];
    usb_lines?: string[];
    test_command?: string;
  };
};

export type AudioSource = {
  id?: string;
  name?: string;
  driver?: string | null;
  description?: string;
};

export type CameraRole = {
  id?: string;
  display_name?: string;
  detected_v4l2_name?: string;
  role?: string;
  resolved_device_path?: string | null;
  enabled?: boolean;
  available?: boolean;
  preferred_resolution?: {
    width?: number;
    height?: number;
  };
  preferred_pixel_format?: string;
  matched_device?: {
    path?: string;
    name?: string | null;
    bus_info?: string | null;
  } | null;
};

export type CameraRolesStatus = {
  ok?: boolean;
  default_role?: string;
  active_role?: string;
  active_camera?: CameraRole | null;
  cameras?: CameraRole[];
  devices?: Array<{
    path?: string;
    name?: string | null;
    bus_info?: string | null;
  }>;
  error?: string;
};

export type CameraControlStatus = {
  present?: boolean;
  value?: number | null;
  min?: number | null;
  max?: number | null;
  step?: number | null;
};

export type CameraDiagnosticsStatus = {
  overall?: string;
  ready?: boolean;
  active_role?: string;
  default_role?: string;
  active_camera?: CameraRole;
  cameras?: CameraRole[];
  capture_device?: {
    path?: string;
    present?: boolean;
    role?: string;
    driver?: string | null;
    card?: string | null;
    bus_info?: string | null;
    format?: {
      width?: number | null;
      height?: number | null;
      pixel_format?: string | null;
      fps?: string | null;
    };
  };
  metadata_device?: {
    path?: string;
    present?: boolean;
    role?: string;
  };
  controls?: {
    pan_absolute?: CameraControlStatus;
    tilt_absolute?: CameraControlStatus;
    zoom_absolute?: CameraControlStatus;
  };
  gimbal?: {
    standard_controls_present?: boolean;
    standard_controls_move_physical_gimbal?: boolean;
    status?: string;
    note?: string;
  };
  extension_unit?: {
    detected?: boolean;
    unit_id?: number | null;
    guid?: string | null;
    controls?: number | null;
  };
};

export type CalibrationStatus = {
  ready?: boolean;
  active_profile_id?: string | null;
  profile_name?: string | null;
  status?: string;
  known_width_mm?: number | null;
  known_height_mm?: number | null;
  pixel_to_mm_x?: number | null;
  pixel_to_mm_y?: number | null;
  mm_per_pixel_x?: number | null;
  mm_per_pixel_y?: number | null;
  pixels_per_mm_x?: number | null;
  pixels_per_mm_y?: number | null;
  confidence?: number | null;
  last_calibrated_at?: string | null;
  error?: string | null;
};

export type CameraProfile = {
  id?: string;
  name?: string;
  status?: string;
  camera?: Record<string, unknown>;
  scan_mat?: {
    name?: string;
    status?: string;
    known_width_mm?: number | null;
    known_height_mm?: number | null;
  };
  calibration?: Partial<CalibrationStatus>;
  [key: string]: unknown;
};

export type CalibrationApplyResponse = {
  ok?: boolean;
  profile?: CameraProfile;
  calibration?: CalibrationStatus & {
    corners?: number[][];
    edge_lengths_px?: Record<string, number>;
    image_width_px?: number | null;
    image_height_px?: number | null;
    pixel_width_px?: number;
    pixel_height_px?: number;
  };
  error?: string;
};

export type ScanMatDiagnostics = {
  image_width?: number | null;
  image_height?: number | null;
  mode?: string;
  edges_found?: boolean;
  edge_pixels?: number | null;
  contour_count?: number;
  candidate_quad_count?: number;
  largest_contour_area?: number | null;
  largest_contour_area_ratio?: number | null;
  selected_quad_area?: number | null;
  selected_quad_area_ratio?: number | null;
  corners_detected?: boolean;
  rectified_available?: boolean;
  failure_reason?: string | null;
  suggestions?: string[];
};

export type MeasurementStatus = {
  ready?: boolean;
  measurement_engine_ready?: boolean;
  active_profile_id?: string | null;
  active_profile_name?: string | null;
  calibration_ready?: boolean;
  calibration_confidence?: number | null;
  supported_methods?: string[];
  error?: string | null;
};

export type MeasurementResult = {
  ok?: boolean;
  error?: string;
  measurement?: {
    bbox_px?: {
      x?: number;
      y?: number;
      width?: number;
      height?: number;
    };
    bbox_mm?: {
      width?: number;
      height?: number;
    };
    area_px?: number;
    area_mm2?: number;
    confidence?: number;
    method?: string;
  };
  calibration?: {
    ready?: boolean;
    profile_id?: string | null;
    profile_name?: string | null;
    mm_per_pixel_x?: number | null;
    mm_per_pixel_y?: number | null;
    pixels_per_mm_x?: number | null;
    pixels_per_mm_y?: number | null;
    confidence?: number | null;
    error?: string | null;
  };
  diagnostics?: {
    image_width?: number | null;
    image_height?: number | null;
    contour_count?: number;
    candidate_count?: number;
    selected_area_ratio?: number | null;
    failure_reason?: string | null;
    suggestions?: string[];
  };
};

export type DashboardStatus = {
  brain?: {
    overall?: string;
    ready?: boolean;
    runtime?: {
      host?: string;
      model?: string;
      engine?: string;
    };
    postgres?: string;
    exact_memory?: string;
    semantic_memory?: string;
    last_topic?: string;
    recent_history_rows_checked?: number;
    llm_endpoint?: string;
    local_embeddings?: string;
  };
  model?: {
    online?: boolean;
    active_model_id?: string;
    active_model_name?: string;
    runtime?: string;
    host?: string;
    detail?: string;
  };
  vision?: {
    online?: boolean;
    overall?: string;
    runtime?: string;
    host?: string;
    port?: number;
    active_model_id?: string;
    active_model_name?: string;
    detail?: string;
    capabilities?: string[];
  };
  memory?: {
    exact_memory?: {
      fact_count?: number;
      keys?: string[];
      online?: boolean;
    };
    semantic_memory?: {
      online?: boolean;
      detail?: string;
    };
    postgres?: {
      online?: boolean;
      detail?: string;
    };
    local_embeddings?: {
      online?: boolean;
      detail?: string;
    };
    recent_history?: {
      rows_checked?: number;
    };
    last_topic?: string;
  };
  martybench?: {
    available?: boolean;
    run_id?: string;
    variant?: string;
    elapsed_seconds?: number | string;
    started_at?: string;
    run_folder?: string;
    score?: {
      total?: number | null;
      max_total?: number;
      verdict?: string;
    };
  };
  devices?: DeviceStatus;
  camera_diagnostics?: CameraDiagnosticsStatus;
  calibration?: CalibrationStatus;
  measurement?: MeasurementStatus;
};
