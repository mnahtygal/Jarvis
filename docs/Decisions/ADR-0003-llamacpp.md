# ADR-0003 – llama.cpp for Local Model Serving

## Status
Accepted

## Context
Jarvis needs local model serving on NVIDIA Jetson hardware.

## Decision
Use llama.cpp server with OpenAI-compatible endpoints for local text and vision models where practical.

## Consequences
- Simple local API integration
- Good fit for GGUF models
- Works well with the existing Flask backend
- Keeps cloud dependencies optional

## Rationale
llama.cpp provides a practical, flexible, and hardware-friendly serving layer for Jarvis.
