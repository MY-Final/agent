import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import type { ApiResponse, HealthData } from '@/types/api'
import { getStoredBackendUrl, normalizeBackendUrl } from '@/utils/settings'

const AGENT_TIMEOUT_MS = 10 * 60 * 1000

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly code?: number,
    public readonly status?: number,
    public readonly details?: unknown,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

const http = axios.create({
  timeout: 30_000,
})

http.interceptors.request.use((config) => {
  config.baseURL = getStoredBackendUrl()
  return config
})

function toRequestError(error: unknown): ApiRequestError {
  if (error instanceof ApiRequestError) return error
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiResponse<unknown>>
    const response = axiosError.response
    if (response?.data?.msg) {
      return new ApiRequestError(
        response.data.msg,
        response.data.code,
        response.status,
        response.data.data,
      )
    }
    if (axiosError.code === 'ECONNABORTED') {
      return new ApiRequestError('请求超时，请检查后端任务是否仍在执行')
    }
    if (!response) {
      return new ApiRequestError('无法连接后端服务，请检查地址和服务状态')
    }
    return new ApiRequestError(`请求失败（HTTP ${response.status}）`, undefined, response.status)
  }
  return new ApiRequestError(error instanceof Error ? error.message : '请求失败')
}

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const response = await http.request<ApiResponse<T>>(config)
    const payload = response.data
    if (payload.code !== 0) {
      throw new ApiRequestError(payload.msg || '请求失败', payload.code, response.status, payload.data)
    }
    return payload.data as T
  } catch (error) {
    throw toRequestError(error)
  }
}

export function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status === 404
}

export function getErrorMessage(error: unknown): string {
  return toRequestError(error).message
}

export async function testBackendConnection(baseUrl: string): Promise<HealthData> {
  try {
    const response = await axios.get<ApiResponse<HealthData>>('/health', {
      baseURL: normalizeBackendUrl(baseUrl),
      timeout: 8_000,
    })
    if (response.data.code !== 0 || !response.data.data) {
      throw new ApiRequestError(response.data.msg || '健康检查失败', response.data.code)
    }
    return response.data.data
  } catch (error) {
    throw toRequestError(error)
  }
}

export const agentRequestConfig = {
  timeout: AGENT_TIMEOUT_MS,
} satisfies Pick<AxiosRequestConfig, 'timeout'>
