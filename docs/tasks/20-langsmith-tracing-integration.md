---
phase: 3
order: "20"
mvp: true
title: LangSmith tracing integration
refs:
  - PRD §4.1(10), §17.1
  - SDD §23 (observability, trace privacy)
  - depends_on: [14]
---

# 20 — LangSmith tracing integration

Goal: Implement `TracingPort` with LangSmith; propagate correlation ID; enforce trace privacy.

## Checklist

- [ ] Wrap LangGraph execution + use cases in spans linked by correlation ID.
- [ ] Capture: agent command, tool name, operation type, proposal/op id, durations, outcome/error category.
- [ ] Redact full message text, image-derived text, credentials, object URLs, sensitive notes in prod traces.
- [ ] Configurable on/off via env; disabled cleanly when missing creds.
- [ ] No LangSmith SDK imports in core/agent (only in `integrations/llm` + adapter).
- [ ] Verify a single inbound event produces one traceable chain.
