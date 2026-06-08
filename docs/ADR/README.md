# Architecture Decision Records (ADR)

This directory contains Architecture Decision Records for the `underwrite` platform. Each ADR documents a significant architectural choice, including the context, the problem, the decision, alternatives considered, and the consequences.

## Format

Every ADR follows the same structure:

- **Context**: Background and forces that led to the decision
- **Problem**: The specific problem or gap being addressed
- **Decision**: The chosen approach (with code paths)
- **Alternatives Considered**: Other approaches evaluated and why they were rejected
- **Consequences**: Positive and negative outcomes of the decision

## Index

| ID | Title | Status |
|----|-------|--------|
| 001 | Nano-Service Architecture | Accepted |
| 002 | Event-Driven Communication with Typed Events | Accepted |
| 003 | Ed25519 Cryptographic Provenance | Accepted |
| 004 | Saga Orchestration for Distributed Transactions | Accepted |

## Status Meanings

- **Accepted**: The decision has been implemented and is in use
- **Deprecated**: The decision is no longer recommended but still in use
- **Superseded**: A later ADR has replaced this decision
