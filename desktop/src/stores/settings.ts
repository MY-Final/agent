import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { testBackendConnection } from '@/api/client'
import type { HealthData } from '@/types/api'
import {
  BACKEND_URL_KEY,
  DEFAULT_BACKEND_URL,
  getStoredBackendUrl,
  normalizeBackendUrl,
} from '@/utils/settings'

export const useSettingsStore = defineStore('settings', () => {
  const backendUrl = ref(getStoredBackendUrl())
  const health = ref<HealthData | null>(null)
  const checking = ref(false)
  const lastCheckedAt = ref<Date | null>(null)

  const isHealthy = computed(() => health.value?.status === 'healthy')

  function saveBackendUrl(value: string): void {
    const normalized = normalizeBackendUrl(value) || DEFAULT_BACKEND_URL
    backendUrl.value = normalized
    localStorage.setItem(BACKEND_URL_KEY, normalized)
  }

  async function checkHealth(candidate = backendUrl.value): Promise<HealthData> {
    checking.value = true
    try {
      const result = await testBackendConnection(candidate)
      health.value = result
      lastCheckedAt.value = new Date()
      return result
    } catch (error) {
      health.value = null
      lastCheckedAt.value = new Date()
      throw error
    } finally {
      checking.value = false
    }
  }

  return {
    backendUrl,
    health,
    checking,
    lastCheckedAt,
    isHealthy,
    saveBackendUrl,
    checkHealth,
  }
})
