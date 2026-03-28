# Design: Deployment Approval

**Date**: 2026-03-27
**Status**: Approved

---

## 1. Overview

Allow users to approve/reject deployments via interactive CLI before proceeding to STAGE/PROD.

---

## 2. Commands

### Primary Command
```bash
mandg approval
```
Shows interactive dropdown of pending approvals, then prompts for approve/reject.

### Alternative Commands
```bash
mandg approve --build <id> --comment "LGTM"
mandg reject --build <id> --comment "Needs changes"
mandg approvals list
```

---

## 3. Interactive Flow

```
$ mandg approval

📋 Pending Approvals:

  1. DEV → STAGE | Build #452 | feature/ADW-1234 | by John | 5 min ago
  2. DEV → STAGE | Build #451 | hotfix/ADW-125 | by Jane | 12 min ago
  3. DEV → PROD | Build #450 | release/v2.1 | by John | 18 min ago

> Select (1-3) or 'q': 1

🤔 Choose action:

  [A]pprove
  [R]eject
  [Q]uit

> Action: A

💬 Add comment (optional): LGTM
✅ Approved Build #452
```

---

## 4. Implementation

### Azure DevOps API
- Query: `POST /_apis/pipeline/approvals/query`
- Approve: `PATCH /_apis/pipeline/approvals/{approvalId}`
- Reject: `PATCH /_apis/pipeline/approvals/{approvalId}` with status 'rejected'

### Files to Modify
1. `cli.js` - Add approval, approve, reject, approvals commands
2. `services/azure-service.js` - Add queryApprovals, approveBuild, rejectBuild methods

---

## 5. Acceptance Criteria

- [ ] `mandg approval` shows interactive dropdown
- [ ] Can approve via dropdown
- [ ] Can reject via dropdown
- [ ] `mandg approve --build <id>` works directly
- [ ] `mandg reject --build <id>` works directly
- [ ] `mandg approvals list` shows all pending