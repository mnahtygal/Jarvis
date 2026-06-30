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

## Future Work
- Formal endpoint table
- OpenAPI export
- API smoke tests
