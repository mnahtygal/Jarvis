# Jarvis API

## Purpose
The Flask API is the bridge between Jarvis backend capabilities and the React dashboard.

## Current Responsibilities
- Health/status checks
- Chat and LLM routing
- Vision workflows
- Camera capture
- Scan Mat mode
- Memory operations
- Dashboard data

## API Design Rules
- Preserve backward compatibility
- Return structured JSON
- Include clear error messages
- Avoid hidden side effects
- Keep endpoints small and focused

## Documentation Standard
Every new endpoint should document:
- route
- method
- request body
- response body
- failure cases
- related frontend component

## Camera Roles

### `GET /api/cameras`

Returns discovered V4L2 cameras, configured Jarvis camera roles, the active role, and the active camera.

Response body:

```json
{
  "ok": true,
  "default_role": "workbench",
  "active_role": "workbench",
  "active_camera": {},
  "cameras": [],
  "devices": []
}
```

Related frontend component: Vision Lab camera selector.

### `GET /api/camera/active`

Returns the active camera role and active camera record.

Response body:

```json
{
  "ok": true,
  "active_role": "workbench",
  "active_camera": {}
}
```

### `POST /api/camera/active`

Switches the active camera role without restarting Jarvis.

Request body:

```json
{
  "role": "workbench"
}
```

Response body: same shape as `GET /api/cameras`.

Failure cases:
- `400` when `role` is missing.
- `409` when the requested role is unknown or the camera is unavailable.

### `POST /api/camera/snapshot`

Backward compatible. With no body, captures from the active camera role. Optional request fields:

```json
{
  "role": "workbench",
  "device": "/dev/video2"
}
```

Explicit `device` is retained for diagnostics and compatibility, but Vision Lab should prefer roles.

## Future Work
- Formal endpoint table
- OpenAPI export
- API smoke tests
