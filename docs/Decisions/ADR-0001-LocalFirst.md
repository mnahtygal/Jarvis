# ADR-0001 – Local-First Architecture

## Status
Accepted

## Context
Jarvis is intended to run primarily on personal hardware without depending on cloud AI services.

## Decision
Jarvis will be built as a local-first system.

## Consequences
- Local models are preferred
- Local memory is preferred
- Cloud services are optional integrations only
- Reliability and maintainability take priority over convenience

## Rationale
The project goal is a personal engineering assistant that remains useful even without internet access.
