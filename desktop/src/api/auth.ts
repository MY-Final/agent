import { request } from './client'
import type { ChangePasswordPayload, LoginResult } from '@/types/auth'

export interface LoginPayload {
  username: string
  password: string
}

export const authApi = {
  login: (payload: LoginPayload) =>
    request<LoginResult>({ method: 'POST', url: '/api/v1/auth/login', data: payload }),

  changePassword: (payload: ChangePasswordPayload) =>
    request<null>({ method: 'POST', url: '/api/v1/auth/change-password', data: payload }),

  logout: () => request<null>({ method: 'POST', url: '/api/v1/auth/logout' }),
}
