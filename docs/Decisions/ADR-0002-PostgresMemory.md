# ADR-0002 – PostgreSQL + pgvector for Memory

## Status
Accepted

## Context
Jarvis needs persistent semantic memory for facts, sessions, project notes, and future scan history.

## Decision
Use PostgreSQL with pgvector as the primary memory backend.

## Consequences
- One durable relational store
- Vector search without adding another database
- Easier backup and inspection
- Strong fit for structured project memory

## Alternatives Considered
- ChromaDB
- SQLite vector extensions
- File-based memory

## Rationale
PostgreSQL + pgvector balances reliability, transparency, and capability.
