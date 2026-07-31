import { request } from './client'
import type {
  RuntimeHealthMap,
  RuntimeSettingsInput,
  RuntimeSettingsRead,
} from '@/types/runtime'

export const runtimeApi = {
  get: () =>
    request<RuntimeSettingsRead>({
      method: 'GET',
      url: '/api/v1/runtime/settings',
    }),

  test: (payload: RuntimeSettingsInput) =>
    request<RuntimeHealthMap>({
      method: 'POST',
      url: '/api/v1/runtime/settings/test',
      data: payload,
    }),

  save: (payload: RuntimeSettingsInput) =>
    request<RuntimeSettingsRead>({
      method: 'PUT',
      url: '/api/v1/runtime/settings',
      data: payload,
    }),
}
