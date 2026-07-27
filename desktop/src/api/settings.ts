import { request } from './client'
import type {
  CurrentLLMConfig,
  LLMConnectionInput,
  LLMConnectionTestInput,
  LLMConnectionTestResult,
  LLMModelListResult,
  LLMProvider,
  LLMProviderCreateInput,
  LLMProviderUpdateInput,
} from '@/types/llm'

export const llmSettingsApi = {
  listProviders: () =>
    request<LLMProvider[]>({
      method: 'GET',
      url: '/api/v1/settings/llm/providers',
    }),

  getProvider: (providerId: string) =>
    request<LLMProvider>({
      method: 'GET',
      url: `/api/v1/settings/llm/providers/${providerId}`,
    }),

  getCurrent: () =>
    request<CurrentLLMConfig>({
      method: 'GET',
      url: '/api/v1/settings/llm/current',
    }),

  listModels: (payload: LLMConnectionInput) =>
    request<LLMModelListResult>({
      method: 'POST',
      url: '/api/v1/settings/llm/models',
      data: payload,
      timeout: Math.max(30_000, payload.timeout_seconds * 1000),
    }),

  testConnection: (payload: LLMConnectionTestInput) =>
    request<LLMConnectionTestResult>({
      method: 'POST',
      url: '/api/v1/settings/llm/test',
      data: payload,
      timeout: Math.max(30_000, payload.timeout_seconds * 1000),
    }),

  createProvider: (payload: LLMProviderCreateInput) =>
    request<LLMProvider>({
      method: 'POST',
      url: '/api/v1/settings/llm/providers',
      data: payload,
    }),

  updateProvider: (providerId: string, payload: LLMProviderUpdateInput) =>
    request<LLMProvider>({
      method: 'PUT',
      url: `/api/v1/settings/llm/providers/${providerId}`,
      data: payload,
    }),

  removeProvider: (providerId: string) =>
    request<{ id: string; deleted: boolean }>({
      method: 'DELETE',
      url: `/api/v1/settings/llm/providers/${providerId}`,
    }),

  setDefault: (providerId: string) =>
    request<LLMProvider>({
      method: 'POST',
      url: `/api/v1/settings/llm/providers/${providerId}/set-default`,
    }),
}
