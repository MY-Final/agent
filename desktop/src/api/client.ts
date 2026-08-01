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

export interface SseStreamEvent {
  type: string
  [key: string]: unknown
}

export async function* streamSse(
  url: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SseStreamEvent> {
  /** 用 fetch 读取 SSE 事件流，逐条产出解析后的事件对象。 */
  const response = await fetch(`${getStoredBackendUrl()}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok || !response.body) {
    let message = `请求失败（HTTP ${response.status}）`
    try {
      const payload = (await response.json()) as ApiResponse<unknown>
      if (payload?.msg) message = payload.msg
    } catch {
      // 错误体不是 JSON 时保留默认消息
    }
    throw new ApiRequestError(message, undefined, response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep = buffer.indexOf('\n\n')
    while (sep !== -1) {
      const raw = buffer.slice(0, sep)
      buffer = buffer.slice(sep + 2)
      for (const line of raw.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            yield JSON.parse(line.slice(6)) as SseStreamEvent
          } catch {
            // 跳过无法解析的事件行
          }
        }
      }
      sep = buffer.indexOf('\n\n')
    }
  }
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
