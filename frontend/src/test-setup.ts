import '@testing-library/jest-dom'

/**
 * jsdom in this setup does not provide localStorage — `typeof localStorage`
 * is 'undefined' even with an explicit origin. Anything touching the auth
 * token (every src/api module goes through `getToken`) therefore cannot be
 * unit tested without this, which is why the API layer had no tests before.
 */
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>()
  const storage: Storage = {
    getItem: key => store.get(key) ?? null,
    setItem: (key, value) => void store.set(key, String(value)),
    removeItem: key => void store.delete(key),
    clear: () => store.clear(),
    key: index => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size
    },
  }
  globalThis.localStorage = storage
}
