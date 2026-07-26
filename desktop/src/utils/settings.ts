export const BACKEND_URL_KEY = 'tender-analysis-backend-url'
export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000'

export function normalizeBackendUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

export function getStoredBackendUrl(): string {
  const stored = localStorage.getItem(BACKEND_URL_KEY)
  return normalizeBackendUrl(stored || DEFAULT_BACKEND_URL)
}
