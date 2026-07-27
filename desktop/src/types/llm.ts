export type LLMProviderType = 'openai_compatible'

export interface LLMProvider {
  id: string
  name: string
  provider_type: LLMProviderType
  base_url: string
  api_key: string
  default_model: string
  timeout_seconds: number
  is_default: boolean
  is_enabled: boolean
  extra_config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface LLMProviderCreateInput {
  name: string
  provider_type: LLMProviderType
  base_url: string
  api_key: string
  default_model: string
  timeout_seconds: number
  is_default: boolean
  is_enabled: boolean
  extra_config: Record<string, unknown>
}

export interface LLMProviderUpdateInput {
  name?: string
  provider_type?: LLMProviderType
  base_url?: string
  api_key?: string
  default_model?: string
  timeout_seconds?: number
  is_default?: boolean
  is_enabled?: boolean
  extra_config?: Record<string, unknown>
}

export interface CurrentLLMConfig {
  source: 'database' | 'env'
  provider_id: string | null
  provider_name: string | null
  provider_type: LLMProviderType | string
  base_url: string | null
  api_key: string | null
  default_model: string
  timeout_seconds: number
  extra_config: Record<string, unknown>
  is_configured: boolean
}

export interface LLMConnectionInput {
  provider_id?: string
  base_url: string
  api_key?: string
  timeout_seconds: number
}

export interface LLMModelListResult {
  models: string[]
  count: number
}

export interface LLMConnectionTestInput extends LLMConnectionInput {
  model: string
}

export interface LLMConnectionTestResult {
  success: boolean
  model: string
  latency_ms: number
}
