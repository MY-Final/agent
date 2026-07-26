import { agentRequestConfig, request } from './client'
import type { HealthData } from '@/types/api'
import type { AgentStatus } from '@/types/agent'
import type { MatchResultRecord, ParseResultRecord } from '@/types/results'
import type {
  DownloadUrlData,
  TaskCreateInput,
  TaskDetail,
  TaskFile,
  TaskListData,
  TaskStatus,
} from '@/types/task'

export const taskApi = {
  health: () => request<HealthData>({ method: 'GET', url: '/health' }),

  list: (params: { page?: number; page_size?: number; status?: TaskStatus } = {}) =>
    request<TaskListData>({ method: 'GET', url: '/api/v1/tasks', params }),

  get: (taskId: string) =>
    request<TaskDetail>({ method: 'GET', url: `/api/v1/tasks/${taskId}` }),

  create: (payload: TaskCreateInput) =>
    request<TaskDetail>({ method: 'POST', url: '/api/v1/tasks', data: payload }),

  remove: (taskId: string) =>
    request<{ id: string; deleted: boolean }>({
      method: 'DELETE',
      url: `/api/v1/tasks/${taskId}`,
    }),

  uploadFile: (taskId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<TaskFile>({
      method: 'POST',
      url: `/api/v1/tasks/${taskId}/files/upload`,
      data: formData,
      timeout: 5 * 60 * 1000,
    })
  },

  listFiles: (taskId: string) =>
    request<TaskFile[]>({ method: 'GET', url: `/api/v1/tasks/${taskId}/files` }),

  getDownloadUrl: (taskId: string, fileId: string) =>
    request<DownloadUrlData>({
      method: 'GET',
      url: `/api/v1/tasks/${taskId}/files/${fileId}/download`,
    }),

  startAgent: (taskId: string) =>
    request<AgentStatus>({
      method: 'POST',
      url: `/api/v1/tasks/${taskId}/agent/start`,
      ...agentRequestConfig,
    }),

  getAgentStatus: (taskId: string) =>
    request<AgentStatus>({ method: 'GET', url: `/api/v1/tasks/${taskId}/agent/status` }),

  confirmAgent: (taskId: string, remark?: string) =>
    request<AgentStatus>({
      method: 'POST',
      url: `/api/v1/tasks/${taskId}/agent/confirm`,
      data: { remark: remark?.trim() || null },
      ...agentRequestConfig,
    }),

  getParseResult: (taskId: string) =>
    request<ParseResultRecord>({
      method: 'GET',
      url: `/api/v1/tasks/${taskId}/parse-result`,
    }),

  getMatchResult: (taskId: string) =>
    request<MatchResultRecord>({
      method: 'GET',
      url: `/api/v1/tasks/${taskId}/match-result`,
    }),
}
