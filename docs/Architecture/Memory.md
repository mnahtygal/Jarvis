# Memory Architecture

## Purpose
Jarvis memory allows the assistant to remember useful project facts, preferences, and technical context.

## Current Storage
- PostgreSQL
- pgvector
- Semantic search

## Rules
- Do not introduce a second vector database without a clear reason
- Store useful engineering context, not noise
- Keep memory inspectable
- Prefer explicit writes for important facts
- Avoid storing sensitive information unnecessarily

## Future Work
- Project-specific memory
- Scan history
- Maker Lab project memory
- Memory review and cleanup tools
