import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi, type LoginPayload } from '@/api/auth'
import {
  AUTH_TOKEN_KEY,
  AUTH_USER_KEY,
  clearStoredAuth,
} from '@/utils/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(AUTH_TOKEN_KEY) ?? '')
  const username = ref(localStorage.getItem(AUTH_USER_KEY) ?? '')
  const mustChangePassword = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))

  async function login(payload: LoginPayload): Promise<boolean> {
    const result = await authApi.login(payload)
    token.value = result.token
    username.value = result.username
    mustChangePassword.value = result.must_change_password
    localStorage.setItem(AUTH_TOKEN_KEY, result.token)
    localStorage.setItem(AUTH_USER_KEY, result.username)
    return result.must_change_password
  }

  function logout(): void {
    clearStoredAuth()
    token.value = ''
    username.value = ''
    mustChangePassword.value = false
    void authApi.logout().catch(() => undefined)
  }

  return {
    token,
    username,
    mustChangePassword,
    isAuthenticated,
    login,
    logout,
  }
})
