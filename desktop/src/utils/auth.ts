export const AUTH_TOKEN_KEY = 'tender-analysis-auth-token'
export const AUTH_USER_KEY = 'tender-analysis-auth-user'

export function getStoredToken(): string {
  return localStorage.getItem(AUTH_TOKEN_KEY) ?? ''
}

export function clearStoredAuth(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY)
  localStorage.removeItem(AUTH_USER_KEY)
}
