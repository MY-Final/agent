export const BACKEND_URL_KEY = 'tender-analysis-backend-url'
export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000'

export function normalizeBackendUrl(value: string): string {
  return value.trim().replace(/\/+$/, '')
}

/** 是否运行在 Tauri 桌面容器内（普通 Web 浏览器环境为 false）。 */
export function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

/**
 * 默认后端地址：
 * 1. 构建时可用 VITE_BACKEND_URL 显式指定；
 * 2. Tauri 桌面端默认 127.0.0.1:8000；
 * 3. 纯 Web 浏览器默认同源（''），由 nginx 等把 /api、/health 反代到后端。
 */
export function getDefaultBackendUrl(): string {
  const envUrl = (import.meta.env.VITE_BACKEND_URL as string | undefined)?.trim()
  if (envUrl) return normalizeBackendUrl(envUrl)
  if (isTauri()) return DEFAULT_BACKEND_URL
  return ''
}

export function getStoredBackendUrl(): string {
  const stored = localStorage.getItem(BACKEND_URL_KEY)
  return normalizeBackendUrl(stored || getDefaultBackendUrl())
}
