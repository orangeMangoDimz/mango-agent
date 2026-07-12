---
phase: 3
order: "19"
mvp: true
title: Anthropic model adapter
refs:
  - PRD §9, §14, §17.1
  - SDD §8 (AnthropicAdapter), §22.3
  - depends_on: [14]
---

# 19 — Anthropic model adapter

Goal: Implement `ModelPort` over Anthropic with tool-calling support; model output stays untrusted.

## Checklist

- [ ] Map messages + tool schemas to Anthropic request; parse tool calls + content.
- [ ] Support image input (screenshot context) per provider capability.
- [ ] Translate Anthropic errors/timeouts to stable application errors.
- [ ] Configurable model selection from env.
- [ ] No Anthropic SDK types leak into core/agent (only via ModelPort).
- [ ] Redaction hook for sensitive content before sending where applicable.
- [ ] Contract test with recorded request/response fixtures + a fake mode for agent tests.
