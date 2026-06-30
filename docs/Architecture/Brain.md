# Brain and Router Architecture

## Purpose
The brain/router layer decides how Jarvis should respond to a request.

## Responsibilities
- Route requests to the correct model or skill
- Maintain session context
- Use memory when helpful
- Keep tool behavior predictable
- Avoid unnecessary coupling between features

## Design Rules
- Routing logic should remain readable
- Skills should be modular
- Memory should be explicit, not magical
- Model-specific logic should be isolated where possible

## Future Work
- Better skill registry
- Confidence-based routing
- Structured planning for Phase 4
