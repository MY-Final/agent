import { request } from './client'
import type { StatsSummary } from '@/types/stats'

export const statsApi = {
  summary: () =>
    request<StatsSummary>({
      method: 'GET',
      url: '/api/v1/stats/summary',
    }),
}
