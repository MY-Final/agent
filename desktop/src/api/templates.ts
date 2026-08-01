import { request, streamSse } from './client'
import type {
  ParseTemplateInput,
  ParseTemplateRecord,
  TemplateSuggestion,
  TemplateSuggestionInput,
} from '@/types/template'

export const templateApi = {
  list: () =>
    request<ParseTemplateRecord[]>({ method: 'GET', url: '/api/v1/templates' }),

  get: (templateId: string) =>
    request<ParseTemplateRecord>({
      method: 'GET',
      url: `/api/v1/templates/${templateId}`,
    }),

  create: (payload: ParseTemplateInput) =>
    request<ParseTemplateRecord>({
      method: 'POST',
      url: '/api/v1/templates',
      data: payload,
    }),

  suggest: (payload: TemplateSuggestionInput) =>
    request<TemplateSuggestion>({
      method: 'POST',
      url: '/api/v1/templates/suggest',
      data: payload,
    }),

  suggestStream: (payload: TemplateSuggestionInput) =>
    streamSse('/api/v1/templates/suggest/stream', payload),

  update: (templateId: string, payload: Partial<ParseTemplateInput>) =>
    request<ParseTemplateRecord>({
      method: 'PUT',
      url: `/api/v1/templates/${templateId}`,
      data: payload,
    }),

  remove: (templateId: string) =>
    request<{ id: string; deleted: boolean }>({
      method: 'DELETE',
      url: `/api/v1/templates/${templateId}`,
    }),
}
