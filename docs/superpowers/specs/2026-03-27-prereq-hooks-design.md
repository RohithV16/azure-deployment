# Design: Prerequisite Check, Secret Rotation & Custom Hooks

**Date**: 2026-03-27
**Status**: Approved

---

## 1. Prerequisite Check

### Description
Validate environment, PAT, and permissions before deployment to fail fast with clear errors.

### Command
```bash
mandg check
```

### Checks
| Check | Description |
|-------|-------------|
| Config exists | `~/.azure-deploy-aem.json` present |
| PAT configured | Token not empty |
| PAT valid | Test Azure DevOps API call |
| Org reachable | Can connect to organization |
| Project accessible | Can access the configured project |
| Pipeline exists | DEV/STAGE pipeline IDs valid |
| Permissions | User can trigger builds |

### Output
```
🔍 Running prerequisite checks...

✅ Config file exists
✅ PAT configured
✅ PAT valid
✅ Organization reachable
✅ Project accessible
✅ Pipeline DEV exists
✅ Pipeline STAGE exists
✅ Build trigger permissions

All checks passed! ✅
```

On failure:
```
❌ PAT validation failed: 401 Unauthorized
   Run: mandg update --token <your-pat>
```

---

## 2. Secret Rotation (PAT Helper)

### Description
Helper to rotate PAT tokens with Azure DevOps.

### Command
```bash
mandg rotate-token --old <old-pat> --new <new-pat>
mandg rotate-token --generate  # Generate new PAT via Azure DevOps
```

### Behavior
- Validate new PAT works before replacing
- Backup old config before updating
- Update `~/.azure-deploy-aem.json` with new token

---

## 3. Custom Hooks

### Description
Run custom scripts at defined lifecycle hooks during deployment.

### Hook Points
| Hook | When | Available Args |
|------|------|-----------------|
| `pre-deploy` | Before triggering build | `--pipeline`, `--branch`, `--build-id` |
| `post-deploy` | After deployment completes | `--pipeline`, `--branch`, `--build-id`, `--status` |
| `pre-retry` | Before retry attempt | `--pipeline`, `--attempt`, `--max-retries` |
| `on-failure` | After all retries exhausted | `--pipeline`, `--error` |

### Configuration
In `~/.azure-deploy-aem.json`:
```json
{
  "hooks": {
    "pre-deploy": "./scripts/pre-deploy.sh",
    "post-deploy": "./scripts/post-deploy.sh"
  }
}
```

### Execution
- Run hook scripts with spawn
- Pass args as environment variables: `DEPLOY_PIPELINE=dev`, `DEPLOY_BRANCH=dev`, etc.
- Continue deployment regardless of hook exit code (log warning if failed)
- Timeout after 60 seconds per hook

---

## 4. Files to Modify

1. `cli.js` - Add `check`, `rotate-token` commands; add hook execution
2. `services/azure-service.js` - Add permission check method
3. Create `utils/hooks.js` - Hook execution utility

---

## 5. Acceptance Criteria

- [ ] `mandg check` validates all prerequisites
- [ ] Clear error messages on failure
- [ ] `mandg rotate-token` updates PAT securely
- [ ] Pre/post hooks execute at correct times
- [ ] Hooks receive correct environment variables