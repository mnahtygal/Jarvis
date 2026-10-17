# Jarvis UI

Jarvis uses a local React 19, TypeScript, and Vite interface backed by the Flask
API. The UI keeps conversation history only in browser memory; refreshing the
page, closing the browser, or restarting the UI clears it.

## Start and stop

From the repository root, use the existing launcher:

```bash
./scripts/jarvis start
```

This starts or validates the text model and any installed vision model, waits for
the Flask API, starts Vite, and waits for the UI readiness check. If the optional
vision model is absent, startup continues in a clearly reported text-only mode.
The full workstation boot sequence remains available as `./scripts/jarvis startup`.

- UI: `http://localhost:5173`
- Flask API: `http://127.0.0.1:5000`
- Text model: `http://127.0.0.1:8080`
- Vision model: `http://127.0.0.1:8081`

Flask remains bound to loopback. The UI does not proxy or expose Developer Agent
routes to the local network; remote-device API access requires a separately
reviewed authenticated deployment path.

Stop the API and UI with:

```bash
./scripts/jarvis stop
```

The stop command deliberately leaves the model servers running.

## Readiness and troubleshooting

Run the existing non-mutating health command:

```bash
./scripts/jarvis status
```

Direct checks are also available:

```bash
curl --fail http://127.0.0.1:5000/health
curl --fail http://127.0.0.1:5000/api/status/dashboard
curl --fail http://127.0.0.1:5173
```

Logs and PID files use the existing locations:

- API log: `/tmp/jarvis-api.log`
- UI log: `/tmp/jarvis_ui.log`
- model logs: `/tmp/Qwen3.log` and `/tmp/GemmaVision.log`
- API/UI PID files: `/tmp/jarvis-api.pid` and `/tmp/jarvis-ui.pid`

If startup refuses port 5000 or 5173, another process owns the expected port.
Inspect it instead of starting a second Jarvis process. A model-unavailable status
means the UI and API are reachable but model-backed conversation may be limited.
After changing Python or frontend source, run `./scripts/jarvis stop` followed by
`./scripts/jarvis start`; the launcher intentionally preserves already-running
healthy services instead of hot-reloading them.

## Development checks

```bash
npm test
npm run lint
npm run build
```

No frontend persistence, approval state, or security policy is implemented here.
Text such as `approve` and `cancel` is sent through `/text` like any other message;
the backend remains the sole authority for pending approvals and Developer Agent
execution.
