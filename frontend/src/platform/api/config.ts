/** The API origin without a path. Set VITE_API_BASE_URL per environment. */
export const API_ORIGIN: string = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export const API_PREFIX = '/api/v1'
