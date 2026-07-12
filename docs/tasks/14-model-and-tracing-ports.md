---
phase: 2
order: "14"
mvp: true
title: Model port + tracing port
refs:
  - PRD §9, §14
  - SDD §8 (ModelPort), §23
---

# 14 — Model port + tracing port

Goal: Provider-independent model port (Anthropic impl later) and a tracing port (LangSmith impl later) so agent/core never import SDKs.

## Checklist

- [ ] `ModelPort`: invoke model with messages/tools, return structured response + usage; support tool-calling.
- [ ] `TracingPort`: start/end span, set attributes, link correlation ID.
- [ ] Model output is treated as untrusted input (validated against structured app input).
- [ ] Trace privacy: redaction hooks for full message text, image-derived text, credentials, object URLs, sensitive notes.
- [ ] No Anthropic/LangSmith SDK types in ports or core.
- [ ] Ports allow deterministic fakes for agent tests.
