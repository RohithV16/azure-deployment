# Design: Watch Mode for Recurring DEV Deployment

**Date**: 2026-03-27
**Status**: Approved

---

## 1. Overview

Add a watch mode to the `mandg dev` command that continuously monitors the dev branch for merged PRs and automatically triggers deployments.

---

## 2. Behavior

| Step | Action |
|------|--------|
| 1 | Poll Azure DevOps every 10 minutes for PRs merged to `dev` branch |
| 2 | When new PR merge detected: wait 5 minutes (fixed delay) |
| 3 | Trigger DEV deployment |
| 4 | If deployment fails: retry up to 2 times (existing retry logic) |
| 5 | After deployment completes: continue polling for new merges |
| 6 | Run until manually stopped (Ctrl+C) |

---

## 3. CLI Changes

### New Options
- `--watch` or `--bg` - Run in background watch mode (mutually exclusive with immediate deploy)
- `--poll-interval <minutes>` - How often to check for new merges (default: 10)
- `--delay <minutes>` - Delay after PR merge before deploying (default: 5)

### Command
```bash
# Watch mode (background)
mandg dev --watch
mandg dev --bg

# With custom intervals
mandg dev --watch --poll-interval 5 --delay 3
```

### Exit
- Press `Ctrl+C` to stop watching
- On exit: print "Stopped watching"

---

## 4. Detection Logic

Track the last deployed PR by:
1. Store last deployed PR info in a local file (e.g., `~/.mandg-watch-state.json`)
2. On each poll: query Azure DevOps for PRs merged to `dev` since last deployed PR
3. If new PR found: increment counter, wait delay, deploy

### State File
```json
{
  "lastPrId": 123,
  "lastPrMergeTime": "2026-03-27T10:00:00Z",
  "lastDeployTime": "2026-03-27T10:05:00Z"
}
```

---

## 5. Deployment Flow

When new PR detected:
1. Log: "New PR #<id> merged. Waiting <delay> minutes..."
2. Wait for delay (console.log countdown every minute)
3. Trigger deployment (reuse existing logic)
4. Apply retry logic on failure
5. Log result (success/failure)
6. Update state file
7. Continue polling

---

## 6. Edge Cases

| Scenario | Behavior |
|----------|----------|
| Multiple PRs merged during delay | Deploy all sequentially after delay |
| Deployment in progress when new PR merges | Complete current, then deploy new |
| No new PRs | Continue polling silently |
| Network error during poll | Log warning, retry after next interval |
| Ctrl+C during deployment | Wait for deployment to complete, then exit |

---

## 7. Files to Modify

1. `cli.js` - Add watch mode option and loop logic
2. `services/azure-service.js` - Add method to get merged PRs since timestamp
3. Create: `utils/watch-state.js` - Handle state file read/write

---

## 8. Acceptance Criteria

- [ ] `mandg dev --watch` starts watch mode
- [ ] Polls every 10 minutes by default
- [ ] Waits 5 minutes after PR merge before deploying
- [ ] Retries failed deployments twice
- [ ] Continues polling after deployment completes
- [ ] Ctrl+C stops the watcher
- [ ] State persists across restarts