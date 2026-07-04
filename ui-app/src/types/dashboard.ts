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
    video_devices?: string[];
    usb_lines?: string[];
    test_command?: string;
  };
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
};
