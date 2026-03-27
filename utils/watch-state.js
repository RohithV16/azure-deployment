const fs = require('fs');
const path = require('path');
const os = require('os');

const STATE_FILE = path.join(os.homedir(), '.mandg-watch-state.json');

function getState() {
  if (fs.existsSync(STATE_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    } catch (e) {
      return { lastPrId: null, lastPrMergeTime: null, lastDeployTime: null };
    }
  }
  return { lastPrId: null, lastPrMergeTime: null, lastDeployTime: null };
}

function saveState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

function resetState() {
  if (fs.existsSync(STATE_FILE)) {
    fs.unlinkSync(STATE_FILE);
  }
}

module.exports = {
  getState,
  saveState,
  resetState,
  STATE_FILE
};
