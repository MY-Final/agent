import { agentRequestConfig, request } from './client'
import type { HealthData } from '@/types/api'
import type { AgentStatus } from '@/types/agent'
import type {
  MatchResultRecord,
  ParseResultRecord,
  ParseSourceTextItem,
} from '@/types/results'
import type {
  DownloadUrlData,
  PdfInfo,
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

  getPdfInfo: (taskId: string, fileId: string) =>
    request<PdfInfo>({
      method: 'GET',
      url: `/api/v1/tasks/${taskId}/files/${fileId}/pdf-info`,
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

  rejectAndReparse: (
    taskId: string,
    parseResultId: string,
    reason?: string,
    templateId?: string | null,
  ) =>
    request<AgentStatus>({
      method: 'POST',
      url: `/api/v1/tasks/${taskId}/agent/reject-and-reparse`,
      data: {
        parse_result_id: parseResultId,
        reason: reason?.trim() || null,
        template_id: templateId || null,
      },
      ...agentRequestConfig,
    }),

  getParseResult: (taskId: string) =>
    request<ParseResultRecord>({
      method: 'GET',
      url: `/api/v1/tasks/${taskId}/parse-result`,
    }),

  listParseResults: (taskId: string) =>
    request<ParseResultRecord[]>({
      method: 'GET',
      url: `/api/v1/tasks/${taskId}/parse-results`,
    }),

  updateParseResult: (
    taskId: string,
    parseResultId: string,
    payload: { data: Record<string, unknown>; raw_summary: string | null },
  ) =>
    request<ParseResultRecord>({
      method: 'PUT',
      url: `/api/v1/tasks/${taskId}/parse-results/${parseResultId}`,
      data: payload,
    }),

  getSourceText: (taskId: string, parseResultId: string) =>
    request<ParseSourceTextItem[]>({
      method: 'GET',
      url: `/api/v1/tasks/${taskId}/parse-results/${parseResultId}/source-text`,
    }),

  getMatchResult: (taskId: string) =>
    request<MatchResultRecord>({
      method: 'GET',
      url: `/api/v1/tasks/${taskId}/match-result`,
    }),
}
