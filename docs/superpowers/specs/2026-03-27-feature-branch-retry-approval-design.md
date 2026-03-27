# Design: Feature Branch Deployment, Auto-Retry & Approval Workflow

**Date**: 2026-03-27
**Status**: Approved

---

## 1. Feature Branch Deployment (DEV only)

### Description
Allow users to deploy feature branches to DEV environment with interactive branch selection.

### Command Changes
- Add `--branch <branchname>` option to `mandg dev` command
- `mandg stage` remains unchanged (tag-based only)

### Behavior

| Scenario | Behavior |
|----------|----------|
| `--branch` specified | Use branch directly |
| `--branch` omitted | Fetch branches from Azure DevOps, show interactive dropdown with search |

### Interactive Dropdown
- Use `inquirer` npm package
- Fetch user's branches from Azure DevOps: `/_api/v3/repos/{repoId}/refs?filter=heads/`
- Show fuzzy search dropdown
- User selects branch, proceed with deployment

### Validation
- Validate branch exists in Azure DevOps
- Fail with clear error if branch not found

### Example Usage
```bash
# Interactive branch selection
mandg dev

# Direct branch deployment
mandg dev --branch feature/ADW-1234
```

---

## 2. Auto-Retry on Failure

### Description
Automatically retry failed builds without user intervention.

### Behavior
- **Retries**: 2 attempts after initial failure
- **Delay**: 30 seconds between retries
- **Trigger**: Only on build failure (result === 'failed')
- **Notifications**: Silent - no user notification between attempts
- Final result (success or failure) notified at end

### Implementation
- After initial build trigger fails, wait 30s, re-check build status
- If failed again after 2 retries, mark as failed and notify
- Use existing `getBuild()` to poll status

---

## 3. Approval Workflow

### Description
Automatically approve pipelines if initiator has permissions, otherwise wait for external approval.

### Behavior

| Condition | Behavior |
|-----------|----------|
| Initiator has approval permission | Auto-approve via Azure DevOps API |
| No permission | Wait for external approval |

### Implementation Steps

1. **Check permissions**: Query Azure DevOps API to check if current user can approve
   - Endpoint: `POST /_apis/pipeline/approvals/query`

2. **Auto-approve**: If has permission, call approval API
   - Endpoint: `PATCH /_apis/pipeline/approvals/{approvalId}`

3. **Wait for approval**: If no permission
   - Poll every 30 seconds for approval status
   - Show "Waiting for approval..." message
   - Max wait: 2 hours (7200 seconds / 140 polls)
   - Fail if timeout

### Error Handling
- Log "Waiting for approval..." while polling
- Notify on approval received
- Fail gracefully on timeout

---

## 4. Dependencies

Add to `package.json`:
- `inquirer` - ^8.0.0 (interactive dropdown)
- `ora` - spinners for waiting states (optional, for polish)

---

## 5. Files to Modify

1. `package.json` - Add inquirer dependency
2. `cli.js` - Add --branch option, modify dev command
3. `services/azure-service.js` - Add branch fetching, approval methods
4. `services/git-service.js` - No changes

---

## 6. Acceptance Criteria

- [ ] `mandg dev` without --branch shows interactive branch dropdown
- [ ] `mandg dev --branch feature/X` deploys specified branch
- [ ] Failed builds auto-retry twice with 30s delay
- [ ] User with approval permissions auto-approves via API
- [ ] User without permissions waits (max 2h) for external approval
- [ ] Stage command remains unchanged