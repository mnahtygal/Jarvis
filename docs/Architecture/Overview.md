# Architecture Overview

Jarvis is a modular local-first AI assistant.

## Major Subsystems
- Flask API
- Brain/router
- Skills layer
- Local LLM services
- Vision pipeline
- Voice pipeline
- PostgreSQL memory
- React/Vite dashboard
- Operational scripts

## High-Level Flow
User input enters through the dashboard, voice, terminal, or future automation. The API routes the request to the brain/router, which selects the appropriate model, skill, or memory workflow.

## Design Goals
- Local-first
- Modular
- Observable
- Testable
- Maintainable
- Safe for workshop use
