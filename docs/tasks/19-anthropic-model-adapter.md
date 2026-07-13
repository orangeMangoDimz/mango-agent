---
phase: 3
order: "19"
mvp: true
title: LangChain model adapter
refs:
  - PRD §9, §14, §17.1
  - SDD §8 (LangChainModelAdapter), §22.3
  - depends_on: [14]
---

# 19 — LangChain model adapter

Goal: Implement `ModelPort` over LangChain's chat-model abstraction, configured for Anthropic in v1, with tool-calling support; model output stays untrusted.

## Checklist

- [ ] Map messages + tool schemas through LangChain; parse tool calls + content.
- [ ] Support image input (screenshot context) per provider capability.
- [ ] Translate model errors/timeouts to stable application errors without importing provider SDKs.
- [ ] Configurable model selection from env.
- [ ] No direct model-provider SDK dependencies, imports, or calls in Mango source code.
- [ ] Redaction hook for sensitive content before sending where applicable.
- [ ] Contract tests with an injected deterministic LangChain chat model for agent tests.
