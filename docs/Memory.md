# Jarvis Memory

Jarvis memory uses PostgreSQL + pgvector.

## Purpose

Memory should help Jarvis remember useful project facts, prior scans, decisions, and engineering context.

## Memory Types

Potential memory categories:

- semantic facts
- project notes
- scan records
- generated model records
- benchmark records
- troubleshooting notes
- workshop settings

## Rules

Do not introduce another vector database unless explicitly requested.

Memory must remain inspectable and maintainable.

Avoid storing unnecessary personal data.

Prefer structured project records for engineering workflows.

## Scan Memory

Future scan records should include:

- scan ID
- project ID
- timestamp
- raw image path
- annotated image path
- rectified image path
- measurement metadata
- generated OpenSCAD path if available
- notes

## Project Memory

Future project records should include:

- project name
- description
- related scans
- related generated files
- status
- next action
- notes

