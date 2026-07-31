import { request } from './client'
import type { DashboardSummary } from '@/types/dashboard'

export const dashboardApi = {
  summary: () =>
    request<DashboardSummary>({
      method: 'GET',
      url: '/api/v1/dashboard/summary',
    }),
}
