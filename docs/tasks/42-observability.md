---
phase: 10
order: "42"
mvp: true
title: Observability — logging, metrics, correlation
refs:
  - PRD §4.1(10)
  - SDD §23, §22.2
  - depends_on: [20]
---

# 42 — Observability — logging, metrics, correlation

Goal: Structured logs + agent/infra metrics + correlation IDs propagated end-to-end; privacy by default.

## Checklist

- [ ] Correlation ID generated per inbound event; propagated through adapter → agent → use cases → infra → LangSmith.
- [ ] Structured log dimensions: env, bot instance, channel, agent command, correlation id, privacy-safe user id, op type, proposal/op id, tool name, duration, outcome/error category.
- [ ] Agent metrics: completion rate, tool success, invalid-arg rate, max-step termination, follow-up rate, proposal approve/revise/reject/expire, duplicate event/op counts.
- [ ] Infra metrics: message latency, PG tx latency/failures, Redis latency/errors, R2 upload/retrieve/cleanup failures, provider delivery failures, pending/orphaned attachments, expired proposals.
- [ ] Sensitive content redacted from logs/traces by default.
- [ ] Secrets never in logs/traces.
