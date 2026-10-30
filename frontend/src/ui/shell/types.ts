export interface NavEntryView {
  key: string
  label: string
  path: string
  icon: string
  /** Live count from the server, shown when above zero. */
  badge?: number
}

export type ThemePreference = 'light' | 'dark' | 'system'

export function isActivePath(activePath: string, itemPath: string): boolean {
  return activePath === itemPath || activePath.startsWith(`${itemPath}/`)
}
