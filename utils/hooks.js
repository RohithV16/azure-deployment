const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const HOOK_TIMEOUT = 60000;

async function runHook(hookName, config, env = {}) {
  const hooks = config.hooks || {};
  const hookPath = hooks[hookName];
  
  if (!hookPath) {
    return { executed: false, skipped: true };
  }
  
  const resolvedPath = path.isAbsolute(hookPath) 
    ? hookPath 
    : path.join(os.homedir(), hookPath);
  
  if (!fs.existsSync(resolvedPath)) {
    return { executed: false, error: `Hook script not found: ${resolvedPath}` };
  }
  
  return new Promise((resolve) => {
    const hookEnv = {
      ...process.env,
      DEPLOY_HOOK: hookName,
      ...env
    };
    
    const child = spawn(resolvedPath, [], {
      env: hookEnv,
      stdio: 'inherit',
      shell: true
    });
    
    const timeout = setTimeout(() => {
      child.kill('SIGTERM');
      resolve({ executed: true, error: 'Hook timed out after 60s' });
    }, HOOK_TIMEOUT);
    
    child.on('close', (code) => {
      clearTimeout(timeout);
      resolve({ 
        executed: true, 
        exitCode: code,
        success: code === 0
      });
    });
    
    child.on('error', (err) => {
      clearTimeout(timeout);
      resolve({ executed: true, error: err.message });
    });
  });
}

module.exports = {
  runHook
};
