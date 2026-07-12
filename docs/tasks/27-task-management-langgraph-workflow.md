---
phase: 5
order: "27"
mvp: true
title: Task-management LangGraph workflow
refs:
  - PRD §13 (workflow), §9
  - SDD §12.1, §12.2 (state diagram), §13.1
  - depends_on: [25, 26, 28]
---

# 27 — Task-management LangGraph workflow

Goal: LangGraph state machine implementing PRD §13 + SDD §12.2 with pause/resume for human approval.

## Checklist

- [ ] Graph state per SDD §12.1 (context, message, op, fields, validation, pending proposal/confirmation, refs, tool results, counters).
- [ ] States: LoadContext → InterpretRequest → ReadFlow / CreateExtraction / UpdateValidation / DeleteTargeting / Unsupported.
- [ ] Create path: ValidateCreate → AskForMissingData or BuildProposal → AwaitApproval → Approve/Revise/Reject.
- [ ] Update path: AskForTarget or ConfirmSensitiveUpdate or ExecuteUpdate.
- [ ] Delete path: AskForTarget → ConfirmDelete → ExecuteDelete.
- [ ] PersistPendingState between turns; resume on next message.
- [ ] Reject → CleanupTemporaryAttachments.
- [ ] Respond → SaveContext.
- [ ] Reads execute immediately (no approval); deletes require confirmation; sensitive updates require confirmation.
- [ ] Approved creation calls `CreateApprovedTask` (verifies approval independently).
- [ ] Agent tests with deterministic fake model + fake tools covering each branch.
