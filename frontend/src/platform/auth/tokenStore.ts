const KEY = 'unio.session'

let memory: string | null = null

/**
 * localStorage can be unavailable or throw in private windows and some webviews, so every access
 * is guarded and the token also lives in memory for the current page.
 */
export const tokenStore = {
  get(): string | null {
    if (memory) return memory
    try {
      memory = window.localStorage.getItem(KEY)
    } catch {
      // storage blocked: stay signed in for this page only
    }
    return memory
  },
  set(token: string): void {
    memory = token
    try {
      window.localStorage.setItem(KEY, token)
    } catch {
      // see above
    }
  },
  clear(): void {
    memory = null
    try {
      window.localStorage.removeItem(KEY)
    } catch {
      // see above
    }
  },
}
