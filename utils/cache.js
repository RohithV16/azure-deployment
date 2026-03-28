class Cache {
  constructor() {
    this.store = new Map();
  }

  get(key) {
    const item = this.store.get(key);
    if (!item) return null;
    if (Date.now() > item.expires) {
      this.store.delete(key);
      return null;
    }
    return item.value;
  }

  set(key, value, ttlSeconds = 300) {
    this.store.set(key, {
      value,
      expires: Date.now() + ttlSeconds * 1000
    });
  }

  has(key) {
    return this.get(key) !== null;
  }

  delete(key) {
    this.store.delete(key);
  }

  clear() {
    this.store.clear();
  }

  keys() {
    return Array.from(this.store.keys());
  }
}

const cache = new Cache();

const CACHE_KEYS = {
  REPO_ID: (name) => `repo:${name}`,
  BRANCHES: (repoId) => `branches:${repoId}`,
  PIPELINE_DEFS: 'pipeline_definitions',
  USER_PROFILE: 'user_profile',
  TAGS: (repoName) => `tags:${repoName}`,
  LAST_BUILD: (defId) => `last_build:${defId}`
};

const TTL = {
  REPO_ID: 600,
  BRANCHES: 300,
  PIPELINE_DEFS: 300,
  USER_PROFILE: 1800,
  TAGS: 300,
  LAST_BUILD: 60
};

module.exports = { cache, CACHE_KEYS, TTL };
